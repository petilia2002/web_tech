# routers/auth_router.py
from fastapi import APIRouter, HTTPException, Request, Form
from sqlalchemy import text
from db.database import engine

from utils.passwords import verify_md5_with_salt

router = APIRouter(tags=["auth"], responses={404: {"description": "Not Found"}})


@router.post("/login")
def login(request: Request, login: str = Form(...), password: str = Form(...)):
    """Принимает form data: login, password"""
    with engine.connect() as conn:
        conn.execute(text("SET search_path TO auth, public"))
        row = (
            conn.execute(
                text(
                    "SELECT user_id, login, salt, password_hash, last_name, first_name FROM auth.users WHERE login = :login"
                ),
                {"login": login},
            )
            .mappings()
            .first()
        )

        salt = row["salt"]
        expected = row["password_hash"]

        if not row or not verify_md5_with_salt(password, salt, expected):
            raise HTTPException(status_code=401, detail="Неверный логин/пароль")

        # Успешная авторизация: сохраняем в сессии
        request.session.clear()
        request.session["user_id"] = row["user_id"]
        request.session["login"] = row["login"]
        request.session["full_name"] = f'{row["last_name"]} {row["first_name"]}'
        return {"status": "ok", "message": "Авторизация успешна"}


@router.post("/logout")
def logout(request: Request):
    request.session.pop("user_id", None)
    request.session.pop("login", None)
    request.session.pop("full_name", None)
    return {"status": "ok", "message": "Вы вышли"}
