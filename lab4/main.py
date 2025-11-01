# main.py
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from core.config import SESSION_SECRET
from routers import userRouter, roleRouter, authRouter, visitsRouter

# ----------------- FastAPI + статика -----------------
app = FastAPI(title="Пользователи и роли — меню и редактирование")
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Сессии: обязательный middleware ---
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,  # замените секретную строку на свою в проде
)

# Подключаем роутеры
app.include_router(userRouter.router, prefix="/api")
app.include_router(roleRouter.router, prefix="/api")
app.include_router(authRouter.router, prefix="/auth")
app.include_router(visitsRouter.router, prefix="/api")


# ----------------- Страницы -----------------
@app.get("/users")
def users_menu_page():
    return FileResponse("static/users_menu.html")


@app.get("/user-edit")
def edit_page():
    return FileResponse("static/edit_user.html")


@app.get("/user-create")
def create_user_page():
    # та же форма, но фронтенд по пути "/create" включает режим создания
    return FileResponse("static/edit_user.html")


@app.get("/roles")
def roles_menu_page():
    return FileResponse("static/roles_menu.html")


@app.get("/role-edit")
def role_edit_page():
    return FileResponse("static/edit_role.html")


# ----------------- Лабораторная работа №4 -----------------
@app.get("/login")
def users_menu_page():
    return FileResponse("static/login.html")


@app.get("/protected")
def users_menu_page():
    return FileResponse("static/protected.html")


@app.get("/stats")
def users_menu_page():
    return FileResponse("static/stats.html")
