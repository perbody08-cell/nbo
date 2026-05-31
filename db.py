import os
import aiosqlite
import asyncio
from typing import Optional

DB_PATH = os.environ.get("DB_PATH", "orders.db")


async def init_db(seed_worker_ids=None):
    """Initialize database tables"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Users table
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

        # Workers table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                user_id INTEGER PRIMARY KEY,
                services TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Orders table
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

        # Services table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS services (
                name TEXT PRIMARY KEY,
                price REAL DEFAULT 0,
                category TEXT DEFAULT 'other'
            )
        """)

        # Worker prices table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS worker_prices (
                worker_id INTEGER,
                service TEXT,
                price REAL DEFAULT 0,
                PRIMARY KEY (worker_id, service)
            )
        """)

        # Withdrawals table
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

        await db.commit()

        # Seed default services if none exist
        cursor = await db.execute("SELECT COUNT(*) FROM services")
        count = await cursor.fetchone()
        if count[0] == 0:
            default_services = [
                ("VK", 50, "main"),
                ("TG", 50, "main"),
                ("WhatsApp", 40, "main"),
                ("Steam", 60, "other"),
                ("OK", 30, "other"),
            ]
            await db.executemany(
                "INSERT INTO services (name, price, category) VALUES (?, ?, ?)",
                default_services
            )
            await db.commit()

        # Seed workers if provided
        if seed_worker_ids:
            for wid in seed_worker_ids:
                await db.execute(
                    "INSERT OR IGNORE INTO workers (user_id, services) VALUES (?, ?)",
                    (wid, "")
                )
            await db.commit()


async def upsert_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
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
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM workers WHERE user_id = ?", (user_id,)
        )
        return await cursor.fetchone() is not None


async def add_worker(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO workers (user_id, services) VALUES (?, ?)",
            (user_id, "")
        )
        await db.commit()


async def remove_worker(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM workers WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_all_workers() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM workers")
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def get_worker_services(user_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT services FROM workers WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if row and row[0]:
            return [s.strip() for s in row[0].split(",") if s.strip()]
        return []


async def set_worker_services(user_id: int, services: list):
    services_str = ",".join(services)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE workers SET services = ? WHERE user_id = ?",
            (services_str, user_id)
        )
        await db.commit()


async def get_workers_for_service(service: str) -> list:
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
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO orders (user_id, service, number, status)
                VALUES (?, ?, ?, 'waiting')""",
            (user_id, service, number)
        )
        await db.commit()
        return cursor.lastrowid


async def get_order(order_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        )
        return await cursor.fetchone()


async def take_order(order_id: int, worker_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE orders SET status = 'active', worker_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE order_id = ?""",
            (worker_id, order_id)
        )
        await db.commit()


async def accept_order(order_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE orders SET status = 'accepted', updated_at = CURRENT_TIMESTAMP
                WHERE order_id = ?""",
            (order_id,)
        )
        await db.commit()


async def reject_order(order_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE orders SET status = 'rejected', updated_at = CURRENT_TIMESTAMP
                WHERE order_id = ?""",
            (order_id,)
        )
        await db.commit()


async def save_code(order_id: int, code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE orders SET code = ?, code_count = code_count + 1, updated_at = CURRENT_TIMESTAMP
                WHERE order_id = ?""",
            (code, order_id)
        )
        await db.commit()


async def get_code_count(order_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT code_count FROM orders WHERE order_id = ?", (order_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def increment_reject_count(order_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET code_count = code_count + 1 WHERE order_id = ?",
            (order_id,)
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT code_count FROM orders WHERE order_id = ?", (order_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def set_code_request_msg_id(order_id: int, msg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET code_request_msg_id = ? WHERE order_id = ?",
            (msg_id, order_id)
        )
        await db.commit()


async def set_worker_msg_id(order_id: int, msg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET worker_msg_id = ? WHERE order_id = ?",
            (msg_id, order_id)
        )
        await db.commit()


async def get_user_active_order(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT * FROM orders 
                WHERE user_id = ? AND status IN ('active', 'waiting')
                ORDER BY created_at DESC LIMIT 1""",
            (user_id,)
        )
        return await cursor.fetchone()


async def get_user_orders_active(user_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT order_id, service, number, status FROM orders
                WHERE user_id = ? AND status IN ('active', 'waiting')
                ORDER BY created_at DESC""",
            (user_id,)
        )
        return await cursor.fetchall()


async def get_user_orders_past(user_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT order_id, service, number, status FROM orders
                WHERE user_id = ? AND status IN ('accepted', 'rejected')
                ORDER BY created_at DESC""",
            (user_id,)
        )
        return await cursor.fetchall()


async def count_user_orders(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0]


async def get_available_orders(worker_id: int) -> list:
    services = await get_worker_services(worker_id)
    if not services:
        return []
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
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT price FROM services WHERE name = ?", (service,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def set_service_price(service: str, price: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO services (name, price) VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET price=excluded.price",
            (service, price)
        )
        await db.commit()


async def get_all_service_prices() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT name, price FROM services")
        rows = await cursor.fetchall()
        return {r[0]: r[1] for r in rows}


async def get_worker_price(worker_id: int, service: str) -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT price FROM worker_prices WHERE worker_id = ? AND service = ?",
            (worker_id, service)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def set_worker_price(worker_id: int, service: str, price: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO worker_prices (worker_id, service, price) VALUES (?, ?, ?)
                ON CONFLICT(worker_id, service) DO UPDATE SET price=excluded.price""",
            (worker_id, service, price)
        )
        await db.commit()


async def get_worker_prices(worker_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT service, price FROM worker_prices WHERE worker_id = ?",
            (worker_id,)
        )
        rows = await cursor.fetchall()
        return {r[0]: r[1] for r in rows}


async def get_user_balance(user_id: int) -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT balance FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def add_user_balance(user_id: int, amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def set_user_balance(user_id: int, balance: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = ? WHERE user_id = ?",
            (balance, user_id)
        )
        await db.commit()


async def get_user_limit(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT order_limit FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 5


async def increment_user_limit(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET order_limit = order_limit + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def create_withdrawal(user_id: int, amount: float, details: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO withdrawals (user_id, amount, details)
                VALUES (?, ?, ?)""",
            (user_id, amount, details)
        )
        await db.commit()
        return cursor.lastrowid


async def get_user_withdrawals(user_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT withdrawal_id, amount, details, status FROM withdrawals
                WHERE user_id = ? ORDER BY created_at DESC""",
            (user_id,)
        )
        return await cursor.fetchall()


async def get_pending_withdrawals() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT * FROM withdrawals WHERE status = 'pending' ORDER BY created_at DESC"""
        )
        return await cursor.fetchall()


async def get_all_withdrawals() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT withdrawal_id, user_id, amount, details, status FROM withdrawals
                ORDER BY created_at DESC"""
        )
        return await cursor.fetchall()


async def get_withdrawal(withdrawal_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM withdrawals WHERE withdrawal_id = ?", (withdrawal_id,)
        )
        return await cursor.fetchone()


async def mark_withdrawal_paid(withdrawal_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE withdrawals SET status = 'paid' WHERE withdrawal_id = ?",
            (withdrawal_id,)
        )
        await db.commit()


async def get_queue_count(service: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE service = ? AND status = 'waiting'",
            (service,)
        )
        row = await cursor.fetchone()
        return row[0]


async def get_queue_position(order_id: int, service: str) -> int:
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
    async with aiosqlite.connect(DB_PATH) as db:
        for admin_id in admin_ids:
            cursor = await db.execute(
                "SELECT username FROM users WHERE user_id = ?", (admin_id,)
            )
            row = await cursor.fetchone()
            if row and row[0]:
                contacts.append(f"@{row[0]}")
            else:
                contacts.append(str(admin_id))
    return contacts




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

async def get_username_by_id(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT username, first_name, last_name FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        username, first_name, last_name = row
        if username:
            return username
        # Build display name from first_name + last_name
        name_parts = []
        if first_name:
            name_parts.append(first_name)
        if last_name:
            name_parts.append(last_name)
        if name_parts:
            return " ".join(name_parts)
        return None


async def get_user_id_by_username(username: str) -> int:
    username = username.lstrip("@")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id FROM users WHERE username = ?", (username,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def get_all_users() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id, username FROM users ORDER BY created_at DESC"
        )
        return await cursor.fetchall()


async def delete_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_all_services() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT name FROM services ORDER BY name")
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def get_main_services() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT name FROM services WHERE category = 'main' ORDER BY name"
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def get_other_services() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT name FROM services WHERE category = 'other' ORDER BY name"
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def get_service_category(service: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT category FROM services WHERE name = ?", (service,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 'other'


async def set_service_category(service: str, category: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE services SET category = ? WHERE name = ?",
            (category, service)
        )
        await db.commit()


async def add_service(name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO services (name) VALUES (?)", (name,)
        )
        await db.commit()


async def remove_service(name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM services WHERE name = ?", (name,))
        await db.commit()


async def remove_all_services():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM services")
        await db.commit()


async def get_orders_by_number(number: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT order_id, user_id, service, number, code, status, worker_id
                FROM orders WHERE number = ? ORDER BY created_at DESC""",
            (number,)
        )
        return await cursor.fetchall()


async def get_user_stats(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,)
        )
        total = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """SELECT COUNT(*) FROM orders WHERE user_id = ? AND status IN ('active', 'waiting')""",
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
