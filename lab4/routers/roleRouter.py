from fastapi import APIRouter, HTTPException, Path, Request
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from db.database import engine

router = APIRouter(tags=["roles"], responses={404: {"description": "Not Found"}})


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


# ----------------- Управление ролями пользователя -----------------
@router.get("/users/{user_id}/roles")
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


@router.post("/users/{user_id}/roles", status_code=201)
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


@router.delete("/users/{user_id}/roles/{role_id}")
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


@router.get("/roles/list")
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
@router.get("/roles/all")
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
@router.post("/roles", response_model=RoleOut, status_code=201)
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
@router.get("/roles/{role_id}", response_model=RoleOut)
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


@router.put("/roles/{role_id}", response_model=RoleOut)
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


@router.delete("/roles/{role_id}")
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
