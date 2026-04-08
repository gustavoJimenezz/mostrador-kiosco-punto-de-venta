"""Router de autenticación.

Endpoints:
    GET  /api/auth/users            — lista usuarios activos para la pantalla de login
    POST /api/auth/login            — autentica por user_id + PIN
    POST /api/auth/logout           — cierra la sesión activa
    POST /api/auth/verify-admin-pin — verifica un PIN de administrador sin cambiar sesión
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from src.application.use_cases.authenticate_user import (
    AuthenticateUser,
    AuthenticationError,
)
from src.application.use_cases.elevate_to_admin import ElevateToAdmin
from src.infrastructure.persistence.mariadb_user_repository import (
    MariadbUserRepository,
)
from src.infrastructure.web.dependencies import get_user_repo

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    user_id: int
    pin: str


class AdminPinRequest(BaseModel):
    pin: str


class UserListItem(BaseModel):
    id: int
    name: str
    role: str


@router.get("/users", response_model=list[UserListItem])
def list_users(user_repo: MariadbUserRepository = Depends(get_user_repo)):
    """Lista usuarios activos para la pantalla de selección de login.

    No expone el PIN ni el hash. Solo id, nombre y rol.
    """
    users = user_repo.get_all_active()
    return [
        UserListItem(id=u.id, name=u.name, role=u.role.value)
        for u in users
    ]


@router.post("/login")
def login(
    request: Request,
    body: LoginRequest,
    user_repo: MariadbUserRepository = Depends(get_user_repo),
):
    """Autentica al usuario con su PIN y establece la sesión HTTP.

    Args:
        body: ``{user_id, pin}`` — el PIN viaja en el body (HTTPS en producción).

    Returns:
        ``{user_id, user_name, user_role}`` del usuario autenticado.

    Raises:
        HTTPException 401: Si el PIN es incorrecto o el usuario no existe.
    """
    try:
        use_case = AuthenticateUser(user_repo)
        user = use_case.execute(body.user_id, body.pin)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    request.session["user_id"] = user.id
    request.session["user_name"] = user.name
    request.session["user_role"] = user.role.value

    return {"user_id": user.id, "user_name": user.name, "user_role": user.role.value}


@router.post("/logout")
def logout(request: Request):
    """Cierra la sesión activa limpiando la cookie de sesión."""
    request.session.clear()
    return {"detail": "Sesión cerrada."}


@router.post("/verify-admin-pin")
def verify_admin_pin(
    body: AdminPinRequest,
    user_repo: MariadbUserRepository = Depends(get_user_repo),
):
    """Verifica que el PIN ingresado corresponde a algún administrador activo.

    No modifica la sesión. Devuelve 200 si el PIN es válido, 401 si no.

    Args:
        body: ``{pin}`` — PIN en texto plano.

    Returns:
        ``{ok: true}`` si el PIN es correcto.

    Raises:
        HTTPException 401: Si el PIN no coincide con ningún administrador activo.
    """
    use_case = ElevateToAdmin(user_repo)
    if not use_case.execute(body.pin):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="PIN incorrecto.",
        )
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    """Retorna los datos de la sesión activa o 401 si no hay sesión."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado.",
        )
    return {
        "user_id": user_id,
        "user_name": request.session.get("user_name"),
        "user_role": request.session.get("user_role"),
    }
