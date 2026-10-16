"""
================================================================================
MÓDULO: routes/community_routes.py   (Blueprint "community")
PRINCIPIO SOLID: Single Responsibility (SRP) + OCP
================================================================================
Nuevo módulo (Abierto/Cerrado: se registró en app.py sin modificar las rutas
existentes). Expone la capa COMUNITARIA adaptada del prompt "EcoEco / BarrioVivo":

  Vistas:
    /profile      → perfil de gamificación (eco-puntos, insignias, nivel)
    /missions     → jornadas de limpieza comunitarias (CleanupMission)
  API:
    GET  /api/profile
    GET  /api/leaderboard
    GET  /api/missions
    POST /api/missions
    POST /api/missions/<id>/join
    POST /api/missions/<id>/complete
================================================================================
"""
from flask import (
    Blueprint, render_template, request, jsonify, session,
    redirect, url_for, current_app,
)

community_bp = Blueprint("community", __name__)


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


def _require_api_login():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401
    return None


# --- Vistas -----------------------------------------------------------------
@community_bp.route("/profile")
def profile_page():
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    profile = _svc("community_service").profile(session.get("user"))
    return render_template(
        "profile.html",
        user=session.get("user"),
        profile=profile,
        leaderboard=_svc("community_service").leaderboard(limit=10),
    )


@community_bp.route("/missions")
def missions_page():
    guard = _require_login()
    if guard:
        return guard

    missions = _svc("community_service").list_missions()
    report_service = _svc("report_service")
    reports_by_id = {r.id: r for r in report_service.list_reports()}
    return render_template(
        "missions.html",
        user=session.get("user"),
        missions=[m.to_dict() for m in missions],
        reports_by_id={k: v.to_dict() for k, v in reports_by_id.items()},
    )


# --- API --------------------------------------------------------------------
@community_bp.route("/api/profile", methods=["GET"])
def api_profile():
    guard = _require_api_login()
    if guard:
        return guard
    return jsonify(_svc("community_service").profile(session.get("user")))


@community_bp.route("/api/leaderboard", methods=["GET"])
def api_leaderboard():
    guard = _require_api_login()
    if guard:
        return guard
    return jsonify(_svc("community_service").leaderboard(limit=10))


@community_bp.route("/api/missions", methods=["GET"])
def api_missions():
    guard = _require_api_login()
    if guard:
        return guard
    return jsonify([m.to_dict() for m in _svc("community_service").list_missions()])


@community_bp.route("/api/missions", methods=["POST"])
def api_create_mission():
    guard = _require_api_login()
    if guard:
        return guard

    payload = request.get_json(silent=True) or request.form.to_dict()
    report_id = payload.get("report_id")

    # Si no se da título, lo derivamos del reporte asociado (DRY).
    title = payload.get("title")
    zone = payload.get("zone", "Centro")
    lat = payload.get("lat", current_app.config["DEFAULT_LAT"])
    lng = payload.get("lng", current_app.config["DEFAULT_LNG"])

    if report_id:
        report = _svc("report_service").get(int(report_id))
        if report is None:
            return jsonify({"error": "El reporte asociado no existe."}), 404
        title = title or f"Limpieza: {report.title}"
        zone = payload.get("zone") or report.zone
        lat = payload.get("lat", report.lat)
        lng = payload.get("lng", report.lng)

    try:
        mission = _svc("community_service").create_mission(
            report_id=int(report_id or 0),
            title=title or "Jornada de limpieza",
            zone=zone,
            lat=lat,
            lng=lng,
            date=payload.get("date"),
            created_by=session.get("user"),
        )
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(mission.to_dict()), 201


@community_bp.route("/api/missions/<int:mission_id>/join", methods=["POST"])
def api_join_mission(mission_id: int):
    guard = _require_api_login()
    if guard:
        return guard

    user = _current_user()
    if user is None:
        return jsonify({"error": "unauthorized"}), 401

    try:
        mission = _svc("community_service").join_mission(mission_id, user)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"mission": mission.to_dict(), "profile": _svc("community_service").profile(user.username)})


@community_bp.route("/api/missions/<int:mission_id>/complete", methods=["POST"])
def api_complete_mission(mission_id: int):
    guard = _require_api_login()
    if guard:
        return guard

    try:
        mission = _svc("community_service").complete_mission(mission_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"mission": mission.to_dict()})
