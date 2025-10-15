# services/auth_service.py
"""
Сервис авторизации: создание и проверка компактного JWT-подобного токена (HS256).
Без внешних зависимостей (можно заменить на PyJWT при желании).

Токен кладётся сервером в HttpOnly-cookie (см. controllers/auth_controller.py),
клиент токен не читает и не хранит — только делает запросы с credentials=include.
"""

from __future__ import annotations

import time
import hmac
import base64
import json
from hashlib import sha256
from typing import Optional, Dict, Any

import config


def _b64url(data: bytes) -> str:
    """URL-safe base64 без хвостовых '='."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64url(s: str) -> bytes:
    """Обратное преобразование: восстановление '=' до кратности 4 и декодирование."""
    pad = 4 - (len(s) % 4)
    if pad and pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s.encode("ascii"))


def create_access_token(claims: Dict[str, Any], *, expires_in: int) -> str:
    """
    Формирует токен с алгоритмом HS256.
    :param claims: произвольные поля (например, {"uid": 1, "u": "user"})
    :param expires_in: время жизни токена в секундах
    :return: строка вида header.payload.signature
    """
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())

    payload = dict(claims)
    payload["iat"] = now
    payload["exp"] = now + int(expires_in)

    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

    signature = hmac.new(config.JWT_SECRET.encode("utf-8"), signing_input, sha256).digest()
    sig_b64 = _b64url(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Валидирует подпись и срок действия токена.
    :return: payload при успехе, иначе None
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

        expected_sig = hmac.new(config.JWT_SECRET.encode("utf-8"), signing_input, sha256).digest()
        actual_sig = _unb64url(sig_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload = json.loads(_unb64url(payload_b64).decode("utf-8"))

        # Проверка срока действия
        if int(payload.get("exp", 0)) < int(time.time()):
            return None

        return payload
    except Exception:
        # Любая ошибка чтения/декодирования — считаем токен невалидным
        return None
