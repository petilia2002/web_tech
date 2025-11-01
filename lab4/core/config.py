from dotenv import load_dotenv
import os

load_dotenv()

HOST = os.getenv("HOST", "localhost")
PORT = int(os.getenv("PORT", "5000"))
DEBUG = os.getenv("DEBUG", "TRUE").lower() == "true"

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "webapp_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
SESSION_SECRET = os.getenv("SESSION_SECRET")
