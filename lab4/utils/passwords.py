# utils/passwords.py
"""
Утилиты для хеширования паролей.

Содержит:
- md5-схему с отдельной солью (для ЛР4, соль длиной 8).

Использование:
  from utils.passwords import generate_salt, hash_md5_with_salt, verify_md5_with_salt
  s = generate_salt()
  h = hash_md5_with_salt("plain", s)
  verify_md5_with_salt("plain", s, h) -> True
"""

from __future__ import annotations
import hashlib
import secrets
import string


# --- MD5 + соль (лаб. требование) ---
def generate_salt(length: int = 8) -> str:
    """Генерирует соль заданной длины (ASCII letters + digits)."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def hash_md5_with_salt(password: str, salt: str) -> str:
    """
    Хеширует пароль как md5(salt || password) и возвращает hex-строку.
    (точно соответствует описанию ЛР)
    """
    if password is None:
        raise ValueError("Password must be provided")
    b = (salt + password).encode("utf-8")
    return hashlib.md5(b).hexdigest()


def verify_md5_with_salt(password: str, salt: str, stored_hash: str) -> bool:
    """Проверяет, соответствует ли пароль (и соль) сохранённому md5-хешу."""
    return hash_md5_with_salt(password, salt) == stored_hash
