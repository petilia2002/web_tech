# main.py
import os
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Path, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# ----------------- Подключение к БД -----------------
load_dotenv()
url = URL.create(
    "postgresql+psycopg",
    username=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME", "webapp_db"),
)
engine = create_engine(url, future=True)

# ----------------- FastAPI + статика -----------------
app = FastAPI(title="Пользователи и роли — меню и редактирование")
app.mount("/static", StaticFiles(directory="static"), name="static")


# ----------------- Модели пользователей -----------------
class UserOut(BaseModel):
    user_id: int
    last_name: str
    first_name: str
    email: EmailStr
    login: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserUpdate(BaseModel):
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    login: Optional[str] = Field(None, min_length=1, max_length=100)
    password: Optional[str] = Field(None, max_length=200)  # пусто = не менять


class UserCreate(BaseModel):
    last_name: str = Field(..., min_length=1, max_length=100)
    first_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    login: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)  # в ЛР без хеширования


def _row_to_userout(row) -> UserOut:
    return UserOut(
        user_id=row["user_id"],
        last_name=row["last_name"],
        first_name=row["first_name"],
        email=row["email"],
        login=row["login"],
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


# ----------------- Модели ролей -----------------
class RoleOut(BaseModel):
    role_id: int
    name: str
    is_enabled: bool
    created_at: Optional[datetime] = None


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    is_enabled: bool = True


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_enabled: Optional[bool] = None


def _row_to_roleout(row) -> RoleOut:
    return RoleOut(
        role_id=row["role_id"],
        name=row["name"],  # SELECT ... AS name
        is_enabled=bool(row["is_enabled"]),
        created_at=row.get("created_at"),
    )


# ---- модель для выдачи роли пользователю
class RoleGrant(BaseModel):
    role_id: int = Field(..., ge=1)


# ----------------- Страницы -----------------
@app.get("/")
def users_menu_page():
    return FileResponse("static/users_menu.html")


@app.get("/edit")
def edit_page():
    return FileResponse("static/edit_user.html")


@app.get("/roles")
def roles_menu_page():
    return FileResponse("static/roles_menu.html")


@app.get("/role-edit")
def role_edit_page():
    return FileResponse("static/edit_role.html")


# ----------------- Список пользователей (до /{user_id}) -----------------
ALLOWED_ORDER = {
    "id": "u.user_id",
    "login": "u.login",
    "email": "u.email",
    "name": "u.last_name, u.first_name",
}
ALLOWED_DIR = {"asc": "ASC", "desc": "DESC"}


@app.get("/api/users/list")
def users_list(request: Request):
    """Список пользователей с поиском/сортировкой/пагинацией."""
    qp = request.query_params
    q = (qp.get("q") or "").strip()
    try:
        offset = int(qp.get("offset") or 0)
    except Exception:
        offset = 0
    try:
        limit = int(qp.get("limit") or 25)
    except Exception:
        limit = 25
    order = (qp.get("order") or "id").lower()
    direction = (qp.get("direction") or "asc").lower()

    offset = max(0, offset)
    limit = min(max(1, limit), 100)
    order_by = ALLOWED_ORDER.get(order, ALLOWED_ORDER["id"])
    dir_sql = ALLOWED_DIR.get(direction, "ASC")

    where_sql = "WHERE 1=1"
    params_where = {}
    if q:
        where_sql += (
            " AND (lower(u.login) LIKE :q OR lower(u.email) LIKE :q "
            "OR lower(u.last_name) LIKE :q OR lower(u.first_name) LIKE :q)"
        )
        params_where["q"] = f"%{q.lower()}%"

    with engine.connect() as conn:
        conn.execute(text("SET search_path TO auth, public"))

        total = conn.execute(
            text(f"SELECT COUNT(*) FROM auth.users u {where_sql}"),
            params_where,
        ).scalar_one()

        params_paging = {**params_where, "limit": limit, "offset": offset}
        rows = (
            conn.execute(
                text(
                    f"""
                SELECT u.user_id, u.last_name, u.first_name, u.login, u.email, u.created_at
                FROM auth.users u
                {where_sql}
                ORDER BY {order_by} {dir_sql}
                LIMIT :limit OFFSET :offset
            """
                ),
                params_paging,
            )
            .mappings()
            .all()
        )

    return {
        "total": total,
        "items": [
            {
                "user_id": r["user_id"],
                "name": f'{r["last_name"]} {r["first_name"]}',
                "login": r["login"],
                "email": r["email"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
    }


# ----------------- Создание пользователя (до /{user_id}) -----------------
@app.post("/api/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate):
    try:
        with engine.begin() as conn:
            conn.execute(text("SET search_path TO auth, public"))
            row = (
                conn.execute(
                    text(
                        """
                    INSERT INTO auth.users (
                        last_name, first_name, email, login, password_hash, created_at, updated_at
                    )
                    VALUES (:last_name, :first_name, :email, :login, :password_hash, NOW(), NOW())
                    RETURNING user_id, last_name, first_name, email, login, created_at, updated_at
                """
                    ),
                    {
                        "last_name": payload.last_name,
                        "first_name": payload.first_name,
                        "email": str(payload.email),
                        "login": payload.login,
                        "password_hash": payload.password,  # в проде обязательно хешировать
                    },
                )
                .mappings()
                .first()
            )
            return _row_to_userout(row)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Конфликт уникальности email/login")
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")


# ----------------- CRUD по пользователю -----------------
@app.get("/api/users/{user_id}", response_model=UserOut)
def get_user(user_id: int = Path(..., ge=1)):
    with engine.connect() as conn:
        conn.execute(text("SET search_path TO auth, public"))
        row = (
            conn.execute(
                text(
                    """
                SELECT user_id, last_name, first_name, email, login, created_at, updated_at
                FROM auth.users WHERE user_id = :uid
            """
                ),
                {"uid": user_id},
            )
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        return _row_to_userout(row)


@app.put("/api/users/{user_id}", response_model=UserOut)
def update_user(payload: UserUpdate, user_id: int = Path(..., ge=1)):
    fields = []
    params = {"uid": user_id, "updated_at": datetime.now(timezone.utc)}
    if payload.last_name is not None:
        fields.append("last_name = :last_name")
        params["last_name"] = payload.last_name
    if payload.first_name is not None:
        fields.append("first_name = :first_name")
        params["first_name"] = payload.first_name
    if payload.email is not None:
        fields.append("email = :email")
        params["email"] = str(payload.email)
    if payload.login is not None:
        fields.append("login = :login")
        params["login"] = payload.login
    if payload.password not in (None, ""):
        fields.append("password_hash = :password_hash")
        params["password_hash"] = payload.password

    if not fields:
        raise HTTPException(status_code=400, detail="Нет полей для обновления")

    fields.append("updated_at = :updated_at")
    sql = f"UPDATE auth.users SET {', '.join(fields)} WHERE user_id = :uid"

    try:
        with engine.begin() as conn:
            conn.execute(text("SET search_path TO auth, public"))
            res = conn.execute(text(sql), params)
            if res.rowcount == 0:
                raise HTTPException(status_code=404, detail="Пользователь не найден")
            row = (
                conn.execute(
                    text(
                        """
                    SELECT user_id, last_name, first_name, email, login, created_at, updated_at
                    FROM auth.users WHERE user_id = :uid
                """
                    ),
                    {"uid": user_id},
                )
                .mappings()
                .first()
            )
            return _row_to_userout(row)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Конфликт уникальности email/login")
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int = Path(..., ge=1)):
    with engine.begin() as conn:
        conn.execute(text("SET search_path TO auth, public"))
        res = conn.execute(
            text("DELETE FROM auth.users WHERE user_id = :uid"), {"uid": user_id}
        )
        if res.rowcount == 0:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {"status": "success", "deleted_user_id": user_id}


# ----------------- Управление ролями пользователя -----------------
@app.get("/api/users/{user_id}/roles")
def user_roles(user_id: int = Path(..., ge=1)):
    """Получить роли, назначенные пользователю."""
    with engine.connect() as conn:
        conn.execute(text("SET search_path TO auth, public"))
        rows = (
            conn.execute(
                text(
                    """
                SELECT ur.role_id, r.role_name AS name, r.is_enabled
                FROM auth.user_roles ur
                JOIN auth.roles r ON r.role_id = ur.role_id
                WHERE ur.user_id = :uid
                ORDER BY r.role_name
            """
                ),
                {"uid": user_id},
            )
            .mappings()
            .all()
        )
    return {
        "items": [
            {
                "role_id": r["role_id"],
                "name": r["name"],
                "is_enabled": bool(r["is_enabled"]),
            }
            for r in rows
        ]
    }


@app.post("/api/users/{user_id}/roles", status_code=201)
def grant_role(user_id: int = Path(..., ge=1), payload: RoleGrant = ...):
    """Выдать роль пользователю (id роли в теле)."""
    try:
        with engine.begin() as conn:
            conn.execute(text("SET search_path TO auth, public"))
            # Проверяем наличие пользователя и роли
            if not conn.execute(
                text("SELECT 1 FROM auth.users WHERE user_id=:uid"), {"uid": user_id}
            ).first():
                raise HTTPException(status_code=404, detail="Пользователь не найден")
            if not conn.execute(
                text("SELECT 1 FROM auth.roles WHERE role_id=:rid"),
                {"rid": payload.role_id},
            ).first():
                raise HTTPException(status_code=404, detail="Роль не найдена")

            # ON CONFLICT DO NOTHING позволит делать операцию идемпотентной
            conn.execute(
                text(
                    """
                    INSERT INTO auth.user_roles (user_id, role_id)
                    VALUES (:uid, :rid)
                    ON CONFLICT DO NOTHING
                """
                ),
                {"uid": user_id, "rid": payload.role_id},
            )
        return {"status": "ok"}
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")


@app.delete("/api/users/{user_id}/roles/{role_id}")
def revoke_role(user_id: int = Path(..., ge=1), role_id: int = Path(..., ge=1)):
    """Снять роль у пользователя."""
    with engine.begin() as conn:
        conn.execute(text("SET search_path TO auth, public"))
        res = conn.execute(
            text("DELETE FROM auth.user_roles WHERE user_id=:uid AND role_id=:rid"),
            {"uid": user_id, "rid": role_id},
        )
        if res.rowcount == 0:
            raise HTTPException(
                status_code=404, detail="Связь пользователь–роль не найдена"
            )
    return {"status": "ok"}


# ----------------- Список ролей (до /{role_id}) -----------------
ROLES_ALLOWED_ORDER = {
    "id": "r.role_id",
    "name": "r.role_name",
    "status": "r.is_enabled",
}
ROLES_ALLOWED_DIR = {"asc": "ASC", "desc": "DESC"}


@app.get("/api/roles/list")
def roles_list(request: Request):
    """
    Список ролей с поиском, фильтром статуса, сортировкой и пагинацией.
    Параметры: q, status=(all|enabled|disabled), offset, limit, order, direction
    """
    qp = request.query_params
    q = (qp.get("q") or "").strip()
    status = (qp.get("status") or "all").lower()
    try:
        offset = int(qp.get("offset") or 0)
    except Exception:
        offset = 0
    try:
        limit = int(qp.get("limit") or 25)
    except Exception:
        limit = 25
    order = (qp.get("order") or "id").lower()
    direction = (qp.get("direction") or "asc").lower()

    offset = max(0, offset)
    limit = min(max(1, limit), 100)
    order_by = ROLES_ALLOWED_ORDER.get(order, ROLES_ALLOWED_ORDER["id"])
    dir_sql = ROLES_ALLOWED_DIR.get(direction, "ASC")

    where_sql = "WHERE 1=1"
    params_where = {}

    if q:
        where_sql += " AND (lower(r.role_name) LIKE :q)"
        params_where["q"] = f"%{q.lower()}%"

    if status in ("enabled", "disabled"):
        where_sql += " AND r.is_enabled = :st"
        params_where["st"] = status == "enabled"

    with engine.connect() as conn:
        conn.execute(text("SET search_path TO auth, public"))

        total = conn.execute(
            text(f"SELECT COUNT(*) FROM auth.roles r {where_sql}"),
            params_where,
        ).scalar_one()

        params_paging = {**params_where, "limit": limit, "offset": offset}
        rows = (
            conn.execute(
                text(
                    f"""
                SELECT
                    r.role_id,
                    r.role_name AS name,
                    r.is_enabled,
                    r.created_at
                FROM auth.roles r
                {where_sql}
                ORDER BY {order_by} {dir_sql}
                LIMIT :limit OFFSET :offset
            """
                ),
                params_paging,
            )
            .mappings()
            .all()
        )

    return {
        "total": total,
        "items": [
            {
                "role_id": r["role_id"],
                "name": r["name"],
                "is_enabled": bool(r["is_enabled"]),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
    }


# Полный справочник ролей для UI (селект)
@app.get("/api/roles/all")
def roles_all():
    with engine.connect() as conn:
        conn.execute(text("SET search_path TO auth, public"))
        rows = (
            conn.execute(
                text(
                    """
                SELECT role_id, role_name AS name, is_enabled, created_at
                FROM auth.roles
                ORDER BY role_name ASC
            """
                )
            )
            .mappings()
            .all()
        )
    return {
        "items": [
            {
                "role_id": r["role_id"],
                "name": r["name"],
                "is_enabled": bool(r["is_enabled"]),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    }


# ----------------- Создание роли (до /{role_id}) -----------------
@app.post("/api/roles", response_model=RoleOut, status_code=201)
def create_role(payload: RoleCreate):
    try:
        with engine.begin() as conn:
            conn.execute(text("SET search_path TO auth, public"))
            row = (
                conn.execute(
                    text(
                        """
                    INSERT INTO auth.roles (role_name, is_enabled, created_at)
                    VALUES (:name, :is_enabled, NOW())
                    RETURNING role_id, role_name AS name, is_enabled, created_at
                """
                    ),
                    {"name": payload.name, "is_enabled": payload.is_enabled},
                )
                .mappings()
                .first()
            )
            return _row_to_roleout(row)
    except IntegrityError:
        raise HTTPException(
            status_code=409, detail="Роль с таким именем уже существует"
        )
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")


# ----------------- CRUD по конкретной роли -----------------
@app.get("/api/roles/{role_id}", response_model=RoleOut)
def get_role(role_id: int = Path(..., ge=1)):
    with engine.connect() as conn:
        conn.execute(text("SET search_path TO auth, public"))
        row = (
            conn.execute(
                text(
                    """
                SELECT role_id, role_name AS name, is_enabled, created_at
                FROM auth.roles WHERE role_id = :rid
            """
                ),
                {"rid": role_id},
            )
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Роль не найдена")
        return _row_to_roleout(row)


@app.put("/api/roles/{role_id}", response_model=RoleOut)
def update_role(payload: RoleUpdate, role_id: int = Path(..., ge=1)):
    fields = []
    params = {"rid": role_id}
    if payload.name is not None:
        fields.append("role_name = :name")
        params["name"] = payload.name
    if payload.is_enabled is not None:
        fields.append("is_enabled = :is_enabled")
        params["is_enabled"] = payload.is_enabled

    if not fields:
        raise HTTPException(status_code=400, detail="Нет полей для обновления")

    sql = f"UPDATE auth.roles SET {', '.join(fields)} WHERE role_id = :rid"

    try:
        with engine.begin() as conn:
            conn.execute(text("SET search_path TO auth, public"))
            res = conn.execute(text(sql), params)
            if res.rowcount == 0:
                raise HTTPException(status_code=404, detail="Роль не найдена")
            row = (
                conn.execute(
                    text(
                        """
                    SELECT role_id, role_name AS name, is_enabled, created_at
                    FROM auth.roles WHERE role_id = :rid
                """
                    ),
                    {"rid": role_id},
                )
                .mappings()
                .first()
            )
            return _row_to_roleout(row)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Конфликт уникальности имени роли")
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")


@app.delete("/api/roles/{role_id}")
def delete_role(role_id: int = Path(..., ge=1)):
    try:
        with engine.begin() as conn:
            conn.execute(text("SET search_path TO auth, public"))
            res = conn.execute(
                text("DELETE FROM auth.roles WHERE role_id = :rid"), {"rid": role_id}
            )
            if res.rowcount == 0:
                raise HTTPException(status_code=404, detail="Роль не найдена")
        return {"status": "success", "deleted_role_id": role_id}
    except IntegrityError:
        # если есть связи в auth.user_roles и нет ON DELETE CASCADE
        raise HTTPException(
            status_code=409, detail="Нельзя удалить роль: есть связанные пользователи"
        )
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
