# routers/visits_router.py
from fastapi import APIRouter, Request, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from db.database import engine

router = APIRouter(tags=["visits"], responses={404: {"description": "Not Found"}})


@router.get("/visit")
def visit_page(request: Request, page: str = Query("protected_page")):
    """
    Записывает визит текущего пользователя в auth.user_visits и возвращает общее количество его заходов на page.
    Если нет сессии — 401.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Не авторизован")

    try:
        with engine.begin() as conn:
            conn.execute(text("SET search_path TO auth, public"))
            conn.execute(
                text(
                    "INSERT INTO auth.user_visits (user_id, page_name) VALUES (:uid, :pname)"
                ),
                {"uid": user_id, "pname": page},
            )
            cnt = conn.execute(
                text(
                    "SELECT COUNT(*) FROM auth.user_visits WHERE user_id = :uid AND page_name = :pname"
                ),
                {"uid": user_id, "pname": page},
            ).scalar_one()
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return {
        "user_id": user_id,
        "page": page,
        "count": int(cnt),
        "message": f"Вы посетили данную страницу {int(cnt)} раз",
    }


@router.get("/stats")
def stats(request: Request, page: str = Query("protected_page")):
    """
    Возвращает агрегированную статистику: для каждого пользователя сколько раз он заходил на page.
    Требует авторизации.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Не авторизован")

    with engine.connect() as conn:
        conn.execute(text("SET search_path TO auth, public"))
        rows = (
            conn.execute(
                text(
                    """
                SELECT u.login, v.page_name, COUNT(*) AS cnt
                FROM auth.user_visits v
                JOIN auth.users u ON u.user_id = v.user_id
                WHERE v.page_name = :pname
                GROUP BY u.login, v.page_name
                ORDER BY cnt DESC, u.login
                """
                ),
                {"pname": page},
            )
            .mappings()
            .all()
        )

    # Вернём список объектов
    items = [
        {"login": r["login"], "page": r["page_name"], "count": int(r["cnt"])}
        for r in rows
    ]
    return {"page": page, "items": items}
