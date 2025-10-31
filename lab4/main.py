# main.py
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from routers import userRouter
from routers import roleRouter

# ----------------- FastAPI + статика -----------------
app = FastAPI(title="Пользователи и роли — меню и редактирование")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(userRouter.router, prefix="/api")
app.include_router(roleRouter.router, prefix="/api")


# ----------------- Страницы -----------------
@app.get("/")
def users_menu_page():
    return FileResponse("static/users_menu.html")


@app.get("/edit")
def edit_page():
    return FileResponse("static/edit_user.html")


@app.get("/create")
def create_user_page():
    # та же форма, но фронтенд по пути "/create" включает режим создания
    return FileResponse("static/edit_user.html")


@app.get("/roles")
def roles_menu_page():
    return FileResponse("static/roles_menu.html")


@app.get("/role-edit")
def role_edit_page():
    return FileResponse("static/edit_role.html")
