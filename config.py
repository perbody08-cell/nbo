import os

# --- Telegram Bot ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# --- Admins ---
_admin_ids_raw = os.environ.get("ADMIN_IDS", "")
ADMINS: set[int] = set()
if _admin_ids_raw:
    for _id in _admin_ids_raw.split(","):
        _id = _id.strip()
        if _id.isdigit():
            ADMINS.add(int(_id))

# --- Workers ---
WORKERS: list[int] = []

# --- Services ---
SERVICES: list[str] = [
    "VK", "TG", "WA", "Viber", "OK", "Mail",
    "Yandex", "Steam", "Discord", "Google",
    "Apple", "Instagram", "Facebook", "Twitter",
    "TikTok", "Avito", "СБЕР", "Tinkoff",
]

MAIN_SERVICES: list[str] = [
    "VK", "TG", "WA", "Viber", "OK", "Mail",
]

OTHER_SERVICES: list[str] = [s for s in SERVICES if s not in MAIN_SERVICES]

# --- AI Assistant Settings ---
AI_PROVIDER = os.environ.get("AI_PROVIDER", "groq")
AI_API_KEY = os.environ.get("AI_API_KEY", "")
