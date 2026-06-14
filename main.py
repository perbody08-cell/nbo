import asyncio
import os
import re

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    FSInputFile,
)
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext

from config import TOKEN, WORKERS, ADMINS
from states import OrderState, AdminState
from db import (
    init_db,
    upsert_user,
    is_worker,
    create_order,
    get_order,
    take_order,
    set_code_request_msg_id,
    set_worker_msg_id,
    get_user_active_order,
    get_user_orders_active,
    get_user_orders_past,
    count_user_orders,
    save_code,
    get_code_count,
    accept_order,
    reject_order,
    increment_reject_count,
    get_worker_services,
    get_workers_for_service,
    get_service_price,
    get_user_balance,
    add_user_balance,
    get_worker_price,
    create_withdrawal,
    get_queue_count,
    get_queue_position,
    get_admin_contacts,
    get_main_services,
    get_other_services,
    get_username_by_id,
    get_user_display_name,
    get_user_withdrawals,
    get_user_limit,
    increment_user_limit,
    get_available_orders,
    get_user_stats,
    get_worker_stats,
    log_order_created,
    log_order_taken,
    log_order_completed,
)
import admin as admin_module

# ═══════════════════════════════════════════════════════════════════════════
#  STARTUP DIAGNOSTICS
# ═══════════════════════════════════════════════════════════════════════════
import os
print("=" * 60)
print("NOTY SMS BOT - STARTUP CHECK")
print(f"TOKEN from env: {bool(os.environ.get('TELEGRAM_BOT_TOKEN'))}")
print(f"TOKEN from config: {bool(TOKEN)} (len={len(TOKEN)})")
print(f"ADMINS: {ADMINS}")
print(f"WORKERS: {WORKERS}")
print("=" * 60)

if not TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN is not set!")
    print("Please set TELEGRAM_BOT_TOKEN in Railway Variables")
    # Don't exit - let it fail naturally with clear error
# ═══════════════════════════════════════════════════════════════════════════

bot = Bot(token=TOKEN)
dp = Dispatcher()
dp.include_router(admin_module.router)


_active_timers: set = set()


class Style:
    PRIMARY   = "\U0001f535"
    SUCCESS   = "\U0001f7e2"
    DANGER    = "\U0001f534"
    WARNING   = "\U0001f7e1"
    INFO      = "\U0001f537"
    MONEY     = "\U0001f4b0"
    USER      = "\U0001f464"
    WORKER    = "\U0001f477"
    ADMIN     = "\U0001f451"
    PHONE     = "\U0001f4f1"
    CODE      = "\U0001f511"
    ORDER     = "\U0001f4cb"
    QUEUE     = "\U0001f4ca"
    BACK      = "\U000025c0\U0000fe0f"
    HOME      = "\U0001f3e0"
    SUPPORT   = "\U0001f198"
    PROFILE   = "\U0001f464"
    WITHDRAW  = "\U0001f4b8"
    ACTIVE    = "\U0001f4cb"
    HISTORY   = "\U0001f550"
    SETTINGS  = "\U00002699\U0000fe0f"
    ADD       = "\U00002795"
    REMOVE    = "\U0001f5d1\U0000fe0f"
    EDIT      = "\U0000270f\U0000fe0f"
    SEARCH    = "\U0001f50d"
    BONUS     = "\U0001f381"
    PRICE     = "\U0001f3f7\U0000fe0f"
    BALANCE   = "\U0001f4b3"
    SERVICES  = "\U0001f9e9"
    STATS     = "\U0001f4c8"
    STAR      = "\U00002b50"
    ARROW_R   = "\U000025b6\U0000fe0f"
    ARROW_L   = "\U000025c0\U0000fe0f"
    CHECK     = "\U00002705"
    CROSS     = "\U0000274c"
    REFRESH   = "\U0001f504"
    BELL      = "\U0001f514"
    CLOCK     = "\U000023f0"
    CHAT      = "\U0001f4ac"
    DOC       = "\U0001f4c4"
    PIN       = "\U0001f4cc"
    FIRE      = "\U0001f525"
    CROWN     = "\U0001f451"
    GEM       = "\U0001f48e"


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=f"{Style.PHONE} Сдать номер"),
                KeyboardButton(text=f"{Style.SUPPORT} Поддержка"),
            ],
            [
                KeyboardButton(text=f"{Style.ACTIVE} Активные заявки"),
                KeyboardButton(text=f"{Style.HISTORY} Прошлые заявки"),
            ],
            [
                KeyboardButton(text=f"{Style.PROFILE} Профиль"),
                KeyboardButton(text=f"{Style.WITHDRAW} Выплата"),
            ],
            [
                KeyboardButton(text=f"{Style.BALANCE} Мои заявки на вывод"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие...",
    )


def worker_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"{Style.QUEUE} Очередь заявок")],
            [KeyboardButton(text=f"{Style.PROFILE} Профиль")],
            [KeyboardButton(text=f"{Style.MONEY} Баланс")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие...",
    )


def admin_start_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"{Style.ADMIN} Админ-панель")],
        ],
        resize_keyboard=True,
    )


def back_kb(callback_data: str = "back_to_services") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data=callback_data)]
        ]
    )


def service_selected_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{Style.BACK} Изменить сервис", callback_data="back_to_services"
                )
            ]
        ]
    )


def take_order_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{Style.CHECK} Взять заявку", callback_data=f"take_{order_id}"
                )
            ]
        ]
    )


def worker_action_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{Style.SUCCESS} Принять", callback_data=f"accept_{order_id}"
                ),
                InlineKeyboardButton(
                    text=f"{Style.WARNING} Запросить повтор", callback_data=f"reject_{order_id}"
                ),
            ]
        ]
    )


def not_admin(message: Message) -> bool:
    return message.from_user.id not in ADMINS

def admin_only(user_id: int) -> bool:
    return user_id in ADMINS



RUSSIAN_PHONE_RE = re.compile(r"^\+?7\d{10}$")
CODE_RE = re.compile(r"^\d+$")

STATUS_LABELS = {
    "waiting":  f"{Style.CLOCK} Ожидает скупа",
    "active":   f"{Style.REFRESH} В работе",
    "accepted": f"{Style.SUCCESS} Принята",
    "rejected": f"{Style.DANGER} Отклонена",
}


async def build_services_kb() -> InlineKeyboardMarkup:
    rows = []
    main_services = await get_main_services()
    if not main_services:
        main_services = []
    for service in main_services:
        price = await get_service_price(service)
        label = f"{Style.STAR} {service} — {price} $"
        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"service_{service}")]
        )
    other_svcs = await get_other_services()
    if other_svcs:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{Style.ARROW_R} Другие сервисы", callback_data="service_Другие сервисы"
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def build_other_services_kb() -> InlineKeyboardMarkup:
    rows = []
    for service in await get_other_services():
        price = await get_service_price(service)
        label = f"{Style.INFO} {service} — {price} $"
        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"oservice_{service}")]
        )
    rows.append(
        [InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="back_to_services")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)




# Channel subscription check
REQUIRED_CHANNEL = "@notiyone"


async def is_subscribed(user_id: int) -> bool:
    """Check if user is subscribed to required channel"""
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False


async def send_subscription_request(message: Message):
    """Send message asking user to subscribe to channel"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{Style.BELL} Подписаться на канал", url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}")],
            [InlineKeyboardButton(text=f"{Style.REFRESH} Проверить подписку", callback_data="check_subscription")],
        ]
    )
    await message.answer(
        f"{Style.WARNING} <b>Доступ ограничен</b>\n\n"
        f"{Style.INFO} Для использования бота необходимо подписаться на канал:\n"
        f"{Style.BELL} {REQUIRED_CHANNEL}\n\n"
        f"{Style.INFO} После подписки нажмите «Проверить подписку».",
        reply_markup=kb,
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, state: FSMContext):
    """Handle subscription check button"""
    if await is_subscribed(callback.from_user.id):
        await callback.message.delete()
        await callback.answer(f"{Style.CHECK} Подписка подтверждена!")
        # Restart the start flow
        await start(callback.message, state)
    else:
        await callback.answer(
            f"{Style.CROSS} Вы ещё не подписались на канал {REQUIRED_CHANNEL}",
            show_alert=True,
        )

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    # Check subscription first
    if not await is_subscribed(message.from_user.id):
        await send_subscription_request(message)
        return

    await upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
    await state.clear()

    if message.from_user.id in ADMINS:
        await message.answer(
            f"{Style.CROWN} <b>Добро пожаловать, Администратор!</b>\n\n"
            f"Используйте /admin для открытия панели управления.",
            reply_markup=admin_start_kb(),
            parse_mode="HTML",
        )
        return

    if await is_worker(message.from_user.id):
        services = await get_worker_services(message.from_user.id)
        if services:
            await message.answer(
                f"{Style.WORKER} <b>Вы вошли как скуп</b>\n\n"
                f"{Style.SERVICES} Ваши сервисы: <code>{', '.join(services)}</code>\n\n"
                f"{Style.BELL} Ожидайте новых заявок — они будут приходить сюда автоматически.",
                reply_markup=worker_menu_kb(),
                parse_mode="HTML",
            )
        else:
            await message.answer(
                f"{Style.WORKER} <b>Вы вошли как скуп</b>\n\n"
                f"{Style.WARNING} Вам пока не назначен ни один сервис.\n"
                f"{Style.SUPPORT} Обратитесь к администратору.",
                reply_markup=worker_menu_kb(),
                parse_mode="HTML",
            )
        return

    balance = await get_user_balance(message.from_user.id)
    avatar = FSInputFile("bot_avatar.jpg")
    await message.answer_photo(
        photo=avatar,
        caption=
        f"{Style.GEM} <b>Добро пожаловать в Noty SMS!</b>\n\n"
        f"{Style.MONEY} Ваш баланс: <code>{balance} $</code>\n"
        f"{Style.INFO} Work Empire — надежный скуп номеров\n\n"
        f"Выберите нужный раздел в меню ниже.",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


@dp.message(F.text.contains("Очередь заявок"))
async def worker_queue(message: Message, state: FSMContext):
    await state.clear()
    if not await is_worker(message.from_user.id):
        await message.answer(f"{Style.CROSS} Нет доступа", reply_markup=main_menu_kb())
        return

    # Show worker balance
    worker_balance = await get_user_balance(message.from_user.id)

    orders = await get_available_orders(message.from_user.id)
    if not orders:
        msg = f"{Style.QUEUE} Очередь пуста. Новые заявки приходят автоматически.\n\n" + f"{Style.MONEY} Ваш баланс: <code>{worker_balance} $</code>"
        await message.answer(msg, reply_markup=worker_menu_kb())
        return

    # Show orders with price info
    for oid, uid, svc, number in orders:
        worker_price = await get_worker_price(message.from_user.id, svc) or 0
        can_afford = worker_balance >= worker_price if worker_price > 0 else True
        price_info = f" | {Style.MONEY} {worker_price} $" if worker_price > 0 else ""
        afford_icon = Style.SUCCESS if can_afford else Style.DANGER
        afford_text = "Можно взять" if can_afford else f"Нужно: {worker_price} $, у вас: {worker_balance} $"

        msg = f"{Style.ORDER} <b>#{oid}</b> | {Style.PHONE} {svc} | <code>{number}</code>{price_info}\n" + f"{afford_icon} {afford_text}"

        await message.answer(
            msg,
            reply_markup=take_order_kb(oid) if can_afford else None,
            parse_mode="HTML",
        )

    msg = f"{Style.INFO} Всего: <b>{len(orders)}</b> заявок.\n"
    msg += f"{Style.MONEY} Ваш баланс: <code>{worker_balance} $</code>"
    await message.answer(
        msg,
        reply_markup=worker_menu_kb(),
        parse_mode="HTML",
    )


@dp.message(F.text.contains("Баланс"))
async def worker_balance(message: Message, state: FSMContext):
    await state.clear()
    if not await is_worker(message.from_user.id):
        await message.answer(f"{Style.CROSS} Нет доступа", reply_markup=main_menu_kb())
        return
    bal = await get_user_balance(message.from_user.id)
    await message.answer(
        f"{Style.MONEY} <b>Баланс:</b> <code>{bal} $</code>",
        reply_markup=worker_menu_kb(),
        parse_mode="HTML",
    )


@dp.message(F.text.contains("Профиль"))
async def profile_menu(message: Message, state: FSMContext):
    if not await is_subscribed(message.from_user.id):
        await send_subscription_request(message)
        return
    await state.clear()
    uid = message.from_user.id
    user_label = await get_user_display_name(
        uid, 
        message.from_user.username, 
        message.from_user.first_name, 
        message.from_user.last_name
    )
    balance = await get_user_balance(uid)

    if await is_worker(uid):
        stats = await get_worker_stats(uid)
        text = (
            f"{Style.WORKER} <b>Профиль скупа</b>\n\n"
            f"{Style.USER} Юзернейм: <code>{user_label}</code>\n"
            f"{Style.MONEY} Баланс: <code>{balance} $</code>\n\n"
            f"{Style.STATS} <b>Статистика:</b>\n"
            f"  {Style.CHECK} Принято за все время: <b>{stats['total_accepted']}</b>\n"
            f"  {Style.FIRE} За сегодня: <b>{stats['today']}</b>"
        )
        await message.answer(text, reply_markup=worker_menu_kb(), parse_mode="HTML")
    else:
        stats = await get_user_stats(uid)
        limit = await get_user_limit(uid)
        text = (
            f"{Style.USER} <b>Профиль</b>\n\n"
            f"{Style.USER} Юзернейм: <code>{user_label}</code>\n"
            f"{Style.MONEY} Баланс: <code>{balance} $</code>\n"
            f"{Style.PIN} Лимит заявок: <b>{limit}</b>\n\n"
            f"{Style.STATS} <b>Статистика заявок:</b>\n"
            f"  {Style.ORDER} Всего создано: <b>{stats['total']}</b>\n"
            f"  {Style.ACTIVE} Активных: <b>{stats['active']}</b>\n"
            f"  {Style.SUCCESS} Принятых: <b>{stats['accepted']}</b>\n"
            f"  {Style.FIRE} Зачислено сегодня: <b>{stats['today']}</b>"
        )
        await message.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")


@dp.message(F.text.contains("Выплата"))
async def withdrawal_start(message: Message, state: FSMContext):
    if not await is_subscribed(message.from_user.id):
        await send_subscription_request(message)
        return
    await state.clear()
    balance = await get_user_balance(message.from_user.id)
    if balance <= 0:
        msg = f"{Style.CROSS} На вашем балансе недостаточно средств для вывода.\n\n"
        msg += f"{Style.MONEY} Ваш баланс: <code>{balance} $</code>"
        await message.answer(
            msg,
            reply_markup=main_menu_kb(),
        )
        return

    # Auto-submit withdrawal without asking for requisites
    await add_user_balance(message.from_user.id, -balance)
    await create_withdrawal(message.from_user.id, balance, "Не указаны — уточнить у пользователя")
    username = await get_username_by_id(message.from_user.id)
    user_label = f"@{username}" if username else str(message.from_user.id)
    for admin_id in ADMINS:
        try:
            admin_msg = f"{Style.WITHDRAW} <b>Новая заявка на выплату</b>\n\n"
            admin_msg += f"{Style.USER} Пользователь: <code>{user_label}</code>\n"
            admin_msg += f"{Style.MONEY} Сумма: <code>{balance} $</code>\n"
            admin_msg += f"{Style.DOC} Реквизиты: <code>Не указаны — уточнить у пользователя</code>\n\n"
            admin_msg += f"{Style.WARNING} Пользователь не указал реквизиты. Свяжитесь с ним для уточнения."
            await bot.send_message(
                admin_id,
                admin_msg,
                parse_mode="HTML",
            )
        except Exception:
            pass
    user_msg = f"{Style.CHECK} Заявка на выплату отправлена администратору.\n\n"
    user_msg += f"{Style.MONEY} Сумма: <code>{balance} $</code>\n"
    user_msg += f"{Style.INFO} Администратор свяжется с вами для уточнения реквизитов."
    await message.answer(
        user_msg,
        reply_markup=main_menu_kb(),
    )


@dp.message(AdminState.entering_withdrawal_details)
async def withdrawal_input(message: Message, state: FSMContext):
    details = message.text.strip()
    if not details:
        await message.answer(f"{Style.CROSS} Введите реквизиты для вывода.")
        return
    data = await state.get_data()
    amount = data.get("withdrawal_amount", 0)
    await add_user_balance(message.from_user.id, -amount)
    await create_withdrawal(message.from_user.id, amount, details)
    username = await get_username_by_id(message.from_user.id)
    user_label = f"@{username}" if username else str(message.from_user.id)
    for admin_id in ADMINS:
        try:
            await bot.send_message(
                admin_id,
                f"{Style.WITHDRAW} <b>Новая заявка на выплату</b>\n\n"
                f"{Style.USER} Пользователь: <code>{user_label}</code>\n"
                f"{Style.MONEY} Сумма: <code>{amount} $</code>\n"
                f"{Style.DOC} Реквизиты: <code>{details}</code>",
                parse_mode="HTML",
            )
        except Exception:
            pass
    await state.clear()
    await message.answer(
        f"{Style.CHECK} Заявка на выплату отправлена администратору.",
        reply_markup=main_menu_kb(),
    )


@dp.message(F.text.contains("Сдать номер"))
async def submit_number_menu(message: Message, state: FSMContext):
    if not await is_subscribed(message.from_user.id):
        await send_subscription_request(message)
        return
    await state.clear()
    await state.set_state(OrderState.choosing_service)
    kb = await build_services_kb()
    sent = await message.answer(
        f"{Style.SERVICES} <b>Выберите сервис:</b>",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await state.update_data(service_msg_id=sent.message_id)


@dp.message(F.text.contains("Поддержка"))
async def support_menu(message: Message, state: FSMContext):
    if not await is_subscribed(message.from_user.id):
        await send_subscription_request(message)
        return
    await state.clear()
    contacts = await get_admin_contacts(list(ADMINS))
    if contacts:
        contact_str = "\n".join(contacts)
        text = (
            f"{Style.SUPPORT} <b>Поддержка</b>\n\n"
            f"{Style.INFO} По всем вопросам обращайтесь к администратору:\n"
            f"<code>{contact_str}</code>"
        )
    else:
        text = (
            f"{Style.SUPPORT} <b>Поддержка</b>\n\n"
            f"{Style.INFO} По всем вопросам обращайтесь к администратору."
        )
    await message.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")


@dp.message(F.text.contains("Активные заявки"))
async def active_orders_menu(message: Message, state: FSMContext):
    if not await is_subscribed(message.from_user.id):
        await send_subscription_request(message)
        return
    await state.clear()
    orders = await get_user_orders_active(message.from_user.id)
    if not orders:
        await message.answer(
            f"{Style.INFO} У вас нет активных заявок.",
            reply_markup=main_menu_kb(),
        )
        return
    lines = [f"{Style.ACTIVE} <b>Активные заявки:</b>\n"]
    for oid, service, number, status in orders:
        label = STATUS_LABELS.get(status, status)
        lines.append(
            f"{Style.ORDER} <b>#{oid}</b> | {Style.PHONE} {service} | <code>{number}</code>\n"
            f"   {label}"
        )
    await message.answer("\n".join(lines), reply_markup=main_menu_kb(), parse_mode="HTML")


@dp.message(F.text.contains("Прошлые заявки"))
async def past_orders_menu(message: Message, state: FSMContext):
    if not await is_subscribed(message.from_user.id):
        await send_subscription_request(message)
        return
    await state.clear()
    orders = await get_user_orders_past(message.from_user.id)
    if not orders:
        await message.answer(
            f"{Style.INFO} У вас нет завершенных заявок.",
            reply_markup=main_menu_kb(),
        )
        return
    lines = [f"{Style.HISTORY} <b>Прошлые заявки:</b>\n"]
    for oid, service, number, status in orders:
        label = STATUS_LABELS.get(status, status)
        lines.append(
            f"{Style.ORDER} <b>#{oid}</b> | {Style.PHONE} {service} | <code>{number}</code>\n"
            f"   {label}"
        )
    await message.answer("\n".join(lines), reply_markup=main_menu_kb(), parse_mode="HTML")


@dp.message(F.text.contains("Мои заявки на вывод"))
async def my_withdrawals_menu(message: Message, state: FSMContext):
    if not await is_subscribed(message.from_user.id):
        await send_subscription_request(message)
        return
    await state.clear()
    rows = await get_user_withdrawals(message.from_user.id)
    if not rows:
        await message.answer(
            f"{Style.INFO} У вас нет заявок на вывод.",
            reply_markup=main_menu_kb(),
        )
        return
    lines = [f"{Style.BALANCE} <b>Мои заявки на вывод:</b>\n"]
    for wid, amount, details, status in rows:
        status_icon = f"{Style.SUCCESS} Оплачена" if status == 'paid' else f"{Style.CLOCK} В ожидании"
        lines.append(
            f"{Style.ORDER} <b>#{wid}</b> | {Style.MONEY} {amount} $ | {Style.DOC} {details}\n"
            f"   {status_icon}"
        )
    await message.answer("\n".join(lines), reply_markup=main_menu_kb(), parse_mode="HTML")


@dp.callback_query(F.data.startswith("service_"))
async def choose_service(callback: CallbackQuery, state: FSMContext):
    service = callback.data.split("_", 1)[1]
    if service == "Другие сервисы":
        kb = await build_other_services_kb()
        await callback.message.edit_text(
            f"{Style.SERVICES} <b>Выберите сервис из категории «Другие»:</b>",
            reply_markup=kb,
            parse_mode="HTML",
        )
        await state.set_state(OrderState.choosing_other_service)
        await callback.answer()
        return
    price = await get_service_price(service)
    await state.update_data(service=service)
    await state.set_state(OrderState.entering_number)
    bonus_line = f"{Style.BONUS} Бонус при выполнении: <code>{price} $</code>\n\n"
    await callback.message.edit_text(
        f"{Style.CHECK} <b>Выбран сервис:</b> <code>{service}</code>\n"
        f"{bonus_line}"
        f"{Style.PHONE} Введите игровой номер в формате <code>79121231212</code>:",
        reply_markup=service_selected_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("oservice_"))
async def choose_other_service(callback: CallbackQuery, state: FSMContext):
    service = callback.data[9:]
    price = await get_service_price(service)
    await state.update_data(service=service)
    await state.set_state(OrderState.entering_number)
    bonus_line = f"{Style.BONUS} Бонус при выполнении: <code>{price} $</code>\n\n"
    await callback.message.edit_text(
        f"{Style.CHECK} <b>Выбран сервис:</b> <code>{service}</code>\n"
        f"{bonus_line}"
        f"{Style.PHONE} Введите игровой номер в формате <code>79121231212</code>:",
        reply_markup=service_selected_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data == "back_to_services")
async def back_to_services(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.choosing_service)
    await state.update_data(service=None)
    kb = await build_services_kb()
    await callback.message.edit_text(
        f"{Style.SERVICES} <b>Выберите сервис:</b>",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(OrderState.entering_number)
async def enter_number(message: Message, state: FSMContext):
    raw_lines = [line.strip() for line in message.text.strip().split("\n") if line.strip()]
    if not raw_lines:
        await message.answer(f"{Style.CROSS} Введите хотя бы один номер.")
        return

    valid_numbers = []
    invalid_numbers = []
    for number in raw_lines:
        if RUSSIAN_PHONE_RE.match(number):
            valid_numbers.append(number)
        else:
            invalid_numbers.append(number)

    if invalid_numbers:
        await message.answer(
            f"{Style.CROSS} <b>Неверный формат номеров:</b>\n"
            f"<code>{chr(10).join(invalid_numbers)}</code>\n\n"
            f"{Style.INFO} Правильный формат:\n"
            f"<code>79121231212</code> или <code>+79121231212</code>"
        )
        return

    data = await state.get_data()
    service = data["service"]

    user_limit = await get_user_limit(message.from_user.id)
    total = await count_user_orders(message.from_user.id)
    remaining = user_limit - total
    if remaining <= 0:
        user_kb = worker_menu_kb() if await is_worker(message.from_user.id) else main_menu_kb()
        await message.answer(
            f"{Style.CROSS} Вы уже подали максимум <b>{user_limit}</b> заявок.\n"
            f"{Style.CLOCK} Дождитесь обработки текущих заявок.",
            reply_markup=user_kb,
            parse_mode="HTML",
        )
        await state.clear()
        return

    numbers_to_process = valid_numbers[:remaining]
    created = []
    for number in numbers_to_process:
        order_id = await create_order(message.from_user.id, service, number)
        
        # Логирование создания заявки
        username = message.from_user.username
        price = await get_service_price(service)
        await log_order_created(
            order_id, 
            message.from_user.id, 
            username, 
            service, 
            number, 
            price
        )
        
        queue_pos = await get_queue_position(order_id, service)
        bonus = await get_service_price(service)
        queue_total = await get_queue_count(service)

        workers_for_service = await get_workers_for_service(service)
        notified = 0
        for worker_id in workers_for_service:
            if await is_worker(worker_id):
                try:
                    worker_bonus = await get_worker_price(worker_id, service)
                    bonus_line = f"{Style.MONEY} Цена для скупа: <code>{worker_bonus or 0} $</code>\n"
                    await bot.send_message(
                        worker_id,
                        f"{Style.BELL} <b>Новая заявка #{order_id}</b>\n\n"
                        f"{Style.SERVICES} Сервис: <code>{service}</code>\n"
                        f"{Style.PHONE} Номер: <code>{number}</code>\n"
                        f"{bonus_line}"
                        f"{Style.QUEUE} В очереди: <b>{queue_total}</b> номеров",
                        reply_markup=take_order_kb(order_id),
                        parse_mode="HTML",
                    )
                    notified += 1
                except Exception as e:
                    # Логировать ошибку отправки уведомления скупу
                    print(f"[ERROR] Failed to notify worker {worker_id}: {e}")

        created.append((order_id, number, notified))

    lines = [f"{Style.SUCCESS} <b>Заявки созданы:</b>\n"]
    for order_id, number, notified in created:
        lines.append(
            f"{Style.ORDER} <b>#{order_id}</b> | {Style.PHONE} <code>{number}</code> | "
            f"{Style.WORKER} скупов уведомлено: <b>{notified}</b>"
        )
    if len(valid_numbers) > remaining:
        lines.append(
            f"\n{Style.WARNING} Создано только <b>{remaining}</b> из <b>{len(valid_numbers)}</b> — "
            f"лимит <b>{user_limit}</b> заявок."
        )
    user_kb = worker_menu_kb() if await is_worker(message.from_user.id) else main_menu_kb()
    await message.answer("\n".join(lines), reply_markup=user_kb, parse_mode="HTML")
    await state.clear()


@dp.callback_query(F.data.startswith("take_"))
async def take_order_handler(callback: CallbackQuery):
    if not await is_worker(callback.from_user.id):
        await callback.answer(f"{Style.CROSS} Нет доступа")
        return

    order_id = int(callback.data.split("_", 1)[1])
    order = await get_order(order_id)

    if not order:
        await callback.answer(f"{Style.CROSS} Заявка не найдена")
        return

    if order[5] != "waiting":
        await callback.answer(f"{Style.WARNING} Уже занято")
        return

    service = order[2]
    worker_services = await get_worker_services(callback.from_user.id)
    if service not in worker_services:
        await callback.answer(f"{Style.CROSS} У вас нет доступа к сервису {service}")
        return

    # Check worker balance before taking order
    worker_id = callback.from_user.id
    worker_price = await get_worker_price(worker_id, service) or 0
    if worker_price > 0:
        worker_balance = await get_user_balance(worker_id)
        if worker_balance < worker_price:
            await callback.answer(
                f"{Style.CROSS} Недостаточно средств! Нужно: {worker_price} $, у вас: {worker_balance} $",
                show_alert=True,
            )
            return

    await take_order(order_id, worker_id)

    # Log order taken - исправлено: передаем username вместо label
    await log_order_taken(
        order_id, 
        worker_id, 
        callback.from_user.username,  # username вместо label
        await get_worker_price(worker_id, service)
    )

    code_request = await bot.send_message(
        order[1],
        f"{Style.SUCCESS} <b>Ваш номер взят в работу!</b>\n\n"
        f"{Style.CODE} Отправьте игровой код <b>ответом на это сообщение</b>.\n"
        f"{Style.WARNING} Только цифры. У вас 2 попытки.",
        reply_markup=worker_menu_kb() if await is_worker(order[1]) else main_menu_kb(),
        parse_mode="HTML",
    )
    await set_code_request_msg_id(order_id, code_request.message_id)

    number = order[3]
    service = order[2]
    await callback.message.edit_text(
        f"{Style.ORDER} <b>Заявка #{order_id}</b> взята в работу\n\n"
        f"{Style.SERVICES} Сервис: <code>{service}</code>\n"
        f"{Style.PHONE} Номер: <code>{number}</code>\n\n"
        f"{Style.CLOCK} Ожидайте код от пользователя...\n"
        f"{Style.WARNING} Автоотмена через 2 минуты.",
        reply_markup=worker_action_kb(order_id),
        parse_mode="HTML",
    )
    await set_worker_msg_id(order_id, callback.message.message_id)
    await callback.answer(f"{Style.CHECK} Заявка #{order_id} взята!")

    task = asyncio.create_task(auto_cancel_timer(order_id, order[1], worker_id))
    _active_timers.add(task)
    task.add_done_callback(_active_timers.discard)


@dp.message(not_admin, ~StateFilter(AdminState))
async def catch_all(message: Message, state: FSMContext):
    user_id = message.from_user.id

    # Check subscription for regular users
    if not await is_worker(user_id) and not admin_only(user_id):
        if not await is_subscribed(user_id):
            await send_subscription_request(message)
            return

    order = await get_user_active_order(user_id)

    if not order:
        if await is_worker(user_id):
            await message.answer(
                f"{Style.INFO} Нет такого варианта ответа",
                reply_markup=worker_menu_kb(),
            )
        else:
            await message.answer(
                f"{Style.INFO} Нет такого варианта ответа",
                reply_markup=main_menu_kb(),
            )
        return

    order_id = order[0]
    service = order[2]
    number = order[3]
    worker_id = order[6]
    code_count = order[7]
    code_request_msg_id = order[8]
    worker_msg_id = order[9]

    is_reply_to_code_request = (
        message.reply_to_message is not None
        and code_request_msg_id is not None
        and message.reply_to_message.message_id == code_request_msg_id
    )

    if not is_reply_to_code_request:
        try:
            await bot.send_message(
                worker_id,
                f"{Style.CHAT} <b>Комментарий пользователя по заявке #{order_id}:</b>\n"
                f"<code>{message.text}</code>",
                parse_mode="HTML",
            )
        except Exception:
            pass
        await message.answer(
            f"{Style.CHAT} Ваше сообщение передано скупу как комментарий.\n"
            f"{Style.CODE} Чтобы отправить код — ответьте на сообщение с просьбой кода."
        )
        return

    if code_count >= 2:
        await message.answer(
            f"{Style.CROSS} Вы уже отправили максимум 2 кода по этой заявке.\n"
            f"{Style.INFO} Дальнейшая отправка кодов невозможна."
        )
        return

    code = message.text.strip()
    if not CODE_RE.match(code):
        await message.answer(
            f"{Style.CROSS} Код должен содержать только цифры.\n"
            f"{Style.CODE} Отправьте ответ на сообщение с просьбой кода еще раз."
        )
        return

    await save_code(order_id, code)
    new_count = code_count + 1

    attempt_label = (
        f"{Style.DANGER} последняя попытка" if new_count >= 2 else f"{Style.INFO} попытка {new_count} из 2"
    )

    try:
        await bot.send_message(
            worker_id,
            f"{Style.CODE} <b>Код от пользователя</b>\n\n"
            f"{Style.ORDER} Заявка <b>#{order_id}</b>\n"
            f"{Style.SERVICES} Сервис: <code>{service}</code>\n"
            f"{Style.PHONE} Номер: <code>{number}</code>\n\n"
            f"{Style.CODE} Код: <code>{code}</code>\n"
            f"({attempt_label})",
            reply_markup=worker_action_kb(order_id),
            parse_mode="HTML",
        )
    except Exception:
        pass

    await message.answer(
        f"{Style.CHECK} Код отправлен. {Style.CLOCK} Ожидайте подтверждения.",
        parse_mode="HTML",
    )


async def auto_cancel_timer(order_id: int, user_id: int, worker_id: int):
    await asyncio.sleep(120)
    order = await get_order(order_id)
    if order and order[5] == "active":
        await reject_order(order_id)
        await log_order_completed(order_id, 'rejected')
        try:
            await bot.send_message(
                user_id,
                f"{Style.CLOCK} <b>Заявка автоматически отменена</b>\n\n"
                f"{Style.INFO} Скуп не успел принять код за 2 минуты.",
                parse_mode="HTML",
            )
        except Exception:
            pass
        try:
            await bot.send_message(
                worker_id,
                f"{Style.CLOCK} <b>Заявка #{order_id} автоматически отменена</b>\n"
                f"{Style.INFO} Истекло время (2 минуты).",
                parse_mode="HTML",
            )
        except Exception:
            pass


async def periodic_cleanup_task():
    """Background task: auto-cancel orders older than 24 hours every 30 minutes"""
    while True:
        await asyncio.sleep(1800)  # 30 minutes
        try:
            from db import cleanup_old_orders, log_order_completed
            rows = await cleanup_old_orders(hours=24)
            if rows:
                for oid, uid, wid, status in rows:
                    await log_order_completed(oid, 'rejected')
                    try:
                        await bot.send_message(
                            uid,
                            f"{Style.CROSS} <b>Заявка #{oid} автоматически отменена</b>\n\n"
                            f"{Style.INFO} Истекло 24 часа. Создайте новую заявку.",
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
                    if wid:
                        try:
                            await bot.send_message(
                                wid,
                                f"{Style.CROSS} <b>Заявка #{oid} отменена системой</b>\n"
                                f"{Style.INFO} Истекло 24 часа.",
                                parse_mode="HTML",
                            )
                        except Exception:
                            pass
                print(f"[AUTO-CLEANUP] Cancelled {len(rows)} old orders")
        except Exception as e:
            print(f"[AUTO-CLEANUP] Error: {e}")


@dp.callback_query(F.data.startswith("accept_"))
async def accept_handler(callback: CallbackQuery):
    if not await is_worker(callback.from_user.id):
        await callback.answer(f"{Style.CROSS} Нет доступа")
        return

    order_id = int(callback.data.split("_", 1)[1])
    order = await get_order(order_id)

    if not order:
        await callback.answer(f"{Style.CROSS} Заявка не найдена")
        return

    user_id = order[1]
    service = order[2]

    await accept_order(order_id)
    await log_order_completed(order_id, 'accepted', order[4])
    await increment_user_limit(user_id, 3)

    # Ensure user exists in database before adding balance
    await upsert_user(
        user_id, 
        callback.from_user.username,
        callback.from_user.first_name,
        callback.from_user.last_name
    )

    bonus = await get_service_price(service)
    worker_price = await get_worker_price(callback.from_user.id, service) or 0

    # Debug logging
    print(f"[DEBUG] Accept order #{order_id}: user={user_id}, service={service}, bonus={bonus}, worker_price={worker_price}")

    if bonus > 0:
        await add_user_balance(user_id, bonus)
        new_balance = await get_user_balance(user_id)
        print(f"[DEBUG] Added {bonus} $ to user {user_id}, new balance: {new_balance}")
    else:
        print(f"[DEBUG] Bonus is 0, not adding balance")
    if bonus != 0:
        sign = "+" if bonus > 0 else ""
        await bot.send_message(
            order[1],
            f"{Style.SUCCESS} <b>Ваш номер успешно принят!</b>\n"
            f"{Style.MONEY} Начислен бонус: <code>{sign}{bonus} $</code>\n"
            f"{Style.STAR} Лимит заявок увеличен на +3!",
            parse_mode="HTML",
        )
    else:
        await bot.send_message(
            order[1],
            f"{Style.SUCCESS} <b>Ваш номер успешно принят!</b>\n"
            f"{Style.STAR} Лимит заявок увеличен на +3!",
            parse_mode="HTML",
        )
    if worker_price != 0:
        await add_user_balance(callback.from_user.id, -worker_price)
    try:
        await bot.send_message(
            callback.from_user.id,
            f"{Style.BALANCE} Баланс по заявке <b>#{order_id}</b> обновлен.\n"
            f"{Style.MONEY} Списано: <code>{worker_price} $</code>",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await callback.message.edit_text(
        f"{Style.SUCCESS} Заявка <b>#{order_id}</b> подтверждена",
        parse_mode="HTML",
    )
    await callback.answer(f"{Style.CHECK} Принято!")


@dp.callback_query(F.data.startswith("reject_"))
async def reject_handler(callback: CallbackQuery):
    if not await is_worker(callback.from_user.id):
        await callback.answer(f"{Style.CROSS} Нет доступа")
        return

    order_id = int(callback.data.split("_", 1)[1])
    order = await get_order(order_id)

    if not order:
        await callback.answer(f"{Style.CROSS} Заявка не найдена")
        return

    if order[5] != "active":
        await callback.answer(f"{Style.WARNING} Заявка уже не активна")
        return

    reject_count = await increment_reject_count(order_id)
    user_id = order[1]
    number = order[3]
    service = order[2]

    if reject_count >= 2:
        await reject_order(order_id)
        await log_order_completed(order_id, 'rejected')
        await bot.send_message(
            user_id,
            f"{Style.CROSS} <b>Заявка отменена</b>\n\n"
            f"{Style.INFO} Исчерпаны все попытки отправки кода.",
            parse_mode="HTML",
        )
        await callback.message.edit_text(
            f"{Style.CROSS} Заявка <b>#{order_id}</b> отменена — попытки исчерпаны",
            parse_mode="HTML",
        )
    else:
        user_kb = worker_menu_kb() if await is_worker(user_id) else main_menu_kb()
        code_request = await bot.send_message(
            user_id,
            f"{Style.WARNING} <b>Код не подошел</b>\n\n"
            f"{Style.REFRESH} Скуп запросил повтор кода.\n\n"
            f"{Style.DANGER} Осталась <b>последняя попытка</b>.\n"
            f"{Style.CODE} Отправьте новый код <b>ответом на это сообщение</b>.",
            reply_markup=user_kb,
            parse_mode="HTML",
        )
        await set_code_request_msg_id(order_id, code_request.message_id)
        await callback.message.edit_text(
            f"{Style.ORDER} <b>Заявка #{order_id}</b>\n\n"
            f"{Style.SERVICES} Сервис: <code>{service}</code>\n"
            f"{Style.PHONE} Номер: <code>{number}</code>\n\n"
            f"{Style.REFRESH} Повтор запрошен. {Style.CLOCK} Ожидайте новый код\n"
            f"{Style.DANGER} (осталась 1 попытка)",
            reply_markup=worker_action_kb(order_id),
            parse_mode="HTML",
        )

    await callback.answer()


async def main():
    await init_db(seed_worker_ids=WORKERS)

    # Start background auto-cleanup task
    asyncio.create_task(periodic_cleanup_task())

    port = int(os.environ.get("PORT", 8080))

    from aiohttp import web

    async def health(_request):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_get("/bot", health)
    app.router.add_get("/bot/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
