# Noty SMS Bot

Telegram-бот для скупа номеров с AI-ассистентом админа.

## Быстрый старт (локально)

```bash
pip install -r requirements.txt
# Создай .env файл
python main.py
```

## Деплой на Render.com (бесплатно, 24/7)

1. Форкни/загрузи этот репозиторий на GitHub
2. Зарегистрируйся на [render.com](https://render.com)
3. Нажми **New → Web Service → Connect GitHub**
4. Выбери репозиторий
5. Укажи переменные окружения в разделе **Environment**:
   - `TELEGRAM_BOT_TOKEN` — токен от @BotFather
   - `ADMIN_IDS` — твой Telegram ID
   - `AI_API_KEY` — ключ от Groq/Cerebras
6. Нажми **Deploy**

## Переменные окружения

| Переменная | Описание | Пример |
|-----------|----------|--------|
| `TELEGRAM_BOT_TOKEN` | Токен бота от BotFather | `123456:ABC...` |
| `ADMIN_IDS` | ID админов через запятую | `123456789,987654321` |
| `AI_PROVIDER` | Провайдер AI | `groq` |
| `AI_API_KEY` | API ключ для AI | `gsk_...` |

## AI-провайдеры (бесплатно)

- **Groq** (рекомендую): [console.groq.com](https://console.groq.com) — 14,400 запросов/день
- **Cerebras**: [cerebras.ai](https://cerebras.ai) — 1M токенов/день
- **DeepSeek**: [platform.deepseek.com](https://platform.deepseek.com) — 5M токенов

## Команды

- `/start` — начать
- `/admin` — панель админа
- `/ai` — AI-ассистент

## Структура

```
.
├── main.py          # Основной бот
├── admin.py         # Админ-панель
├── ai_assistant.py  # AI-ассистент
├── db.py            # База данных
├── config.py        # Конфигурация
├── states.py        # FSM-состояния
├── bot_avatar.jpg   # Аватарка бота
└── requirements.txt # Зависимости
```
