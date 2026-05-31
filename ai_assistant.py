import os
import json
import asyncio
from typing import Literal

import aiohttp

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
