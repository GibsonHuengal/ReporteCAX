"""
================================================================================
MÓDULO: routes/auth_routes.py
PRINCIPIO SOLID: Single Responsibility (SRP)
TEMA DEL CURSO: Refactorización y SRP
================================================================================
Solo define ENDPOINTS HTTP. Toda la lógica está en AuthService.
Esto permite testear los servicios sin arrancar Flask.
================================================================================
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, current_app

auth_bp = Blueprint("auth", __name__)


def _get_auth_service():
    """IoC: el servicio se resuelve desde la app (Inversión de Control)."""
    return current_app.extensions["auth_service"]


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = _get_auth_service().authenticate(username, password)
        if user:
            session["user"] = user.username
            return redirect(url_for("main.index"))
        error = "Usuario o contraseña incorrectos."

    return render_template("auth.html", is_register=False, error=error)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        try:
            user = _get_auth_service().register(username, password)
            session["user"] = user.username
            return redirect(url_for("main.index"))
        except Exception as exc:  # AuthError
            error = str(exc)

    return render_template("auth.html", is_register=True, error=error)


@auth_bp.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("auth.login"))