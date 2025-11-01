# routers/cart_router.py
from fastapi import APIRouter, Request, HTTPException, Body
from sqlalchemy import text
from db.database import engine

router = APIRouter(tags=["cart"], responses={404: {"description": "Not Found"}})


# --- Вспомог: получить cart из сессии как set of ints ---
def _get_cart_set(request: Request):
    c = request.session.get("cart")
    if not c:
        return set()
    # храним как list в сессии, возвращаем set[int]
    try:
        return set(int(x) for x in c)
    except Exception:
        return set()


def _save_cart_set(request: Request, s: set):
    request.session["cart"] = list(s)


# ----------------- Компании: список -----------------
@router.get("/companies")
def companies_list():
    with engine.connect() as conn:
        conn.execute(text("SET search_path TO catalog, public"))
        rows = (
            conn.execute(
                text("SELECT company_id, name FROM catalog.companies ORDER BY name")
            )
            .mappings()
            .all()
        )
    return [{"company_id": r["company_id"], "name": r["name"]} for r in rows]


# ----------------- Автомобили компании (исключая те, что в cart) -----------------
@router.get("/companies/{company_id}/cars")
def company_cars(company_id: int, request: Request):
    cart = _get_cart_set(request)
    with engine.connect() as conn:
        conn.execute(text("SET search_path TO catalog, public"))
        # проверим компанию
        comp = (
            conn.execute(
                text(
                    "SELECT company_id, name FROM catalog.companies WHERE company_id = :cid"
                ),
                {"cid": company_id},
            )
            .mappings()
            .first()
        )
        if not comp:
            raise HTTPException(status_code=404, detail="Фирма не найдена")
        rows = (
            conn.execute(
                text(
                    "SELECT car_id, model, year, price FROM catalog.cars WHERE company_id = :cid ORDER BY model"
                ),
                {"cid": company_id},
            )
            .mappings()
            .all()
        )
    items = []
    for r in rows:
        in_cart = int(r["car_id"]) in cart
        items.append(
            {
                "car_id": r["car_id"],
                "model": r["model"],
                "year": r.get("year"),
                "price": float(r["price"]) if r.get("price") is not None else None,
                "in_cart": in_cart,
            }
        )
    return {
        "company": {"company_id": comp["company_id"], "name": comp["name"]},
        "items": items,
    }


# ----------------- Добавление автомобиля в корзину (POST) -----------------
@router.post("/cart/add")
def cart_add(request: Request, payload: dict = Body(...)):
    """
    Ожидает JSON: {"car_id": <int>}
    Добавляет car_id в request.session['cart'] (множество).
    """
    car_id = payload.get("car_id")
    if car_id is None:
        raise HTTPException(status_code=400, detail="car_id required")
    try:
        car_id = int(car_id)
    except Exception:
        raise HTTPException(status_code=400, detail="car_id must be integer")

    # Проверим, что такой автомобиль есть
    with engine.connect() as conn:
        conn.execute(text("SET search_path TO catalog, public"))
        row = conn.execute(
            text("SELECT car_id FROM catalog.cars WHERE car_id = :cid"), {"cid": car_id}
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Автомобиль не найден")

    cart = _get_cart_set(request)
    if car_id in cart:
        return {"status": "ok", "message": "Уже в корзине", "cart_count": len(cart)}
    cart.add(car_id)
    _save_cart_set(request, cart)
    return {"status": "ok", "message": "Добавлено в заказ", "cart_count": len(cart)}


# ----------------- Просмотр корзины -----------------
@router.get("/cart")
def cart_view(request: Request):
    cart = _get_cart_set(request)
    if not cart:
        return {"items": [], "total": 0}
    with engine.connect() as conn:
        conn.execute(text("SET search_path TO catalog, public"))
        # получим данные для car_id в cart
        rows = (
            conn.execute(
                text(
                    """
                SELECT c.car_id, c.model, c.year, c.price, comp.company_id, comp.name as company_name
                FROM catalog.cars c
                JOIN catalog.companies comp ON comp.company_id = c.company_id
                WHERE c.car_id = ANY(:ids)
                ORDER BY comp.name, c.model
                """
                ),
                {"ids": list(cart)},
            )
            .mappings()
            .all()
        )

    items = []
    total = 0.0
    for r in rows:
        price = float(r["price"]) if r.get("price") is not None else 0.0
        items.append(
            {
                "car_id": r["car_id"],
                "company_id": r["company_id"],
                "company_name": r["company_name"],
                "model": r["model"],
                "year": r.get("year"),
                "price": price,
            }
        )
        total += price
    return {"items": items, "total": total, "count": len(items)}


# ----------------- Очистить корзину -----------------
@router.post("/cart/clear")
def cart_clear(request: Request):
    # просто удалить ключ
    request.session.pop("cart", None)
    return {"status": "ok", "message": "Корзина очищена"}
