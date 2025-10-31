from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class UserRequest(BaseModel):
    name: str
    age: Optional[int] = None
    message: Optional[str] = None


class FormData(BaseModel):
    name: str
    age: Optional[int] = None
    message: Optional[str] = None
    button: str  # Информация о нажатой кнопке


app = FastAPI(title="Тестовый сервер")

# Размещение статических файлов (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.post("/api/json")
async def create_json_data(request: UserRequest):
    """
    Принимает входные данные и возвращает их в формате JSON
    Версия с обработкой POST-запросов
    """
    response_data = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "received_data": {
            "name": request.name,
            "age": request.age,
            "message": request.message,
        },
        "processing_info": {
            "method": "POST",
            "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_length": len(request.name)
            + (len(request.message) if request.message else 0),
        },
    }

    return JSONResponse(content=response_data)


@app.post("/api/form")
async def handle_form(data: FormData):
    """Обработка данных из формы с возвратом информации о кнопке"""

    print(data)

    # Определяем действие на основе нажатой кнопки
    button_actions = {
        "save": "сохранение данных",
        "preview": "предпросмотр данных",
        "reset": "сброс формы",
    }

    action_description = button_actions.get(data.button, "неизвестное действие")

    response_data = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "pressed_button": data.button,
        "button_action": action_description,
        "current_values": {"name": data.name, "age": data.age, "message": data.message},
        "data_length": len(data.name) + (len(data.message) if data.message else 0),
        "processing_time": datetime.now().strftime("%H:%M:%S"),
    }

    return JSONResponse(content=response_data)


@app.get("/")
async def read_root():
    """Главная страница - возвращает HTML файл"""
    return FileResponse("static/index.html")


@app.get("/about")
async def read_root():
    """Главная страница - возвращает HTML файл"""
    return FileResponse("static/about.html")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
