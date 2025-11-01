from fastapi import APIRouter, HTTPException, Path, Request
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from db.database import engine
from utils.passwords import generate_salt, hash_md5_with_salt, verify_md5_with_salt

router = APIRouter(tags=["users"], responses={404: {"description": "Not Found"}})


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


# ----------------- Список пользователей (до /{user_id}) -----------------
ALLOWED_ORDER = {
    "id": "u.user_id",
    "login": "u.login",
    "email": "u.email",
    "name": "u.last_name, u.first_name",
}
ALLOWED_DIR = {"asc": "ASC", "desc": "DESC"}


@router.get("/users/list")
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
@router.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate):
    salt = generate_salt()  # 8 символов по умолчанию
    password_hash = hash_md5_with_salt(payload.password, salt)  # хешируем пароль

    try:
        with engine.begin() as conn:
            conn.execute(text("SET search_path TO auth, public"))
            row = (
                conn.execute(
                    text(
                        """
                    INSERT INTO auth.users (
                        last_name, first_name, email, login, salt, password_hash, created_at, updated_at
                    )
                    VALUES (:last_name, :first_name, :email, :login, :salt, :password_hash, NOW(), NOW())
                    RETURNING user_id, last_name, first_name, email, login, created_at, updated_at
                """
                    ),
                    {
                        "last_name": payload.last_name,
                        "first_name": payload.first_name,
                        "email": str(payload.email),
                        "login": payload.login,
                        "salt": salt,
                        "password_hash": password_hash,
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
@router.get("/users/{user_id}", response_model=UserOut)
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


@router.put("/users/{user_id}", response_model=UserOut)
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


@router.delete("/users/{user_id}")
def delete_user(user_id: int = Path(..., ge=1)):
    with engine.begin() as conn:
        conn.execute(text("SET search_path TO auth, public"))
        res = conn.execute(
            text("DELETE FROM auth.users WHERE user_id = :uid"), {"uid": user_id}
        )
        if res.rowcount == 0:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {"status": "success", "deleted_user_id": user_id}
