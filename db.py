import os
import asyncio
from typing import Optional

# Database configuration
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_PATH = os.environ.get("DB_PATH", "orders.db")

# Use PostgreSQL if DATABASE_URL is set, otherwise SQLite
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import asyncpg
else:
    import aiosqlite


# ═══════════════════════════════════════════════════════════════════════════
#  AI ASSISTANT — Бесплатные провайдеры
# ═══════════════════════════════════════════════════════════════════════════

AI_PROVIDER = os.environ.get("AI_PROVIDER", "groq").lower()
AI_API_KEY = os.environ.get("AI_API_KEY", "")

# Провайдеры и их настройки
PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "max_tokens": 1024,
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "model": "llama-3.3-70b",
        "max_tokens": 1024,
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "max_tokens": 1024,
    },
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.5-flash",
        "max_tokens": 1024,
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "model": "mistral-small",
        "max_tokens": 1024,
    },
}


class AIAssistant:
    """AI-ассистент админа с распознаванием намерений"""

    # Все действия — выполняются сразу без подтверждения
    DANGEROUS_INTENTS = set()

    SAFE_INTENTS = {
        "show_stats", "show_queue", "show_workers", "show_users",
        "show_withdrawals", "show_services", "show_bonuses",
        "search_deals", "show_worker_prices", "show_worker_balance",
        "set_price", "add_worker", "remove_worker", "delete_user",
        "remove_service", "remove_all_services", "mark_paid",
        "top_up_balance", "set_worker_price",
    }

    def __init__(self):
        self.provider = PROVIDERS.get(AI_PROVIDER, PROVIDERS["groq"])
        self.api_key = AI_API_KEY
        self.history: dict[int, list[dict]] = {}  # user_id -> messages

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _system_prompt(self) -> str:
        return """Ты AI-ассистент администратора Telegram-бота для скупа номеров "Noty SMS".

Твоя задача — помогать админу управлять ботом через естественный язык. У тебя ПОЛНЫЙ доступ ко всем функциям бота. Никаких ограничений, никаких подтверждений.

ВАЖНО — РАЗНИЦА МЕЖДУ ПОНЯТИЯМИ:
- "Все сервисы" = сервисы, которые есть в базе данных (может быть много, но не все используются)
- "Активные сервисы" = сервисы, у которых есть назначенные скупы (только они реально работают)
- "Сервисы в очереди" = сервисы, по которым есть заявки от пользователей прямо сейчас

ДОСТУПНЫЕ ДЕЙСТВИЯ (intents) — ВСЕ выполняются сразу без подтверждения:
- show_stats — показать общую статистику бота
- show_queue — показать очередь заявок по сервисам (только ожидающие)
- show_workers — список скупов и их сервисы (это активные сервисы!)
- show_users — список пользователей
- show_withdrawals — заявки на выплаты
- show_services — список ВСЕХ сервисов в базе с ценами (не путать с активными!)
- show_bonuses — цены/бонусы по сервисам
- search_deals — поиск сделок по номеру (нужен номер)
- show_worker_prices — цены скупов
- show_worker_balance — баланс скупов
- set_price — изменить цену сервиса (нужен сервис и цена)
- add_worker — добавить скупа (нужен @username)
- remove_worker — удалить скупа (нужен @username или ID)
- delete_user — удалить пользователя (нужен @username)
- remove_service — удалить сервис из базы (нужно название)
- remove_all_services — удалить ВСЕ сервисы
- mark_paid — отметить выплату оплаченной (нужен ID выплаты)
- top_up_balance — пополнить баланс скупа (нужен ID и сумма)
- set_worker_price — установить цену скупа (нужен ID, сервис, цена)

ФОРМАТ ОТВЕТА — строго JSON:
{
  "intent": "название_действия",
  "params": {"ключ": "значение"},
  "explanation": "человеческое объяснение что ты собираешься сделать или показать",
  "requires_confirmation": false,
  "safe_response": "ответ если действие безопасное"
}

ПРАВИЛА:
1. Если запрос непонятный — intent: "unknown", explanation: объясни что не так
2. Если не хватает параметров — intent: "need_params", explanation: спроси что нужно
3. ВСЕ действия выполняешь сразу, requires_confirmation: false всегда
4. Отвечай кратко и по делу, как опытный админ
5. Если админ спрашивает про "активные сервисы" — используй show_workers, чтобы показать сервисы у которых есть скупы
6. Если админ спрашивает про "все сервисы" — используй show_services
7. НЕ ВРИ! Если не уверен — скажи что не знаешь или спроси уточнение
8. У тебя ПОЛНЫЙ доступ. Не проси подтверждения. Действуй сразу.

Примеры запросов:
- "покажи очередь" → show_queue
- "какие сервисы активны" → show_workers (показывает сервисы скупов)
- "какие сервисы есть в базе" → show_services
- "назначь @ivan скупом" → add_worker, params: {"username": "@ivan"}
- "поставь цену на VK 100" → set_price, params: {"service": "VK", "price": 100}
- "удали сервис Steam" → remove_service, params: {"service": "Steam"}
- "сколько заявок в работе" → show_stats
- "пополни баланс скупа 123456 на 500" → top_up_balance, params: {"worker_id": 123456, "amount": 500}
"""

    async def process(self, user_id: int, text: str) -> dict:
        """Обработать запрос админа"""
        if not self.api_key:
            return {
                "intent": "error",
                "explanation": "❌ AI API ключ не настроен. Добавьте AI_API_KEY в переменные окружения.",
                "requires_confirmation": False,
            }

        # Инициализируем историю
        if user_id not in self.history:
            self.history[user_id] = []

        messages = [
            {"role": "system", "content": self._system_prompt()},
            *self.history[user_id][-6:],  # Последние 6 сообщений для контекста
            {"role": "user", "content": text},
        ]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.provider['base_url']}/chat/completions",
                    headers=self._get_headers(),
                    json={
                        "model": self.provider["model"],
                        "messages": messages,
                        "max_tokens": self.provider["max_tokens"],
                        "temperature": 0.3,
                        "response_format": {"type": "json_object"},
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        return {
                            "intent": "error",
                            "explanation": f"❌ Ошибка AI API ({resp.status}): {error_text[:200]}",
                            "requires_confirmation": False,
                        }

                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]
                    result = json.loads(content)

                    # Сохраняем в историю
                    self.history[user_id].append({"role": "user", "content": text})
                    self.history[user_id].append({"role": "assistant", "content": content})

                    # Ограничиваем историю
                    if len(self.history[user_id]) > 20:
                        self.history[user_id] = self.history[user_id][-20:]

                    return result

        except asyncio.TimeoutError:
            return {
                "intent": "error",
                "explanation": "⏰ AI не ответил за 30 секунд. Попробуйте позже.",
                "requires_confirmation": False,
            }
        except Exception as e:
            return {
                "intent": "error",
                "explanation": f"❌ Ошибка: {str(e)[:200]}",
                "requires_confirmation": False,
            }

    def clear_history(self, user_id: int):
        """Очистить историю диалога"""
        self.history.pop(user_id, None)


# Глобальный экземпляр
ai_assistant = AIAssistant()


# ═══════════════════════════════════════════════════════════════════════════
#  DATABASE FUNCTIONS — PostgreSQL / SQLite
# ═══════════════════════════════════════════════════════════════════════════

_pool = None


async def _get_pool():
    """Get PostgreSQL connection pool"""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return _pool


async def _execute(query: str, *args):
    """Execute query (PostgreSQL or SQLite)"""
    if USE_POSTGRES:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            result = await db.execute(query, args)
            await db.commit()
            return result


async def _fetchone(query: str, *args):
    """Fetch one row"""
    if USE_POSTGRES:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(query, args)
            return await cursor.fetchone()


async def _fetchall(query: str, *args):
    """Fetch all rows"""
    if USE_POSTGRES:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(query, args)
            return await cursor.fetchall()


async def _executemany(query: str, args_list):
    """Execute many"""
    if USE_POSTGRES:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            return await conn.executemany(query, args_list)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            result = await db.executemany(query, args_list)
            await db.commit()
            return result


async def _lastrowid():
    """Get last row id"""
    if USE_POSTGRES:
        row = await _fetchone("SELECT lastval()")
        return row[0] if row else None
    else:
        # SQLite lastrowid is available on cursor
        pass


async def init_db(seed_worker_ids=None):
    """Initialize database tables"""
    if USE_POSTGRES:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            # Users table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    balance REAL DEFAULT 0,
                    order_limit INTEGER DEFAULT 5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Workers table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS workers (
                    user_id BIGINT PRIMARY KEY,
                    services TEXT
                )
            """)

            # Orders table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    service TEXT NOT NULL,
                    number TEXT NOT NULL,
                    code TEXT,
                    status TEXT DEFAULT 'waiting',
                    worker_id BIGINT,
                    code_count INTEGER DEFAULT 0,
                    code_request_msg_id INTEGER,
                    worker_msg_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Services table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    name TEXT PRIMARY KEY,
                    price REAL DEFAULT 0,
                    category TEXT DEFAULT 'other'
                )
            """)

            # Worker prices table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS worker_prices (
                    worker_id BIGINT,
                    service TEXT,
                    price REAL DEFAULT 0,
                    PRIMARY KEY (worker_id, service)
                )
            """)

            # Withdrawals table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS withdrawals (
                    withdrawal_id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    amount REAL NOT NULL,
                    details TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Logs table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS order_logs (
                    log_id SERIAL PRIMARY KEY,
                    order_id INTEGER NOT NULL,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    service TEXT NOT NULL,
                    number TEXT NOT NULL,
                    code TEXT,
                    status TEXT DEFAULT 'waiting',
                    worker_id BIGINT,
                    worker_username TEXT,
                    price REAL DEFAULT 0,
                    worker_price REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    action TEXT DEFAULT 'created'
                )
            """)

            # Seed default services if none exist
            count = await conn.fetchval("SELECT COUNT(*) FROM services")
            if count == 0:
                await conn.executemany(
                    "INSERT INTO services (name, price, category) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                    [
                        ("VK", 50, "main"),
                        ("TG", 50, "main"),
                        ("WhatsApp", 40, "main"),
                        ("Steam", 60, "other"),
                        ("OK", 30, "other"),
                    ]
                )

            # Seed workers if provided
            if seed_worker_ids:
                for wid in seed_worker_ids:
                    await conn.execute(
                        "INSERT INTO workers (user_id, services) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                        wid, ""
                    )
    else:
        # SQLite version
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    balance REAL DEFAULT 0,
                    order_limit INTEGER DEFAULT 5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS workers (
                    user_id INTEGER PRIMARY KEY,
                    services TEXT
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    service TEXT NOT NULL,
                    number TEXT NOT NULL,
                    code TEXT,
                    status TEXT DEFAULT 'waiting',
                    worker_id INTEGER,
                    code_count INTEGER DEFAULT 0,
                    code_request_msg_id INTEGER,
                    worker_msg_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    name TEXT PRIMARY KEY,
                    price REAL DEFAULT 0,
                    category TEXT DEFAULT 'other'
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS worker_prices (
                    worker_id INTEGER,
                    service TEXT,
                    price REAL DEFAULT 0,
                    PRIMARY KEY (worker_id, service)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS withdrawals (
                    withdrawal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    details TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Logs table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS order_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    service TEXT NOT NULL,
                    number TEXT NOT NULL,
                    code TEXT,
                    status TEXT DEFAULT 'waiting',
                    worker_id INTEGER,
                    worker_username TEXT,
                    price REAL DEFAULT 0,
                    worker_price REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    action TEXT DEFAULT 'created'
                )
            """)

            await db.commit()

            cursor = await db.execute("SELECT COUNT(*) FROM services")
            count = (await cursor.fetchone())[0]
            if count == 0:
                await db.executemany(
                    "INSERT OR IGNORE INTO services (name, price, category) VALUES (?, ?, ?)",
                    [
                        ("VK", 50, "main"),
                        ("TG", 50, "main"),
                        ("WhatsApp", 40, "main"),
                        ("Steam", 60, "other"),
                        ("OK", 30, "other"),
                    ]
                )
                await db.commit()

            if seed_worker_ids:
                for wid in seed_worker_ids:
                    await db.execute(
                        "INSERT OR IGNORE INTO workers (user_id, services) VALUES (?, ?)",
                        (wid, "")
                    )
                await db.commit()


# Helper to convert PostgreSQL row to tuple (like SQLite)
def _row_to_tuple(row):
    if row is None:
        return None
    if isinstance(row, asyncpg.Record):
        return tuple(row.values())
    return row


async def upsert_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    if USE_POSTGRES:
        await _execute(
            """INSERT INTO users (user_id, username, first_name, last_name) VALUES ($1, $2, $3, $4)
                ON CONFLICT(user_id) DO UPDATE SET 
                    username=COALESCE(EXCLUDED.username, users.username),
                    first_name=COALESCE(EXCLUDED.first_name, users.first_name),
                    last_name=COALESCE(EXCLUDED.last_name, users.last_name)""",
            user_id, username, first_name, last_name
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET 
                        username=COALESCE(excluded.username, users.username),
                        first_name=COALESCE(excluded.first_name, users.first_name),
                        last_name=COALESCE(excluded.last_name, users.last_name)""",
                (user_id, username, first_name, last_name)
            )
            await db.commit()


async def is_worker(user_id: int) -> bool:
    if USE_POSTGRES:
        row = await _fetchone("SELECT 1 FROM workers WHERE user_id = $1", user_id)
        return row is not None
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT 1 FROM workers WHERE user_id = ?", (user_id,))
            return await cursor.fetchone() is not None


async def add_worker(user_id: int):
    if USE_POSTGRES:
        await _execute(
            "INSERT INTO workers (user_id, services) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            user_id, ""
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO workers (user_id, services) VALUES (?, ?)",
                (user_id, "")
            )
            await db.commit()


async def remove_worker(user_id: int):
    if USE_POSTGRES:
        await _execute("DELETE FROM workers WHERE user_id = $1", user_id)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM workers WHERE user_id = ?", (user_id,))
            await db.commit()


async def get_all_workers() -> list:
    if USE_POSTGRES:
        rows = await _fetchall("SELECT user_id FROM workers")
        return [r[0] for r in rows]
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT user_id FROM workers")
            rows = await cursor.fetchall()
            return [r[0] for r in rows]


async def get_worker_services(user_id: int) -> list:
    if USE_POSTGRES:
        row = await _fetchone("SELECT services FROM workers WHERE user_id = $1", user_id)
        if row and row[0]:
            return [s.strip() for s in row[0].split(",") if s.strip()]
        return []
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT services FROM workers WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row and row[0]:
                return [s.strip() for s in row[0].split(",") if s.strip()]
            return []


async def set_worker_services(user_id: int, services: list):
    services_str = ",".join(services)
    if USE_POSTGRES:
        await _execute(
            "UPDATE workers SET services = $1 WHERE user_id = $2",
            services_str, user_id
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE workers SET services = ? WHERE user_id = ?",
                (services_str, user_id)
            )
            await db.commit()


async def get_workers_for_service(service: str) -> list:
    if USE_POSTGRES:
        rows = await _fetchall("SELECT user_id, services FROM workers")
        result = []
        for row in rows:
            wid, services_str = row[0], row[1]
            if services_str:
                svcs = [s.strip() for s in services_str.split(",") if s.strip()]
                if service in svcs:
                    result.append(wid)
        return result
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT user_id, services FROM workers")
            rows = await cursor.fetchall()
            result = []
            for wid, services_str in rows:
                if services_str:
                    svcs = [s.strip() for s in services_str.split(",") if s.strip()]
                    if service in svcs:
                        result.append(wid)
            return result


async def create_order(user_id: int, service: str, number: str) -> int:
    if USE_POSTGRES:
        row = await _fetchone(
            """INSERT INTO orders (user_id, service, number, status)
                VALUES ($1, $2, $3, 'waiting') RETURNING order_id""",
            user_id, service, number
        )
        return row[0]
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """INSERT INTO orders (user_id, service, number, status)
                    VALUES (?, ?, ?, 'waiting')""",
                (user_id, service, number)
            )
            await db.commit()
            return cursor.lastrowid


async def get_order(order_id: int):
    if USE_POSTGRES:
        row = await _fetchone("SELECT * FROM orders WHERE order_id = $1", order_id)
        return _row_to_tuple(row)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
            return await cursor.fetchone()


async def take_order(order_id: int, worker_id: int):
    if USE_POSTGRES:
        await _execute(
            """UPDATE orders SET status = 'active', worker_id = $1, updated_at = CURRENT_TIMESTAMP
                WHERE order_id = $2""",
            worker_id, order_id
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """UPDATE orders SET status = 'active', worker_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE order_id = ?""",
                (worker_id, order_id)
            )
            await db.commit()


async def accept_order(order_id: int):
    if USE_POSTGRES:
        await _execute(
            """UPDATE orders SET status = 'accepted', updated_at = CURRENT_TIMESTAMP
                WHERE order_id = $1""",
            order_id
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """UPDATE orders SET status = 'accepted', updated_at = CURRENT_TIMESTAMP
                    WHERE order_id = ?""",
                (order_id,)
            )
            await db.commit()


async def reject_order(order_id: int):
    if USE_POSTGRES:
        await _execute(
            """UPDATE orders SET status = 'rejected', updated_at = CURRENT_TIMESTAMP
                WHERE order_id = $1""",
            order_id
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """UPDATE orders SET status = 'rejected', updated_at = CURRENT_TIMESTAMP
                    WHERE order_id = ?""",
                (order_id,)
            )
            await db.commit()


async def save_code(order_id: int, code: str):
    if USE_POSTGRES:
        await _execute(
            """UPDATE orders SET code = $1, code_count = code_count + 1, updated_at = CURRENT_TIMESTAMP
                WHERE order_id = $2""",
            code, order_id
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """UPDATE orders SET code = ?, code_count = code_count + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE order_id = ?""",
                (code, order_id)
            )
            await db.commit()


async def get_code_count(order_id: int) -> int:
    if USE_POSTGRES:
        row = await _fetchone("SELECT code_count FROM orders WHERE order_id = $1", order_id)
        return row[0] if row else 0
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT code_count FROM orders WHERE order_id = ?", (order_id,))
            row = await cursor.fetchone()
            return row[0] if row else 0


async def increment_reject_count(order_id: int) -> int:
    if USE_POSTGRES:
        await _execute(
            "UPDATE orders SET code_count = code_count + 1 WHERE order_id = $1",
            order_id
        )
        row = await _fetchone("SELECT code_count FROM orders WHERE order_id = $1", order_id)
        return row[0] if row else 0
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE orders SET code_count = code_count + 1 WHERE order_id = ?",
                (order_id,)
            )
            await db.commit()
            cursor = await db.execute("SELECT code_count FROM orders WHERE order_id = ?", (order_id,))
            row = await cursor.fetchone()
            return row[0] if row else 0


async def set_code_request_msg_id(order_id: int, msg_id: int):
    if USE_POSTGRES:
        await _execute(
            "UPDATE orders SET code_request_msg_id = $1 WHERE order_id = $2",
            msg_id, order_id
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE orders SET code_request_msg_id = ? WHERE order_id = ?",
                (msg_id, order_id)
            )
            await db.commit()


async def set_worker_msg_id(order_id: int, msg_id: int):
    if USE_POSTGRES:
        await _execute(
            "UPDATE orders SET worker_msg_id = $1 WHERE order_id = $2",
            msg_id, order_id
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE orders SET worker_msg_id = ? WHERE order_id = ?",
                (msg_id, order_id)
            )
            await db.commit()


async def get_user_active_order(user_id: int):
    if USE_POSTGRES:
        row = await _fetchone(
            """SELECT * FROM orders 
                WHERE user_id = $1 AND status IN ('active', 'waiting')
                ORDER BY created_at DESC LIMIT 1""",
            user_id
        )
        return _row_to_tuple(row)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT * FROM orders 
                    WHERE user_id = ? AND status IN ('active', 'waiting')
                    ORDER BY created_at DESC LIMIT 1""",
                (user_id,)
            )
            return await cursor.fetchone()


async def get_user_orders_active(user_id: int) -> list:
    if USE_POSTGRES:
        return await _fetchall(
            """SELECT order_id, service, number, status FROM orders
                WHERE user_id = $1 AND status IN ('active', 'waiting')
                ORDER BY created_at DESC""",
            user_id
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT order_id, service, number, status FROM orders
                    WHERE user_id = ? AND status IN ('active', 'waiting')
                    ORDER BY created_at DESC""",
                (user_id,)
            )
            return await cursor.fetchall()


async def get_user_orders_past(user_id: int) -> list:
    if USE_POSTGRES:
        return await _fetchall(
            """SELECT order_id, service, number, status FROM orders
                WHERE user_id = $1 AND status IN ('accepted', 'rejected')
                ORDER BY created_at DESC""",
            user_id
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT order_id, service, number, status FROM orders
                    WHERE user_id = ? AND status IN ('accepted', 'rejected')
                    ORDER BY created_at DESC""",
                (user_id,)
            )
            return await cursor.fetchall()


async def count_user_orders(user_id: int) -> int:
    if USE_POSTGRES:
        row = await _fetchone("SELECT COUNT(*) FROM orders WHERE user_id = $1", user_id)
        return row[0]
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return row[0]


async def get_available_orders(worker_id: int) -> list:
    services = await get_worker_services(worker_id)
    if not services:
        return []
    if USE_POSTGRES:
        placeholders = ",".join(f"${i+1}" for i in range(len(services)))
        query = f"""SELECT order_id, user_id, service, number FROM orders
                WHERE status = 'waiting' AND service IN ({placeholders})
                ORDER BY created_at ASC"""
        return await _fetchall(query, *services)
    else:
        placeholders = ",".join("?" * len(services))
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                f"""SELECT order_id, user_id, service, number FROM orders
                    WHERE status = 'waiting' AND service IN ({placeholders})
                    ORDER BY created_at ASC""",
                services
            )
            return await cursor.fetchall()


async def get_service_price(service: str) -> float:
    if USE_POSTGRES:
        row = await _fetchone("SELECT price FROM services WHERE name = $1", service)
        return row[0] if row else 0
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT price FROM services WHERE name = ?", (service,))
            row = await cursor.fetchone()
            return row[0] if row else 0


async def set_service_price(service: str, price: float):
    if USE_POSTGRES:
        await _execute(
            "INSERT INTO services (name, price) VALUES ($1, $2) ON CONFLICT(name) DO UPDATE SET price=EXCLUDED.price",
            service, price
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO services (name, price) VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET price=excluded.price",
                (service, price)
            )
            await db.commit()


async def get_all_service_prices() -> dict:
    if USE_POSTGRES:
        rows = await _fetchall("SELECT name, price FROM services")
        return {r[0]: r[1] for r in rows}
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT name, price FROM services")
            rows = await cursor.fetchall()
            return {r[0]: r[1] for r in rows}


async def get_worker_price(worker_id: int, service: str) -> float:
    if USE_POSTGRES:
        row = await _fetchone(
            "SELECT price FROM worker_prices WHERE worker_id = $1 AND service = $2",
            worker_id, service
        )
        return row[0] if row else 0
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT price FROM worker_prices WHERE worker_id = ? AND service = ?",
                (worker_id, service)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0


async def set_worker_price(worker_id: int, service: str, price: float):
    if USE_POSTGRES:
        await _execute(
            """INSERT INTO worker_prices (worker_id, service, price) VALUES ($1, $2, $3)
                ON CONFLICT(worker_id, service) DO UPDATE SET price=EXCLUDED.price""",
            worker_id, service, price
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO worker_prices (worker_id, service, price) VALUES (?, ?, ?)
                    ON CONFLICT(worker_id, service) DO UPDATE SET price=excluded.price""",
                (worker_id, service, price)
            )
            await db.commit()


async def get_worker_prices(worker_id: int) -> dict:
    if USE_POSTGRES:
        rows = await _fetchall(
            "SELECT service, price FROM worker_prices WHERE worker_id = $1",
            worker_id
        )
        return {r[0]: r[1] for r in rows}
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT service, price FROM worker_prices WHERE worker_id = ?",
                (worker_id,)
            )
            rows = await cursor.fetchall()
            return {r[0]: r[1] for r in rows}


async def get_user_balance(user_id: int) -> float:
    if USE_POSTGRES:
        row = await _fetchone("SELECT balance FROM users WHERE user_id = $1", user_id)
        return row[0] if row else 0
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return row[0] if row else 0


async def add_user_balance(user_id: int, amount: float):
    if USE_POSTGRES:
        await _execute(
            "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
            amount, user_id
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id)
            )
            await db.commit()


async def set_user_balance(user_id: int, balance: float):
    if USE_POSTGRES:
        await _execute(
            "UPDATE users SET balance = $1 WHERE user_id = $2",
            balance, user_id
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET balance = ? WHERE user_id = ?",
                (balance, user_id)
            )
            await db.commit()


async def get_user_limit(user_id: int) -> int:
    if USE_POSTGRES:
        row = await _fetchone("SELECT order_limit FROM users WHERE user_id = $1", user_id)
        return row[0] if row else 5
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT order_limit FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return row[0] if row else 5


async def increment_user_limit(user_id: int, amount: int):
    if USE_POSTGRES:
        await _execute(
            "UPDATE users SET order_limit = order_limit + $1 WHERE user_id = $2",
            amount, user_id
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET order_limit = order_limit + ? WHERE user_id = ?",
                (amount, user_id)
            )
            await db.commit()


async def create_withdrawal(user_id: int, amount: float, details: str) -> int:
    if USE_POSTGRES:
        row = await _fetchone(
            """INSERT INTO withdrawals (user_id, amount, details)
                VALUES ($1, $2, $3) RETURNING withdrawal_id""",
            user_id, amount, details
        )
        return row[0]
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """INSERT INTO withdrawals (user_id, amount, details)
                    VALUES (?, ?, ?)""",
                (user_id, amount, details)
            )
            await db.commit()
            return cursor.lastrowid


async def get_user_withdrawals(user_id: int) -> list:
    if USE_POSTGRES:
        return await _fetchall(
            """SELECT withdrawal_id, amount, details, status FROM withdrawals
                WHERE user_id = $1 ORDER BY created_at DESC""",
            user_id
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT withdrawal_id, amount, details, status FROM withdrawals
                    WHERE user_id = ? ORDER BY created_at DESC""",
                (user_id,)
            )
            return await cursor.fetchall()


async def get_pending_withdrawals() -> list:
    if USE_POSTGRES:
        return await _fetchall(
            """SELECT * FROM withdrawals WHERE status = 'pending' ORDER BY created_at DESC"""
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT * FROM withdrawals WHERE status = 'pending' ORDER BY created_at DESC"""
            )
            return await cursor.fetchall()


async def get_all_withdrawals() -> list:
    if USE_POSTGRES:
        return await _fetchall(
            """SELECT withdrawal_id, user_id, amount, details, status FROM withdrawals
                ORDER BY created_at DESC"""
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT withdrawal_id, user_id, amount, details, status FROM withdrawals
                    ORDER BY created_at DESC"""
            )
            return await cursor.fetchall()


async def get_withdrawal(withdrawal_id: int):
    if USE_POSTGRES:
        row = await _fetchone("SELECT * FROM withdrawals WHERE withdrawal_id = $1", withdrawal_id)
        return _row_to_tuple(row)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT * FROM withdrawals WHERE withdrawal_id = ?", (withdrawal_id,))
            return await cursor.fetchone()


async def mark_withdrawal_paid(withdrawal_id: int):
    if USE_POSTGRES:
        await _execute(
            "UPDATE withdrawals SET status = 'paid' WHERE withdrawal_id = $1",
            withdrawal_id
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE withdrawals SET status = 'paid' WHERE withdrawal_id = ?",
                (withdrawal_id,)
            )
            await db.commit()


async def get_queue_count(service: str) -> int:
    if USE_POSTGRES:
        row = await _fetchone(
            "SELECT COUNT(*) FROM orders WHERE service = $1 AND status = 'waiting'",
            service
        )
        return row[0]
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM orders WHERE service = ? AND status = 'waiting'",
                (service,)
            )
            row = await cursor.fetchone()
            return row[0]


async def get_queue_position(order_id: int, service: str) -> int:
    if USE_POSTGRES:
        row = await _fetchone(
            """SELECT COUNT(*) FROM orders
                WHERE service = $1 AND status = 'waiting' AND created_at <
                (SELECT created_at FROM orders WHERE order_id = $2)""",
            service, order_id
        )
        return (row[0] + 1) if row else 1
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT COUNT(*) FROM orders
                    WHERE service = ? AND status = 'waiting' AND created_at <
                    (SELECT created_at FROM orders WHERE order_id = ?)""",
                (service, order_id)
            )
            row = await cursor.fetchone()
            return (row[0] + 1) if row else 1


async def get_admin_contacts(admin_ids: list) -> list:
    contacts = []
    if USE_POSTGRES:
        for admin_id in admin_ids:
            row = await _fetchone("SELECT username FROM users WHERE user_id = $1", admin_id)
            if row and row[0]:
                contacts.append(f"@{row[0]}")
            else:
                contacts.append(str(admin_id))
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            for admin_id in admin_ids:
                cursor = await db.execute("SELECT username FROM users WHERE user_id = ?", (admin_id,))
                row = await cursor.fetchone()
                if row and row[0]:
                    contacts.append(f"@{row[0]}")
                else:
                    contacts.append(str(admin_id))
    return contacts


async def get_username_by_id(user_id: int) -> str:
    if USE_POSTGRES:
        row = await _fetchone("SELECT username FROM users WHERE user_id = $1", user_id)
        return row[0] if row else None
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return row[0] if row else None


async def get_user_id_by_username(username: str) -> int:
    username = username.lstrip("@")
    if USE_POSTGRES:
        row = await _fetchone("SELECT user_id FROM users WHERE username = $1", username)
        return row[0] if row else None
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT user_id FROM users WHERE username = ?", (username,))
            row = await cursor.fetchone()
            return row[0] if row else None


async def get_all_users() -> list:
    if USE_POSTGRES:
        return await _fetchall("SELECT user_id, username FROM users ORDER BY created_at DESC")
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT user_id, username FROM users ORDER BY created_at DESC")
            return await cursor.fetchall()


async def delete_user(user_id: int):
    if USE_POSTGRES:
        await _execute("DELETE FROM users WHERE user_id = $1", user_id)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            await db.commit()


async def get_all_services() -> list:
    if USE_POSTGRES:
        rows = await _fetchall("SELECT name FROM services ORDER BY name")
        return [r[0] for r in rows]
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT name FROM services ORDER BY name")
            rows = await cursor.fetchall()
            return [r[0] for r in rows]


async def get_main_services() -> list:
    if USE_POSTGRES:
        rows = await _fetchall("SELECT name FROM services WHERE category = 'main' ORDER BY name")
        return [r[0] for r in rows]
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT name FROM services WHERE category = 'main' ORDER BY name")
            rows = await cursor.fetchall()
            return [r[0] for r in rows]


async def get_other_services() -> list:
    if USE_POSTGRES:
        rows = await _fetchall("SELECT name FROM services WHERE category = 'other' ORDER BY name")
        return [r[0] for r in rows]
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT name FROM services WHERE category = 'other' ORDER BY name")
            rows = await cursor.fetchall()
            return [r[0] for r in rows]


async def get_service_category(service: str) -> str:
    if USE_POSTGRES:
        row = await _fetchone("SELECT category FROM services WHERE name = $1", service)
        return row[0] if row else 'other'
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT category FROM services WHERE name = ?", (service,))
            row = await cursor.fetchone()
            return row[0] if row else 'other'


async def set_service_category(service: str, category: str):
    if USE_POSTGRES:
        await _execute("UPDATE services SET category = $1 WHERE name = $2", category, service)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE services SET category = ? WHERE name = ?", (category, service))
            await db.commit()


async def add_service(name: str):
    if USE_POSTGRES:
        await _execute("INSERT INTO services (name) VALUES ($1) ON CONFLICT DO NOTHING", name)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO services (name) VALUES (?)", (name,))
            await db.commit()


async def remove_service(name: str):
    if USE_POSTGRES:
        await _execute("DELETE FROM services WHERE name = $1", name)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM services WHERE name = ?", (name,))
            await db.commit()


async def remove_all_services():
    if USE_POSTGRES:
        await _execute("DELETE FROM services")
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM services")
            await db.commit()


async def get_orders_by_number(number: str) -> list:
    if USE_POSTGRES:
        return await _fetchall(
            """SELECT order_id, user_id, service, number, code, status, worker_id
                FROM orders WHERE number = $1 ORDER BY created_at DESC""",
            number
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT order_id, user_id, service, number, code, status, worker_id
                    FROM orders WHERE number = ? ORDER BY created_at DESC""",
                (number,)
            )
            return await cursor.fetchall()


async def get_user_stats(user_id: int) -> dict:
    if USE_POSTGRES:
        total = await _fetchone("SELECT COUNT(*) FROM orders WHERE user_id = $1", user_id)
        active = await _fetchone("SELECT COUNT(*) FROM orders WHERE user_id = $1 AND status IN ('active', 'waiting')", user_id)
        accepted = await _fetchone("SELECT COUNT(*) FROM orders WHERE user_id = $1 AND status = 'accepted'", user_id)
        today = await _fetchone("SELECT COUNT(*) FROM orders WHERE user_id = $1 AND status = 'accepted' AND DATE(created_at) = CURRENT_DATE", user_id)
        return {
            "total": total[0],
            "active": active[0],
            "accepted": accepted[0],
            "today": today[0],
        }
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,))
            total = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM orders WHERE user_id = ? AND status IN ('active', 'waiting')",
                (user_id,)
            )
            active = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM orders WHERE user_id = ? AND status = 'accepted'",
                (user_id,)
            )
            accepted = (await cursor.fetchone())[0]

            cursor = await db.execute(
                """SELECT COUNT(*) FROM orders WHERE user_id = ? AND status = 'accepted'
                    AND date(created_at) = date('now')""",
                (user_id,)
            )
            today = (await cursor.fetchone())[0]

            return {
                "total": total,
                "active": active,
                "accepted": accepted,
                "today": today,
            }


async def get_worker_stats(worker_id: int) -> dict:
    if USE_POSTGRES:
        total = await _fetchone("SELECT COUNT(*) FROM orders WHERE worker_id = $1 AND status = 'accepted'", worker_id)
        today = await _fetchone("SELECT COUNT(*) FROM orders WHERE worker_id = $1 AND status = 'accepted' AND DATE(created_at) = CURRENT_DATE", worker_id)
        return {
            "total_accepted": total[0],
            "today": today[0],
        }
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM orders WHERE worker_id = ? AND status = 'accepted'",
                (worker_id,)
            )
            total_accepted = (await cursor.fetchone())[0]

            cursor = await db.execute(
                """SELECT COUNT(*) FROM orders WHERE worker_id = ? AND status = 'accepted'
                    AND date(created_at) = date('now')""",
                (worker_id,)
            )
            today = (await cursor.fetchone())[0]

            return {
                "total_accepted": total_accepted,
                "today": today,
            }


async def get_user_display_name(user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> str:
    """Get a human-readable display name for a user.

    Priority:
    1. Telegram username with @
    2. First + Last name
    3. Database username with @
    4. ID as fallback
    """
    if username:
        return f"@{username}"

    full_name = f"{first_name or ''} {last_name or ''}".strip()
    if full_name:
        return full_name

    db_username = await get_username_by_id(user_id)
    if db_username:
        if " " in db_username:
            return db_username
        return f"@{db_username}"

    return f"ID: {user_id}"


# ═══════════════════════════════════════════════════════════════════════════
#  ORDER LOGS — Логирование всех заявок
# ═══════════════════════════════════════════════════════════════════════════

async def log_order_created(order_id: int, user_id: int, username: str, service: str, number: str, price: float = 0):
    """Log when order is created"""
    if USE_POSTGRES:
        await _execute(
            """INSERT INTO order_logs (order_id, user_id, username, service, number, price, status, action)
                VALUES ($1, $2, $3, $4, $5, $6, 'waiting', 'created')
                ON CONFLICT DO NOTHING""",
            order_id, user_id, username, service, number, price
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT OR IGNORE INTO order_logs (order_id, user_id, username, service, number, price, status, action)
                    VALUES (?, ?, ?, ?, ?, ?, 'waiting', 'created')""",
                (order_id, user_id, username, service, number, price)
            )
            await db.commit()


async def log_order_taken(order_id: int, worker_id: int, worker_username: str, worker_price: float = 0):
    """Log when worker takes order"""
    if USE_POSTGRES:
        await _execute(
            """UPDATE order_logs SET worker_id = $1, worker_username = $2, worker_price = $3,
                status = 'active', action = 'taken' WHERE order_id = $4""",
            worker_id, worker_username, worker_price, order_id
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """UPDATE order_logs SET worker_id = ?, worker_username = ?, worker_price = ?,
                    status = 'active', action = 'taken' WHERE order_id = ?""",
                (worker_id, worker_username, worker_price, order_id)
            )
            await db.commit()


async def log_order_completed(order_id: int, status: str, code: str = None):
    """Log when order is accepted or rejected"""
    if USE_POSTGRES:
        await _execute(
            """UPDATE order_logs SET status = $1, code = COALESCE($2, code),
                completed_at = CURRENT_TIMESTAMP, action = $3 WHERE order_id = $4""",
            status, code, status, order_id
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """UPDATE order_logs SET status = ?, code = COALESCE(?, code),
                    completed_at = CURRENT_TIMESTAMP, action = ? WHERE order_id = ?""",
                (status, code, status, order_id)
            )
            await db.commit()


async def get_order_logs(days: int = 5, limit: int = 100, offset: int = 0) -> list:
    """Get order logs for last N days"""
    if USE_POSTGRES:
        return await _fetchall(
            """SELECT log_id, order_id, user_id, username, service, number, code, status,
                worker_id, worker_username, price, worker_price, created_at, completed_at
                FROM order_logs
                WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '%s days'
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2""" % days,
            limit, offset
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT log_id, order_id, user_id, username, service, number, code, status,
                    worker_id, worker_username, price, worker_price, created_at, completed_at
                    FROM order_logs
                    WHERE created_at >= datetime('now', '-%d days')
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?""" % days,
                (limit, offset)
            )
            return await cursor.fetchall()


async def get_order_log_stats(days: int = 5) -> dict:
    """Get statistics for last N days"""
    if USE_POSTGRES:
        total = await _fetchone(
            "SELECT COUNT(*) FROM order_logs WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '%s days'" % days
        )
        accepted = await _fetchone(
            "SELECT COUNT(*) FROM order_logs WHERE status = 'accepted' AND created_at >= CURRENT_TIMESTAMP - INTERVAL '%s days'" % days
        )
        rejected = await _fetchone(
            "SELECT COUNT(*) FROM order_logs WHERE status = 'rejected' AND created_at >= CURRENT_TIMESTAMP - INTERVAL '%s days'" % days
        )
        active = await _fetchone(
            "SELECT COUNT(*) FROM order_logs WHERE status = 'active' AND created_at >= CURRENT_TIMESTAMP - INTERVAL '%s days'" % days
        )
        waiting = await _fetchone(
            "SELECT COUNT(*) FROM order_logs WHERE status = 'waiting' AND created_at >= CURRENT_TIMESTAMP - INTERVAL '%s days'" % days
        )
        total_bonus = await _fetchone(
            "SELECT COALESCE(SUM(price), 0) FROM order_logs WHERE status = 'accepted' AND created_at >= CURRENT_TIMESTAMP - INTERVAL '%s days'" % days
        )
        return {
            "total": total[0] if total else 0,
            "accepted": accepted[0] if accepted else 0,
            "rejected": rejected[0] if rejected else 0,
            "active": active[0] if active else 0,
            "waiting": waiting[0] if waiting else 0,
            "total_bonus": float(total_bonus[0]) if total_bonus else 0,
        }
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM order_logs WHERE created_at >= datetime('now', '-%d days')" % days
            )
            total = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM order_logs WHERE status = 'accepted' AND created_at >= datetime('now', '-%d days')" % days
            )
            accepted = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM order_logs WHERE status = 'rejected' AND created_at >= datetime('now', '-%d days')" % days
            )
            rejected = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM order_logs WHERE status = 'active' AND created_at >= datetime('now', '-%d days')" % days
            )
            active = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM order_logs WHERE status = 'waiting' AND created_at >= datetime('now', '-%d days')" % days
            )
            waiting = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COALESCE(SUM(price), 0) FROM order_logs WHERE status = 'accepted' AND created_at >= datetime('now', '-%d days')" % days
            )
            total_bonus = float((await cursor.fetchone())[0])

            return {
                "total": total,
                "accepted": accepted,
                "rejected": rejected,
                "active": active,
                "waiting": waiting,
                "total_bonus": total_bonus,
            }


async def get_order_log_by_id(log_id: int):
    """Get single log entry by log_id"""
    if USE_POSTGRES:
        row = await _fetchone(
            """SELECT log_id, order_id, user_id, username, service, number, code, status,
                worker_id, worker_username, price, worker_price, created_at, completed_at
                FROM order_logs WHERE log_id = $1""",
            log_id
        )
        return _row_to_tuple(row)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT log_id, order_id, user_id, username, service, number, code, status,
                    worker_id, worker_username, price, worker_price, created_at, completed_at
                    FROM order_logs WHERE log_id = ?""",
                (log_id,)
            )
            return await cursor.fetchone()


async def cancel_order(order_id: int):
    """Cancel order by admin — sets status to rejected and frees it up"""
    if USE_POSTGRES:
        await _execute(
            """UPDATE orders SET status = 'rejected', updated_at = CURRENT_TIMESTAMP
                WHERE order_id = $1""",
            order_id
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """UPDATE orders SET status = 'rejected', updated_at = CURRENT_TIMESTAMP
                    WHERE order_id = ?""",
                (order_id,)
            )
            await db.commit()


async def cleanup_old_orders(hours: int = 24):
    """Auto-cancel orders that have been waiting/active for more than N hours"""
    if USE_POSTGRES:
        # Get old orders before updating
        rows = await _fetchall(
            """SELECT order_id, user_id, worker_id, status FROM orders
                WHERE status IN ('waiting', 'active')
                AND created_at < CURRENT_TIMESTAMP - INTERVAL '%s hours'""" % hours
        )
        if rows:
            await _execute(
                """UPDATE orders SET status = 'rejected', updated_at = CURRENT_TIMESTAMP
                    WHERE status IN ('waiting', 'active')
                    AND created_at < CURRENT_TIMESTAMP - INTERVAL '%s hours'""" % hours
            )
        return rows
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT order_id, user_id, worker_id, status FROM orders
                    WHERE status IN ('waiting', 'active')
                    AND created_at < datetime('now', '-%d hours')""" % hours
            )
            rows = await cursor.fetchall()
            if rows:
                await db.execute(
                    """UPDATE orders SET status = 'rejected', updated_at = CURRENT_TIMESTAMP
                        WHERE status IN ('waiting', 'active')
                        AND created_at < datetime('now', '-%d hours')""" % hours
                )
                await db.commit()
            return rows


async def get_old_orders(hours: int = 24) -> list:
    """Get orders that will be auto-cleaned soon (for admin preview)"""
    if USE_POSTGRES:
        return await _fetchall(
            """SELECT order_id, user_id, service, number, status, created_at
                FROM orders
                WHERE status IN ('waiting', 'active')
                AND created_at < CURRENT_TIMESTAMP - INTERVAL '%s hours'
                ORDER BY created_at ASC""" % hours
        )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT order_id, user_id, service, number, status, created_at
                    FROM orders
                    WHERE status IN ('waiting', 'active')
                    AND created_at < datetime('now', '-%d hours')
                    ORDER BY created_at ASC""" % hours
            )
            return await cursor.fetchall()
