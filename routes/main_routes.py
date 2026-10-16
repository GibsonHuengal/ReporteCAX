"""
================================================================================
MÓDULO: routes/main_routes.py
PRINCIPIO SOLID: Single Responsibility (SRP) + Dependency Inversion (DIP)
================================================================================
Endpoints de la aplicación principal. Solo traducen HTTP ↔ servicios.
No contienen reglas de negocio ni persistencia.

ADAPTACIÓN DE "EcoEco / BarrioVivo" A ESTE PROYECTO:
  Se añaden los endpoints que el prompt de la app Android requería:
    - POST /api/reports        → crea reporte con FOTO + clasificación IA local
    - POST /api/reports/<id>/upvote    → votos comunitarios (transacción)
    - POST /api/reports/<id>/status    → cambio de estado (admin/operador)
    - GET  /api/reports?lat&lng&radius → reportes cercanos (geofencing)
    - GET  /api/heatmap                → puntos para el mapa de calor
    - POST /api/classify               → inferencia IA sobre una imagen
================================================================================
"""
from flask import (
    Blueprint, render_template, request, jsonify, session,
    redirect, url_for, current_app,
)

main_bp = Blueprint("main", __name__)

STATUS_ROLES = {"admin", "operador"}


# --- Helpers (resolución de dependencias vía IoC) ---------------------------
def _require_login():
    if "user" not in session:
        return redirect(url_for("auth.login"))
    return None


def _svc(name: str):
    return current_app.extensions[name]


def _current_user():
    username = session.get("user")
    if not username:
        return None
    return _svc("user_repo").get_by_username(username)


# --- Vistas -----------------------------------------------------------------
@main_bp.route("/")
def index():
    guard = _require_login()
    if guard:
        return guard

    reports = _svc("report_service").list_reports()
    summary = _svc("analytics_service").compute_summary(reports)
    user = _current_user()

    profile = None
    if user is not None:
        profile = _svc("community_service").profile(user.username)

    return render_template(
        "index.html",
        user=session.get("user"),
        summary=summary,
        profile=profile,
        leaderboard=_svc("community_service").leaderboard(limit=5),
        default_lat=current_app.config["DEFAULT_LAT"],
        default_lng=current_app.config["DEFAULT_LNG"],
        geofence_km=current_app.config["GEOFENCE_RADIUS_KM"],
    )


# --- API JSON (usadas por static/js/app.js) ---------------------------------
@main_bp.route("/api/reports", methods=["GET"])
def api_reports():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401

    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    radius = request.args.get("radius", type=float)

    if lat is not None and lng is not None and radius is not None:
        reports = _svc("report_service").list_nearby(lat, lng, radius)
    else:
        reports = _svc("report_service").list_reports()

    return jsonify([r.to_dict() for r in reports])


@main_bp.route("/api/reports", methods=["POST"])
def api_create_report():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401

    # Aceptamos JSON o form/multipart. Si viene JSON se usa; si no, los campos
    # del formulario. (Si no estuviéramos enviando las 400, un submit del
    # formulario "tiraría" los campos.)
    payload = request.get_json(silent=True) or request.form.to_dict()

    photo_url = None
    ai_label = None
    ai_confidence = 0.0
    group = payload.get("group") or None

    photo = request.files.get("photo")
    if photo and getattr(photo, "filename", ""):
        try:
            raw = photo.read()
            result = _svc("image_classifier").classify(raw)
            ai_label = result.label
            ai_confidence = result.confidence
            # `group` NO se fuerza aquí: si el usuario no eligió tipo, el
            # servicio de reportes decide si adopta la etiqueta de la IA.
            # Reutilizamos el mismo stream para persistir la imagen.
            photo.stream.seek(0)
            photo_url = _svc("storage_service").save_image(photo)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    try:
        report = _svc("report_service").create_report(
            title=payload.get("title", ""),
            description=payload.get("description", ""),
            zone=payload.get("zone", "Centro"),
            lat=payload.get("lat", current_app.config["DEFAULT_LAT"]),
            lng=payload.get("lng", current_app.config["DEFAULT_LNG"]),
            severity=payload.get("severity_level") or payload.get("severity", "critico"),
            username=session.get("user"),
            photo_url=photo_url,
            ai_label=ai_label,
            ai_confidence=ai_confidence,
            group=group,
        )
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400

    # Gamificación: recompensa al autor + posible insignia nueva.
    reward = _svc("community_service").on_report_created(_current_user())

    body = report.to_dict()
    body["ai_label"] = ai_label
    body["ai_confidence"] = ai_confidence
    body["reward"] = reward
    return jsonify(body), 201


@main_bp.route("/api/reports/<int:report_id>/upvote", methods=["POST"])
def api_upvote_report(report_id: int):
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401

    report = _svc("report_service").upvote(report_id)
    if report is None:
        return jsonify({"error": "Reporte no encontrado."}), 404

    # El autor recibe eco-puntos por cada voto.
    reward = _svc("community_service").on_upvote_received(report.user)
    return jsonify({"report": report.to_dict(), "owner_reward": reward})


@main_bp.route("/api/reports/<int:report_id>/status", methods=["POST"])
def api_change_status(report_id: int):
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401

    user = _current_user()
    if user is None or user.role not in STATUS_ROLES:
        return jsonify({"error": "Solo admin/operador pueden cambiar el estado."}), 403

    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").upper()

    try:
        report = _svc("report_service").change_status(report_id, status)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if report is None:
        return jsonify({"error": "Reporte no encontrado."}), 404

    # Gamificación según el nuevo estado, al autor del reporte.
    community = _svc("community_service")
    owner = _svc("user_repo").get_by_username(report.user) if report.user else None
    if status == "RESUELTO":
        reward = community.on_report_resolved(owner)
    elif status == "EN_PROCESO":
        reward = community.on_report_in_process(owner)
    else:
        reward = {"points": 0, "unlocked": []}

    return jsonify({"report": report.to_dict(), "owner_reward": reward})


@main_bp.route("/api/summary", methods=["GET"])
def api_summary():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401
    reports = _svc("report_service").list_reports()
    return jsonify(_svc("analytics_service").compute_summary(reports))


@main_bp.route("/api/heatmap", methods=["GET"])
def api_heatmap():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(_svc("report_service").heatmap_points())


@main_bp.route("/api/classify", methods=["POST"])
def api_classify():
    """Inferencia IA local sobre una imagen (para vista previa en el formulario)."""
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401

    photo = request.files.get("photo")
    if not photo or not getattr(photo, "filename", ""):
        return jsonify({"error": "Falta la imagen."}), 400

    try:
        raw = photo.read()
        result = _svc("image_classifier").classify(raw)
        return jsonify(result.to_dict())
    except Exception as exc:  # noqa: BLE001 — degradamos a error controlado
        return jsonify({"error": f"No se pudo procesar la imagen: {exc}"}), 400
