from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

import json

import config
from states import AdminState
from ai_assistant import ai_assistant
from db import (
    get_all_workers,
    get_worker_services,
    set_worker_services,
    get_user_id_by_username,
    get_username_by_id,
    get_user_display_name,
    get_all_users,
    delete_user,
    is_worker,
    add_worker,
    remove_worker,
    get_orders_by_number,
    get_all_service_prices,
    set_service_price,
    get_queue_count,
    get_all_services,
    get_main_services,
    get_other_services,
    get_service_category,
    set_service_category,
    add_service,
    remove_service,
    get_worker_prices,
    set_worker_price,
    get_user_balance,
    add_user_balance,
    set_user_balance,
    get_pending_withdrawals,
    get_all_withdrawals,
    mark_withdrawal_paid,
    get_withdrawal,
    remove_all_services,
    get_order_logs,
    get_order_log_stats,
    get_order_log_by_id,
    cancel_order,
    cleanup_old_orders,
    get_old_orders,
    log_order_completed,
)

router = Router()


class Style:
    PRIMARY   = chr(128308)
    SUCCESS   = chr(128994)
    DANGER    = chr(128308)
    WARNING   = chr(128993)
    INFO      = chr(128311)
    MONEY     = chr(128176)
    USER      = chr(128100)
    WORKER    = chr(128119)
    ADMIN     = chr(128081)
    PHONE     = chr(128241)
    CODE      = chr(128273)
    ORDER     = chr(128203)
    QUEUE     = chr(128202)
    BACK      = chr(9664) + chr(65039)
    HOME      = chr(127968)
    SUPPORT   = chr(127384)
    PROFILE   = chr(128100)
    WITHDRAW  = chr(128184)
    ACTIVE    = chr(128203)
    HISTORY   = chr(128344)
    SETTINGS  = chr(9881) + chr(65039)
    ADD       = chr(10133)
    REMOVE    = chr(128465) + chr(65039)
    EDIT      = chr(9999) + chr(65039)
    SEARCH    = chr(128269)
    BONUS     = chr(127873)
    PRICE     = chr(127991) + chr(65039)
    BALANCE   = chr(128179)
    SERVICES  = chr(129513)
    STATS     = chr(128200)
    STAR      = chr(11088)
    ARROW_R   = chr(9654) + chr(65039)
    ARROW_L   = chr(9664) + chr(65039)
    CHECK     = chr(9989)
    CROSS     = chr(10060)
    REFRESH   = chr(128260)
    BELL      = chr(128276)
    CLOCK     = chr(9200)
    CHAT      = chr(128172)
    DOC       = chr(128196)
    PIN       = chr(128204)
    FIRE      = chr(128293)
    CROWN     = chr(128081)
    GEM       = chr(128142)
    PANEL     = chr(128736) + chr(65039)
    DEALS     = chr(128177)
    TAG       = chr(127991) + chr(65039)
    CHART     = chr(128202)
    PUZZLE    = chr(129513)
    WALLET    = chr(128091)


STATUS_LABELS = {
    "waiting":  f"{Style.CLOCK} Ожидает",
    "active":   f"{Style.REFRESH} В работе",
    "accepted": f"{Style.SUCCESS} Принята",
    "rejected": f"{Style.DANGER} Отклонена",
}


def admin_only(user_id: int) -> bool:
    return user_id in config.ADMINS


def main_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{Style.WORKER} Скупы", callback_data="admin_workers")],
            [InlineKeyboardButton(text=f"{Style.USER} Пользователи", callback_data="admin_users")],
            [InlineKeyboardButton(text=f"{Style.SEARCH} Сделки по номеру", callback_data="admin_deals")],
            [InlineKeyboardButton(text=f"{Style.BONUS} Бонусы", callback_data="admin_bonuses")],
            [InlineKeyboardButton(text=f"{Style.QUEUE} Очередь", callback_data="admin_queue")],
            [InlineKeyboardButton(text=f"{Style.PUZZLE} Сервисы", callback_data="admin_services")],
            [InlineKeyboardButton(text=f"{Style.PRICE} Цены скупов", callback_data="admin_worker_prices")],
            [InlineKeyboardButton(text=f"{Style.BALANCE} Баланс скупов", callback_data="admin_worker_balance")],
            [InlineKeyboardButton(text=f"{Style.WITHDRAW} Заявки на выплаты", callback_data="admin_withdrawals")],
            [InlineKeyboardButton(text=f"{Style.DOC} Логи заявок", callback_data="admin_logs")],
            [InlineKeyboardButton(text=f"{Style.REMOVE} Очистка старых заявок", callback_data="admin_cleanup")],
        ]
    )


def back_to_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="admin_panel")]
        ]
    )


async def bonus_prices_kb() -> InlineKeyboardMarkup:
    prices = await get_all_service_prices()
    all_services = await get_all_services()
    rows = []
    for service in all_services:
        price = prices.get(service, 0)
        rows.append([InlineKeyboardButton(
            text=f"{Style.PRICE} {service}: {price} $",
            callback_data=f"setprice_{service}"
        )])
    rows.append([InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def services_kb() -> InlineKeyboardMarkup:
    rows = []
    main_svcs = await get_main_services()
    main_set = set(main_svcs)
    for service in await get_all_services():
        cat_icon = f"{Style.STAR}" if service in main_set else f"{Style.INFO}"
        rows.append([InlineKeyboardButton(text=f"{cat_icon} {service}", callback_data=f"admsrv_{service}")])
    rows.append([
        InlineKeyboardButton(text=f"{Style.ADD} Добавить", callback_data="admin_add_service"),
        InlineKeyboardButton(text=f"{Style.REMOVE} Удалить все", callback_data="admin_remove_all_services"),
    ])
    rows.append([InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def worker_prices_kb() -> InlineKeyboardMarkup:
    rows = []
    for wid in await get_all_workers():
        username = await get_username_by_id(wid)
        if username:
            if " " in username:
                label = username
            else:
                label = f"@{username}"
        else:
            label = f"ID: {wid}"
        rows.append([InlineKeyboardButton(text=f"{Style.WORKER} {label}", callback_data=f"workerprice_{wid}")])
    rows.append([InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def workers_keyboard() -> InlineKeyboardMarkup:
    workers = await get_all_workers()
    rows = []
    for wid in workers:
        label = await get_user_display_name(wid)
        services = await get_worker_services(wid)
        services_str = ", ".join(services) if services else "без сервисов"
        rows.append([
            InlineKeyboardButton(
                text=f"{Style.WORKER} {label} — {services_str}",
                callback_data=f"winfo_{wid}"
            )
        ])
    rows.append([InlineKeyboardButton(text=f"{Style.ADD} Добавить скупа", callback_data="admin_add_worker")])
    rows.append([InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if not admin_only(message.from_user.id):
        return
    await state.clear()
    await message.answer(
        f"{Style.PANEL} <b>Панель администратора</b>",
        reply_markup=main_panel_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_panel")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text(
        f"{Style.PANEL} <b>Панель администратора</b>",
        reply_markup=main_panel_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_workers")
async def show_workers(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await state.clear()
    kb = await workers_keyboard()
    await callback.message.edit_text(
        f"{Style.WORKER} <b>Скупы:</b>",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("winfo_"))
async def worker_info(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        return
    worker_id = int(callback.data.split("_", 1)[1])
    label = await get_user_display_name(worker_id)
    services = await get_worker_services(worker_id)
    services_str = ", ".join(services) if services else "не назначены"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{Style.SETTINGS} Изменить сервисы", callback_data=f"wsetservices_{worker_id}")],
            [InlineKeyboardButton(text=f"{Style.PRICE} Цены скупа", callback_data=f"wprices_{worker_id}")],
            [InlineKeyboardButton(text=f"{Style.REMOVE} Удалить скупа", callback_data=f"wremove_{worker_id}")],
            [InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="admin_workers")],
        ]
    )
    text = f"{Style.WORKER} <b>Скуп:</b> <code>{label}</code>\n" + \
           f"{Style.INFO} ID: <code>{worker_id}</code>\n" + \
           f"{Style.SERVICES} Сервисы: <code>{services_str}</code>"
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")



@router.callback_query(F.data.startswith("logcancel_"))
async def log_cancel_handler(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    try:
        order_id = int(callback.data.split("_", 1)[1])
        order = await get_order(order_id)
        if not order:
            await callback.answer(f"{Style.CROSS} Заявка не найдена")
            return
        if order[5] not in ('waiting', 'active'):
            await callback.answer(f"{Style.WARNING} Заявка уже завершена")
            return

        await cancel_order(order_id)
        await log_order_completed(order_id, 'rejected')

        # Notify user
        user_id = order[1]
        try:
            await bot.send_message(
                user_id,
                f"{Style.CROSS} <b>Заявка #{order_id} отменена администратором</b>\n\n"
                f"{Style.INFO} Обратитесь в поддержку для уточнения.",
                parse_mode="HTML",
            )
        except Exception:
            pass

        # Notify worker if assigned
        worker_id = order[6]
        if worker_id:
            try:
                await bot.send_message(
                    worker_id,
                    f"{Style.CROSS} <b>Заявка #{order_id} отменена администратором</b>",
                    parse_mode="HTML",
                )
            except Exception:
                pass

        await callback.answer(f"{Style.CHECK} Заявка #{order_id} отменена")
        # Refresh log detail
        await log_detail(callback, state)
    except Exception as e:
        await callback.answer(f"{Style.CROSS} Ошибка: {str(e)[:100]}", show_alert=True)

@router.callback_query(F.data.startswith("wprices_"))
async def worker_prices_info(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        return
    worker_id = int(callback.data.split("_", 1)[1])
    label = await get_user_display_name(worker_id)
    prices = await get_worker_prices(worker_id)
    services = await get_worker_services(worker_id)
    lines = [f"{Style.PRICE} <b>Цены скупа:</b> <code>{label}</code>", ""]
    if services:
        for service in services:
            price = prices.get(service, 0)
            lines.append(f"  {Style.PRICE} {service}: <code>{price} $</code>")
    else:
        lines.append(f"{Style.WARNING} Скупу пока не назначены сервисы.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Style.EDIT} Изменить цену", callback_data=f"workerprice_{worker_id}")],
        [InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data=f"winfo_{worker_id}")],
    ])
    await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("wremove_"))
async def remove_worker_cb(callback: CallbackQuery, bot: Bot):
    if not admin_only(callback.from_user.id):
        return
    worker_id = int(callback.data.split("_", 1)[1])
    label = await get_user_display_name(worker_id)
    await remove_worker(worker_id)
    try:
        await bot.send_message(worker_id, f"{Style.CROSS} Вы удалены из списка скупов.")
    except Exception:
        pass
    kb = await workers_keyboard()
    text = f"{Style.CROSS} <code>{label}</code> удалён из скупов.\n\n" + \
           f"{Style.WORKER} <b>Скупы:</b>"
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("wsetservices_"))
async def set_services_start(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    worker_id = int(callback.data.split("_", 1)[1])
    label = await get_user_display_name(worker_id)
    current = await get_worker_services(worker_id)
    current_str = ", ".join(current) if current else "не назначены"
    await state.set_state(AdminState.removing_worker_services)
    await state.update_data(target_worker_id=worker_id)
    all_services = await get_all_services()
    text = f"{Style.SETTINGS} <b>Сервисы для {label}</b>\n" + \
           f"{Style.INFO} Текущие: <code>{current_str}</code>\n\n" + \
           f"{Style.DOC} Введите сервисы через запятую:\n" + \
           f"{Style.INFO} Доступные: <code>{', '.join(all_services)}</code>\n\n" + \
           f"{Style.INFO} Пример: VK,TG"
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{Style.BACK} Отмена", callback_data=f"winfo_{worker_id}")]
        ]),
        parse_mode="HTML",
    )


@router.message(AdminState.removing_worker_services)
async def set_services_input(message: Message, state: FSMContext, bot: Bot):
    if not admin_only(message.from_user.id):
        return
    data = await state.get_data()
    worker_id = data["target_worker_id"]
    label = await get_user_display_name(worker_id)
    all_services = await get_all_services()
    raw = [s.strip() for s in message.text.split(",")]
    valid = [s for s in raw if s in all_services]
    invalid = [s for s in raw if s not in all_services]
    if not valid:
        await message.answer(
            f"{Style.CROSS} Ни один сервис не распознан.\n"
            f"{Style.INFO} Доступные: <code>{', '.join(all_services)}</code>"
        )
        return
    await set_worker_services(worker_id, valid)
    await state.clear()
    try:
        await bot.send_message(worker_id, f"{Style.BELL} Вам назначены сервисы: <code>{', '.join(valid)}</code>", parse_mode="HTML")
    except Exception:
        pass
    msg = f"{Style.CHECK} <code>{label}</code> — сервисы обновлены: <code>{', '.join(valid)}</code>"
    if invalid:
        msg += f"\n{Style.WARNING} Не распознаны: <code>{', '.join(invalid)}</code>"
    kb = await workers_keyboard()
    await message.answer(msg + "\n\n" + f"{Style.WORKER} <b>Скупы:</b>", reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "admin_add_worker")
async def add_worker_start(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await state.set_state(AdminState.adding_worker)
    text = f"{Style.ADD} <b>Добавление скупа</b>\n\n" + \
           f"{Style.DOC} Введите @username скупа:\n" + \
           f"{Style.WARNING} Пользователь должен сначала написать /start боту."
    await callback.message.edit_text(
        text,
        reply_markup=back_to_panel_kb(),
        parse_mode="HTML",
    )


@router.message(AdminState.adding_worker)
async def add_worker_input(message: Message, state: FSMContext, bot: Bot):
    if not admin_only(message.from_user.id):
        return
    username = message.text.strip()
    worker_id = await get_user_id_by_username(username)
    if not worker_id:
        await message.answer(
            f"{Style.CROSS} Пользователь <code>{username}</code> не найден.\n"
            f"{Style.INFO} Попросите его написать /start боту, затем попробуйте снова.",
            reply_markup=back_to_panel_kb(),
            parse_mode="HTML",
        )
        return
    if await is_worker(worker_id):
        await message.answer(f"{Style.WARNING} <code>{username}</code> уже является скупом.")
        await state.clear()
        kb = await workers_keyboard()
        await message.answer(f"{Style.WORKER} <b>Скупы:</b>", reply_markup=kb, parse_mode="HTML")
        return
    await add_worker(worker_id)
    await state.clear()
    try:
        await bot.send_message(worker_id, f"{Style.WORKER} Вы назначены скупом. Напишите /start чтобы начать работу.")
    except Exception:
        pass
    kb = await workers_keyboard()
    await message.answer(
        f"{Style.CHECK} <code>{username}</code> добавлен как скуп.\n\n"
        f"{Style.WORKER} <b>Скупы:</b>",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_users")
async def show_users(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await state.clear()
    all_users = await get_all_users()
    total = len(all_users)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Style.REMOVE} Удалить пользователя", callback_data="admin_delete_user")],
        [InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="admin_panel")],
    ])
    await callback.message.edit_text(
        f"{Style.USER} <b>Пользователи</b>\n\n"
        f"{Style.INFO} Всего в базе: <b>{total}</b> чел.",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_delete_user")
async def delete_user_start(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await state.set_state(AdminState.deleting_user)
    await callback.message.edit_text(
        f"{Style.REMOVE} <b>Удаление пользователя</b>\n\n"
        f"{Style.DOC} Введите @username пользователя:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{Style.BACK} Отмена", callback_data="admin_users")]
        ]),
        parse_mode="HTML",
    )


@router.message(AdminState.deleting_user)
async def delete_user_input(message: Message, state: FSMContext):
    if not admin_only(message.from_user.id):
        return
    username = message.text.strip()
    user_id = await get_user_id_by_username(username)
    if not user_id:
        await message.answer(
            f"{Style.CROSS} Пользователь <code>{username}</code> не найден в базе.",
            reply_markup=back_to_panel_kb(),
            parse_mode="HTML",
        )
        return
    if await is_worker(user_id):
        await message.answer(
            f"{Style.WARNING} <code>{username}</code> является скупом.\n"
            f"{Style.INFO} Сначала удалите его из скупов через раздел {Style.WORKER} Скупы.",
            reply_markup=back_to_panel_kb(),
            parse_mode="HTML",
        )
        await state.clear()
        return
    await delete_user(user_id)
    await state.clear()
    all_users = await get_all_users()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Style.REMOVE} Удалить пользователя", callback_data="admin_delete_user")],
        [InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="admin_panel")],
    ])
    await message.answer(
        f"{Style.CHECK} Пользователь <code>{username}</code> удалён из базы.\n\n"
        f"{Style.USER} <b>Пользователи</b>\n"
        f"{Style.INFO} Всего в базе: <b>{len(all_users)}</b> чел.",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_bonuses")
async def show_bonuses(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await state.clear()
    kb = await bonus_prices_kb()
    await callback.message.edit_text(
        f"{Style.BONUS} <b>Бонусы / цены по сервисам:</b>",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("setprice_"))
async def set_price_start(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    service = callback.data[9:]
    await state.update_data(target_service=service)
    await state.set_state(AdminState.setting_price)
    await callback.message.edit_text(
        f"{Style.MONEY} <b>Введите новую цену для сервиса {service}</b> (для пользователей):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{Style.BACK} Отмена", callback_data="admin_bonuses")]
        ]),
    )
    await callback.answer()


@router.message(AdminState.setting_price)
async def set_price_input(message: Message, state: FSMContext):
    if not admin_only(message.from_user.id):
        return
    data = await state.get_data()
    service = data.get("target_service", "")
    try:
        price = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer(
            f"{Style.CROSS} Введите число (например: 50 или 1.5)",
            parse_mode="HTML",
        )
        return
    await set_service_price(service, price)
    await state.clear()
    kb = await bonus_prices_kb()
    await message.answer(
        f"{Style.CHECK} Цена для <code>{service}</code> установлена: <code>{price} $</code>\n\n"
        f"{Style.BONUS} <b>Бонусы / цены:</b>",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_worker_prices")
async def show_worker_prices(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await state.clear()
    kb = await worker_prices_kb()
    await callback.message.edit_text(
        f"{Style.PRICE} <b>Выберите скупа для цены:</b>",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_worker_balance")
async def show_worker_balance(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await state.clear()
    rows = []
    for wid in await get_all_workers():
        label = await get_user_display_name(wid)
        balance = await get_user_balance(wid)
        rows.append([InlineKeyboardButton(
            text=f"{Style.WORKER} {label}: {balance} $",
            callback_data=f"workerbal_{wid}"
        )])
    rows.append([InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="admin_panel")])
    await callback.message.edit_text(
        f"{Style.BALANCE} <b>Баланс скупов:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("workerbal_"))
async def worker_balance_start(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    worker_id = int(callback.data.split("_", 1)[1])
    await state.update_data(target_worker_id=worker_id)
    await state.set_state(AdminState.topping_up_worker_balance)
    await callback.message.edit_text(
        f"{Style.MONEY} <b>Введите сумму пополнения баланса скупа</b> (например 50):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminState.topping_up_worker_balance)
async def worker_balance_input(message: Message, state: FSMContext):
    if not admin_only(message.from_user.id):
        return
    data = await state.get_data()
    worker_id = data.get("target_worker_id")
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            f"{Style.CROSS} Введите целое число больше 0",
            parse_mode="HTML",
        )
        return
    await add_user_balance(worker_id, amount)
    balance = await get_user_balance(worker_id)
    await state.clear()
    await message.answer(
        f"{Style.CHECK} Баланс скупа пополнен.\n"
        f"{Style.MONEY} Теперь: <code>{balance} $</code>",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_withdrawals")
async def show_withdrawals(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await state.clear()
    rows = await get_all_withdrawals()
    if not rows:
        await callback.message.edit_text(
            f"{Style.WITHDRAW} <b>Заявки на выплаты</b>\n\n"
            f"{Style.INFO} Пока заявок нет.",
            reply_markup=main_panel_kb(),
            parse_mode="HTML",
        )
        await callback.answer()
        return
    lines = [f"{Style.WITHDRAW} <b>Заявки на выплаты:</b>\n"]
    kb_rows = []
    for wid, user_id, amount, details, status in rows:
        user_label = await get_user_display_name(user_id)
        status_text = f"{Style.SUCCESS} ОПЛАЧЕНА" if status == 'paid' else f"{Style.CLOCK} НЕ ОПЛАЧЕНА"
        lines.append(f"#{wid} | {user_label} | {amount} $ | {status_text}")
        kb_rows.append([InlineKeyboardButton(
            text=f"#{wid} | {status_text}",
            callback_data=f"wddtl_{wid}"
        )])
    kb_rows.append([InlineKeyboardButton(text=f"{Style.REFRESH} Обновить", callback_data="admin_withdrawals")])
    kb_rows.append([InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="admin_panel")])
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wddtl_"))
async def withdrawal_detail(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    withdrawal_id = int(callback.data.split("_", 1)[1])
    row = await get_withdrawal(withdrawal_id)
    if not row:
        await callback.answer(f"{Style.CROSS} Заявка не найдена")
        return
    wid, user_id, amount, details, status = row
    user_label = await get_user_display_name(user_id)
    status_text = f"{Style.SUCCESS} ОПЛАЧЕНА" if status == 'paid' else f"{Style.CLOCK} НЕ ОПЛАЧЕНА"
    text = (
        f"{Style.WITHDRAW} <b>Заявка #{wid}</b>\n\n"
        f"{Style.USER} Пользователь: <code>{user_label}</code>\n"
        f"{Style.MONEY} Сумма: <code>{amount} $</code>\n"
        f"{Style.DOC} Реквизиты: <code>{details}</code>\n"
        f"{Style.INFO} Статус: {status_text}"
    )
    kb = []
    if status != 'paid':
        kb.append([InlineKeyboardButton(
            text=f"{Style.CHECK} Отметить оплаченной",
            callback_data=f"wdpaid_{wid}"
        )])
    kb.append([InlineKeyboardButton(
        text=f"{Style.BACK} Назад к списку",
        callback_data="admin_withdrawals"
    )])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("wdpaid_"))
async def mark_withdrawal_paid_handler(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    withdrawal_id = int(callback.data.split("_", 1)[1])
    row = await get_withdrawal(withdrawal_id)
    if not row:
        await callback.answer(f"{Style.CROSS} Заявка не найдена")
        return
    if row[4] == 'paid':
        await callback.answer(f"{Style.CHECK} Эта заявка уже оплачена")
        return
    await mark_withdrawal_paid(withdrawal_id)
    await callback.answer(f"{Style.CHECK} Заявка #{withdrawal_id} отмечена оплаченной")
    await withdrawal_detail(callback, state)


@router.callback_query(F.data.startswith("workerprice_"))
async def worker_price_start(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    worker_id = int(callback.data.split("_", 1)[1])
    await state.update_data(target_worker_id=worker_id)
    await state.set_state(AdminState.setting_worker_price)
    services = await get_worker_services(worker_id)
    all_services = await get_all_services()
    text = f"{Style.PRICE} <b>Введите цену скупа по формату:</b> сервис цена\n" + \
           f"{Style.INFO} Пример: VK 120\n" + \
           f"{Style.INFO} Доступные сервисы: <code>{', '.join(services) if services else ', '.join(all_services)}</code>"
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{Style.BACK} Отмена", callback_data="admin_worker_prices")]
        ]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminState.setting_worker_price)
async def worker_price_input(message: Message, state: FSMContext):
    if not admin_only(message.from_user.id):
        return
    data = await state.get_data()
    worker_id = data.get("target_worker_id")
    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer(
            f"{Style.CROSS} Формат: сервис цена. Пример: VK 120",
            parse_mode="HTML",
        )
        return
    service, price_raw = parts
    try:
        price = float(price_raw.replace(",", "."))
    except ValueError:
        await message.answer(
            f"{Style.CROSS} Цена должна быть числом (например: 120 или 1.5)",
            parse_mode="HTML",
        )
        return
    await set_worker_price(worker_id, service, price)
    await state.clear()
    kb = await worker_prices_kb()
    await message.answer(
        f"{Style.CHECK} Цена для скупа <code>{worker_id}</code> по сервису <code>{service}</code>: <code>{price} $</code>",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_queue")
async def show_queue(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await state.clear()
    lines = [f"{Style.QUEUE} <b>Очередь номеров по сервисам:</b>\n"]
    all_services = await get_all_services()
    for service in all_services:
        count = await get_queue_count(service)
        lines.append(f"  {Style.PHONE} {service}: <b>{count}</b> номеров")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="admin_panel")]
    ])
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_deals")
async def deals_section(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await state.set_state(AdminState.searching_orders)
    text = f"{Style.SEARCH} <b>Поиск сделок по номеру</b>\n\n" + \
           f"{Style.DOC} Введите номер телефона:\n" + \
           f"{Style.INFO} Формат: +79121231212 или 79121231212"
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="admin_panel")]
        ]),
        parse_mode="HTML",
    )


@router.message(AdminState.searching_orders)
async def search_orders_input(message: Message, state: FSMContext):
    if not admin_only(message.from_user.id):
        return
    number = message.text.strip()
    orders = await get_orders_by_number(number)
    await state.clear()
    if not orders:
        await message.answer(
            f"{Style.INFO} По номеру <code>{number}</code> сделок не найдено.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"{Style.SEARCH} Новый поиск", callback_data="admin_deals")],
                [InlineKeyboardButton(text=f"{Style.BACK} Панель", callback_data="admin_panel")],
            ]),
            parse_mode="HTML",
        )
        return
    lines = [f"{Style.SEARCH} <b>Сделки по номеру {number}:</b>\n"]
    for order in orders:
        oid, user_id, service, num, code, status, worker_id = order
        worker_name = None
        if worker_id:
            worker_name = await get_username_by_id(worker_id)
        worker_str = f"@{worker_name}" if worker_name else (str(worker_id) if worker_id else "—")
        status_label = STATUS_LABELS.get(status, status)
        code_str = code if code else "—"
        lines.append(
            f"━━━━━━━━━━━━\n"
            f"{Style.ORDER} <b>Заявка #{oid}</b>\n"
            f"{Style.PHONE} Сервис: <code>{service}</code>\n"
            f"{Style.USER} Пользователь: <code>{user_id}</code>\n"
            f"{Style.WORKER} Скуп: <code>{worker_str}</code>\n"
            f"{Style.CODE} Код: <code>{code_str}</code>\n"
            f"{Style.INFO} Статус: {status_label}"
        )
    await message.answer(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{Style.SEARCH} Новый поиск", callback_data="admin_deals")],
            [InlineKeyboardButton(text=f"{Style.BACK} Панель", callback_data="admin_panel")],
        ]),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_services")
async def show_services(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await state.clear()
    kb = await services_kb()
    all_svcs = await get_all_services()
    main_count = len(await get_main_services())
    other_count = len(all_svcs) - main_count
    text = f"{Style.PUZZLE} <b>Сервисы:</b> <b>{len(all_svcs)}</b> шт.\n" + \
           f"  {Style.STAR} Основные: <b>{main_count}</b>\n" + \
           f"  {Style.INFO} Другие: <b>{other_count}</b>\n\n" + \
           f"{Style.STAR} — основной  |  {Style.INFO} — другие\n" + \
           f"{Style.INFO} Нажмите на сервис, чтобы изменить категорию или удалить."
    await callback.message.edit_text(
        text,
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_service")
async def add_service_start(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await state.set_state(AdminState.adding_service)
    await callback.message.edit_text(
        f"{Style.ADD} <b>Добавление сервиса</b>\n\n"
        f"{Style.DOC} Введите название нового сервиса:",
        reply_markup=back_to_panel_kb(),
        parse_mode="HTML",
    )


@router.message(AdminState.adding_service)
async def add_service_input(message: Message, state: FSMContext):
    if not admin_only(message.from_user.id):
        return
    service = message.text.strip()
    if not service:
        await message.answer(f"{Style.CROSS} Пустое название", parse_mode="HTML")
        return
    if service.isdigit():
        await message.answer(f"{Style.CROSS} Название сервиса не может быть только числом", parse_mode="HTML")
        return
    if service.startswith("_"):
        await message.answer(f"{Style.CROSS} Недопустимое название", parse_mode="HTML")
        return
    await add_service(service)
    await state.clear()
    kb = await services_kb()
    await message.answer(
        f"{Style.CHECK} Сервис добавлен: <code>{service}</code>",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("admsrv_"))
async def service_manage(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    service = callback.data[len("admsrv_"):]
    cat = await get_service_category(service)
    cat_label = f"{Style.STAR} Основной" if cat == 'main' else f"{Style.INFO} Другие"
    toggle_text = f"{Style.ARROW_L} Перенести в другие" if cat == 'main' else f"{Style.ARROW_R} Перенести в основные"
    toggle_data = f"srvoth_{service}" if cat == 'main' else f"srvmain_{service}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=toggle_data)],
        [InlineKeyboardButton(text=f"{Style.MONEY} Установить цену", callback_data=f"setprice_{service}")],
        [InlineKeyboardButton(text=f"{Style.REMOVE} Удалить сервис", callback_data=f"srvrm_{service}")],
        [InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="admin_services")],
    ])
    await callback.message.edit_text(
        f"{Style.PUZZLE} <b>Сервис:</b> <code>{service}</code>\n"
        f"{Style.INFO} Категория: {cat_label}",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("srvmain_"))
async def service_set_main(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        return
    service = callback.data[len("srvmain_"):]
    await set_service_category(service, 'main')
    await callback.answer(f"{service} → Основной список")
    await service_manage(callback, None)


@router.callback_query(F.data.startswith("srvoth_"))
async def service_set_other(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        return
    service = callback.data[len("srvoth_"):]
    await set_service_category(service, 'other')
    await callback.answer(f"{service} → Другие сервисы")
    await service_manage(callback, None)


@router.callback_query(F.data.startswith("srvrm_"))
async def service_remove_start(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    service = callback.data[len("srvrm_"):]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Style.CHECK} Подтвердить удаление", callback_data=f"srvrmc_{service}")],
        [InlineKeyboardButton(text=f"{Style.BACK} Отмена", callback_data="admin_services")],
    ])
    await callback.message.edit_text(
        f"{Style.REMOVE} Удалить сервис <code>{service}</code>?",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("srvrmc_"))
async def service_remove_confirm(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    service = callback.data[len("srvrmc_"):]
    await remove_service(service)
    kb = await services_kb()
    await callback.message.edit_text(
        f"{Style.CHECK} Сервис удалён: <code>{service}</code>",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_remove_all_services")
async def remove_all_services_start(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Style.DANGER} Да, удалить всё", callback_data="admin_remove_all_services_confirm")],
        [InlineKeyboardButton(text=f"{Style.BACK} Отмена", callback_data="admin_services")],
    ])
    await callback.message.edit_text(
        f"{Style.WARNING} <b>Удалить все сервисы и связанные данные?</b>",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_remove_all_services_confirm")
async def remove_all_services_confirm(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await remove_all_services()
    await state.clear()
    await callback.message.edit_text(
        f"{Style.CHECK} <b>Все сервисы удалены.</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="admin_panel")]
        ]),
        parse_mode="HTML",
    )
    await callback.answer()






@router.callback_query(F.data == "admin_cleanup")
async def show_cleanup(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await state.clear()
    try:
        old_orders = await get_old_orders(hours=24)
        count = len(old_orders)

        lines = [
            f"{Style.REMOVE} <b>Очистка старых заявок</b>",
            f"",
            f"{Style.INFO} Заявки висят более 24 часов автоматически отменяются.",
            f"",
            f"{Style.WARNING} Сейчас найдено: <b>{count}</b> старых заявок",
            f"",
        ]

        if old_orders:
            lines.append(f"{Style.DOC} <b>Список:</b>")
            for oid, uid, svc, num, status, created in old_orders[:10]:
                user_label = await get_user_display_name(uid)
                status_icon = Style.CLOCK if status == 'waiting' else Style.REFRESH
                lines.append(f"  #{oid} | {svc} | {user_label} | {status_icon}")
            if len(old_orders) > 10:
                lines.append(f"  ... и ещё {len(old_orders) - 10}")

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{Style.DANGER} Отменить {count} заявок" if count else f"{Style.CHECK} Нечего очищать",
                callback_data="admin_cleanup_confirm" if count else "admin_panel"
            )],
            [InlineKeyboardButton(text=f"{Style.REFRESH} Обновить", callback_data="admin_cleanup")],
            [InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="admin_panel")],
        ])

        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=kb,
            parse_mode="HTML",
        )
        await callback.answer()
    except Exception as e:
        await callback.answer(f"{Style.CROSS} Ошибка: {str(e)[:100]}", show_alert=True)


@router.callback_query(F.data == "admin_cleanup_confirm")
async def confirm_cleanup(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    try:
        rows = await cleanup_old_orders(hours=24)
        count = len(rows)

        # Log and notify users/workers
        for oid, uid, wid, status in rows:
            await log_order_completed(oid, 'rejected')
            try:
                await bot.send_message(
                    uid,
                    f"{Style.CROSS} <b>Заявка #{oid} автоматически отменена</b>\n\n"
                    f"{Style.INFO} Истекло время (24 часа). Создайте новую заявку.",
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

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{Style.REFRESH} Обновить", callback_data="admin_cleanup")],
            [InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="admin_panel")],
        ])

        await callback.message.edit_text(
            f"{Style.CHECK} <b>Очистка завершена</b>\n\n"
            f"{Style.REMOVE} Отменено заявок: <b>{count}</b>",
            reply_markup=kb,
            parse_mode="HTML",
        )
        await callback.answer(f"{Style.CHECK} Отменено {count} заявок")
    except Exception as e:
        await callback.answer(f"{Style.CROSS} Ошибка: {str(e)[:100]}", show_alert=True)

@router.callback_query(F.data == "admin_logs")
async def show_logs(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await state.clear()
    try:
        stats = await get_order_log_stats(days=5)
        rows = await get_order_logs(days=5, limit=20)

        lines = [
            f"{Style.DOC} <b>Логи заявок (последние 5 дней)</b>",
            f"",
            f"{Style.STATS} <b>Статистика:</b>",
            f"  {Style.ORDER} Всего: <b>{stats['total']}</b>",
            f"  {Style.SUCCESS} Принято: <b>{stats['accepted']}</b>",
            f"  {Style.DANGER} Отклонено: <b>{stats['rejected']}</b>",
            f"  {Style.REFRESH} В работе: <b>{stats['active']}</b>",
            f"  {Style.CLOCK} Ожидает: <b>{stats['waiting']}</b>",
            f"  {Style.MONEY} Бонусов выдано: <code>{stats['total_bonus']:.2f} $</code>",
            f"",
        ]

        kb_rows = []
        if rows:
            lines.append(f"{Style.DOC} <b>Последние заявки:</b>")
            for row in rows:
                log_id, order_id, user_id, username, service, number, code, status, worker_id, worker_username, price, worker_price, created_at, completed_at = row
                status_icon = {
                    'accepted': Style.SUCCESS,
                    'rejected': Style.DANGER,
                    'active': Style.REFRESH,
                    'waiting': Style.CLOCK,
                }.get(status, Style.INFO)
                user_short = (username[:15] + '...') if username and len(username) > 15 else (username or f"ID:{user_id}")
                lines.append(f"  #{order_id} | {service} | {user_short} | {status_icon}")
                kb_rows.append([InlineKeyboardButton(
                    text=f"#{order_id} | {service} | {status_icon}",
                    callback_data=f"logdtl_{log_id}"
                )])
        else:
            lines.append(f"{Style.INFO} Заявок за последние 5 дней не найдено.")

        kb_rows.append([InlineKeyboardButton(text=f"{Style.REFRESH} Обновить", callback_data="admin_logs")])
        kb_rows.append([InlineKeyboardButton(text=f"{Style.BACK} Назад", callback_data="admin_panel")])

        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
            parse_mode="HTML",
        )
        await callback.answer()
    except Exception as e:
        await callback.answer(f"{Style.CROSS} Ошибка: {str(e)[:100]}", show_alert=True)


@router.callback_query(F.data.startswith("logdtl_"))
async def log_detail(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    try:
        log_id = int(callback.data.split("_", 1)[1])
        row = await get_order_log_by_id(log_id)
        if not row:
            await callback.answer(f"{Style.CROSS} Запись не найдена")
            return

        log_id, order_id, user_id, username, service, number, code, status, worker_id, worker_username, price, worker_price, created_at, completed_at = row

        status_labels = {
            'accepted': f"{Style.SUCCESS} Принята",
            'rejected': f"{Style.DANGER} Отклонена",
            'active': f"{Style.REFRESH} В работе",
            'waiting': f"{Style.CLOCK} Ожидает",
        }
        status_text = status_labels.get(status, status)

        user_label = username or f"ID: {user_id}"
        worker_label = worker_username or (f"ID: {worker_id}" if worker_id else "—")

        created_str = str(created_at)[:19] if created_at else "—"
        completed_str = str(completed_at)[:19] if completed_at else "—"

        text = (
            f"{Style.DOC} <b>Детали заявки #{order_id}</b>\n\n"
            f"{Style.USER} <b>Пользователь:</b> <code>{user_label}</code>\n"
            f"{Style.PHONE} <b>Сервис:</b> <code>{service}</code>\n"
            f"{Style.CODE} <b>Номер:</b> <code>{number}</code>\n"
            f"{Style.INFO} <b>Статус:</b> {status_text}\n"
            f"{Style.MONEY} <b>Бонус:</b> <code>{price:.2f} $</code>\n\n"
            f"{Style.WORKER} <b>Скуп:</b> <code>{worker_label}</code>\n"
            f"{Style.MONEY} <b>Цена скупа:</b> <code>{worker_price:.2f} $</code>\n"
            f"{Style.CODE} <b>Код:</b> <code>{code or '—'}</code>\n\n"
            f"{Style.CLOCK} <b>Создана:</b> <code>{created_str}</code>\n"
            f"{Style.CLOCK} <b>Завершена:</b> <code>{completed_str}</code>"
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{Style.CROSS} Отменить заявку", callback_data=f"logcancel_{order_id}")],
            [InlineKeyboardButton(text=f"{Style.BACK} Назад к списку", callback_data="admin_logs")],
            [InlineKeyboardButton(text=f"{Style.HOME} В панель", callback_data="admin_panel")],
        ])

        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        await callback.answer(f"{Style.CROSS} Ошибка: {str(e)[:100]}", show_alert=True)
@router.message(Command("ai"))
async def ai_start(message: Message, state: FSMContext):
    if not admin_only(message.from_user.id):
        return
    await state.set_state(AdminState.ai_assistant_chat)
    ai_assistant.clear_history(message.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Style.CROSS} Выйти из AI-режима", callback_data="ai_exit")],
    ])
    text = f"{Style.GEM} <b>AI-ассистент активирован</b>\n\n" + \
           f"{Style.INFO} Примеры запросов:\n" + \
           f"  • покажи очередь\n" + \
           f"  • назначь @ivan скупом для VK\n" + \
           f"  • поставь цену на Steam 150\n" + \
           f"  • удали сервис OK\n" + \
           f"  • пополни баланс скупа 123456 на 500\n\n" + \
           f"{Style.WARNING} Опасные действия требуют подтверждения.\n" + \
           f"{Style.INFO} Используйте /ai для сброса диалога."
    await message.answer(
        text,
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "ai_exit")
async def ai_exit(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await state.clear()
    ai_assistant.clear_history(callback.from_user.id)
    await callback.message.edit_text(
        f"{Style.CROSS} AI-ассистент деактивирован.\n"
        f"{Style.INFO} Используйте /admin для панели управления."
    )
    await callback.answer()


@router.message(AdminState.ai_assistant_chat)
async def ai_chat_handler(message: Message, state: FSMContext):
    if not admin_only(message.from_user.id):
        return

    if message.text.lower() in ["exit", "выход", "quit", "стоп", "/ai_exit"]:
        await state.clear()
        ai_assistant.clear_history(message.from_user.id)
        await message.answer(
            f"{Style.CROSS} AI-ассистент деактивирован.",
            reply_markup=main_panel_kb(),
        )
        return

    thinking = await message.answer(f"{Style.REFRESH} <i>AI думает...</i>", parse_mode="HTML")

    result = await ai_assistant.process(message.from_user.id, message.text)

    try:
        await thinking.delete()
    except Exception:
        pass

    intent = result.get("intent", "unknown")
    params = result.get("params", {})
    explanation = result.get("explanation", "Нет объяснения")
    requires_confirmation = result.get("requires_confirmation", False)

    if intent == "error":
        await message.answer(
            f"{Style.CROSS} <b>Ошибка AI</b>\n\n{explanation}",
            parse_mode="HTML",
        )
        return

    if intent == "need_params":
        await message.answer(
            f"{Style.WARNING} <b>Недостаточно данных</b>\n\n{explanation}",
            parse_mode="HTML",
        )
        return

    if intent == "unknown":
        await message.answer(
            f"{Style.INFO} <b>Не понял запрос</b>\n\n{explanation}\n\n"
            f"{Style.INFO} Попробуйте: /ai для справки",
            parse_mode="HTML",
        )
        return

    if intent in ai_assistant.SAFE_INTENTS and not requires_confirmation:
        await _execute_safe_intent(message, intent, params, explanation)
        return

    if intent in ai_assistant.DANGEROUS_INTENTS or requires_confirmation:
        await state.update_data(
            pending_ai_intent=intent,
            pending_ai_params=params,
            pending_ai_explanation=explanation,
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{Style.CHECK} Подтвердить",
                callback_data="ai_confirm"
            )],
            [InlineKeyboardButton(
                text=f"{Style.CROSS} Отменить",
                callback_data="ai_cancel"
            )],
        ])

        await message.answer(
            f"{Style.WARNING} <b>Требуется подтверждение</b>\n\n"
            f"{Style.INFO} Действие: <code>{intent}</code>\n"
            f"{Style.DOC} Параметры: <code>{json.dumps(params, ensure_ascii=False)}</code>\n\n"
            f"{explanation}",
            reply_markup=kb,
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"{Style.INFO} <b>AI ответ:</b>\n\n{explanation}",
        parse_mode="HTML",
    )


async def _execute_safe_intent(message: Message, intent: str, params: dict, explanation: str):
    from db import (
        get_all_workers, get_worker_services, get_all_users,
        get_all_services, get_all_service_prices, get_queue_count,
        get_all_withdrawals, get_worker_prices, get_user_balance,
        get_orders_by_number, get_username_by_id,
    )

    lines = [f"{Style.INFO} <b>{explanation}</b>\n"]

    if intent == "show_stats":
        workers = await get_all_workers()
        users = await get_all_users()
        services = await get_all_services()
        total_queue = 0
        for svc in services:
            total_queue += await get_queue_count(svc)

        lines.append(
            f"{Style.STATS} <b>Общая статистика:</b>\n"
            f"  {Style.WORKER} Скупов: <b>{len(workers)}</b>\n"
            f"  {Style.USER} Пользователей: <b>{len(users)}</b>\n"
            f"  {Style.SERVICES} Сервисов: <b>{len(services)}</b>\n"
            f"  {Style.QUEUE} Заявок в очереди: <b>{total_queue}</b>"
        )

    elif intent == "show_queue":
        services = await get_all_services()
        lines.append(f"{Style.QUEUE} <b>Очередь по сервисам:</b>")
        for svc in services:
            count = await get_queue_count(svc)
            lines.append(f"  {Style.PHONE} {svc}: <b>{count}</b>")

    elif intent == "show_workers":
        workers = await get_all_workers()
        lines.append(f"{Style.WORKER} <b>Скупы:</b>")
        for wid in workers:
            label = await get_user_display_name(wid)
            services = await get_worker_services(wid)
        else:
            label = f"ID: {wid}"
            svc_str = ", ".join(services) if services else "нет сервисов"
            lines.append(f"  {Style.WORKER} {label} — {svc_str}")

    elif intent == "show_users":
        users = await get_all_users()
        lines.append(f"{Style.USER} <b>Пользователи ({len(users)}):</b>")
        for uid, uname in users[:20]:
            label = f"@{uname}" if uname else str(uid)
            lines.append(f"  {Style.USER} {label}")
        if len(users) > 20:
            lines.append(f"  ... и ещё {len(users) - 20}")

    elif intent == "show_withdrawals":
        rows = await get_all_withdrawals()
        lines.append(f"{Style.WITHDRAW} <b>Заявки на выплаты:</b>")
        if not rows:
            lines.append(f"  {Style.INFO} Пока нет заявок")
        else:
            for wid, uid, amount, details, status in rows[:10]:
                user_label = await get_user_display_name(uid)
                status_icon = f"{Style.SUCCESS} ОПЛ" if status == 'paid' else f"{Style.CLOCK} ЖДЁТ"
                lines.append(f"  #{wid} | {user_label} | {amount}$ | {status_icon}")

    elif intent == "show_services":
        services = await get_all_services()
        prices = await get_all_service_prices()
        workers = await get_all_workers()

        # Get active services (services that have workers)
        active_services = set()
        for wid in workers:
            svcs = await get_worker_services(wid)
            active_services.update(svcs)

        lines.append(f"{Style.SERVICES} <b>Все сервисы в базе:</b>")
        for svc in services:
            price = prices.get(svc, 0)
            status = f"{Style.SUCCESS} активен" if svc in active_services else f"{Style.CLOCK} нет скупов"
            lines.append(f"  {Style.PHONE} {svc}: <code>{price}$</code> ({status})")
        lines.append(f"{Style.INFO} Всего: {len(services)} сервисов, активных: {len(active_services)}")

    elif intent == "show_bonuses":
        prices = await get_all_service_prices()
        lines.append(f"{Style.BONUS} <b>Цены / бонусы:</b>")
        for svc, price in prices.items():
            lines.append(f"  {Style.PRICE} {svc}: <code>{price}$</code>")

    elif intent == "search_deals":
        number = params.get("number", "")
        if not number:
            lines.append(f"{Style.WARNING} Укажите номер телефона")
        else:
            orders = await get_orders_by_number(number)
            lines.append(f"{Style.SEARCH} <b>Сделки по {number}:</b>")
            if not orders:
                lines.append(f"  {Style.INFO} Не найдено")
            else:
                for order in orders[:10]:
                    oid, uid, svc, num, code, status, wid = order
                    status_label = STATUS_LABELS.get(status, status)
                    lines.append(f"  #{oid} | {svc} | {status_label}")

    elif intent == "show_worker_prices":
        workers = await get_all_workers()
        lines.append(f"{Style.PRICE} <b>Цены скупов:</b>")
        for wid in workers:
            label = await get_user_display_name(wid)
            prices = await get_worker_prices(wid)
        else:
            label = f"ID: {wid}"
            if prices:
                price_str = ", ".join([f"{s}:{p}$" for s, p in prices.items()])
                lines.append(f"  {Style.WORKER} {label}: {price_str}")
            else:
                lines.append(f"  {Style.WORKER} {label}: нет цен")

    elif intent == "show_worker_balance":
        workers = await get_all_workers()
        lines.append(f"{Style.BALANCE} <b>Баланс скупов:</b>")
        for wid in workers:
            label = await get_user_display_name(wid)
            balance = await get_user_balance(wid)
        else:
            label = f"ID: {wid}"
            lines.append(f"  {Style.WORKER} {label}: <code>{balance}$</code>")

    else:
        lines.append(f"{Style.INFO} {explanation}")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.callback_query(F.data == "ai_confirm")
async def ai_confirm_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not admin_only(callback.from_user.id):
        return

    data = await state.get_data()
    intent = data.get("pending_ai_intent")
    params = data.get("pending_ai_params", {})

    if not intent:
        await callback.answer(f"{Style.CROSS} Нет pending действия")
        return

    await _execute_dangerous_intent(callback, state, bot, intent, params)
    await state.update_data(pending_ai_intent=None, pending_ai_params=None)
    await callback.answer(f"{Style.CHECK} Выполнено!")


@router.callback_query(F.data == "ai_cancel")
async def ai_cancel_handler(callback: CallbackQuery, state: FSMContext):
    if not admin_only(callback.from_user.id):
        return
    await state.update_data(pending_ai_intent=None, pending_ai_params=None)
    await callback.message.edit_text(
        f"{Style.CROSS} Действие отменено.\n"
        f"{Style.INFO} Используйте /ai для нового запроса."
    )
    await callback.answer()


async def _execute_dangerous_intent(callback: CallbackQuery, state: FSMContext, bot: Bot, intent: str, params: dict):
    from db import (
        set_service_price, add_worker, remove_worker, delete_user,
        remove_service, remove_all_services, mark_withdrawal_paid,
        add_user_balance, set_worker_price, get_user_id_by_username,
        is_worker, get_all_services, get_username_by_id,
    )

    result_lines = [f"{Style.CHECK} <b>Результат:</b>\n"]

    try:
        if intent == "set_price":
            service = params.get("service", "")
            price = float(params.get("price", 0))
            if service and price >= 0:
                await set_service_price(service, price)
                result_lines.append(f"{Style.CHECK} Цена для <code>{service}</code>: <code>{price}$</code>")
            else:
                result_lines.append(f"{Style.CROSS} Неверные параметры")

        elif intent == "add_worker":
            username = params.get("username", "")
            worker_id = await get_user_id_by_username(username)
            if not worker_id:
                result_lines.append(f"{Style.CROSS} Пользователь <code>{username}</code> не найден")
            elif await is_worker(worker_id):
                result_lines.append(f"{Style.WARNING} <code>{username}</code> уже скуп")
            else:
                await add_worker(worker_id)
                try:
                    await bot.send_message(worker_id, f"{Style.WORKER} Вы назначены скупом!")
                except Exception:
                    pass
                result_lines.append(f"{Style.CHECK} <code>{username}</code> добавлен как скуп")

        elif intent == "remove_worker":
            username = params.get("username", "")
            worker_id = await get_user_id_by_username(username)
            if not worker_id:
                try:
                    worker_id = int(params.get("username", 0))
                except ValueError:
                    pass
            if worker_id and await is_worker(worker_id):
                await remove_worker(worker_id)
                try:
                    await bot.send_message(worker_id, f"{Style.CROSS} Вы удалены из скупов")
                except Exception:
                    pass
                result_lines.append(f"{Style.CHECK} Скуп <code>{worker_id}</code> удалён")
            else:
                result_lines.append(f"{Style.CROSS} Скуп не найден")

        elif intent == "delete_user":
            username = params.get("username", "")
            user_id = await get_user_id_by_username(username)
            if not user_id:
                result_lines.append(f"{Style.CROSS} Пользователь <code>{username}</code> не найден")
            elif await is_worker(user_id):
                result_lines.append(f"{Style.WARNING} Это скуп — удалите через раздел Скупы")
            else:
                await delete_user(user_id)
                result_lines.append(f"{Style.CHECK} <code>{username}</code> удалён")

        elif intent == "remove_service":
            service = params.get("service", "")
            all_svcs = await get_all_services()
            if service in all_svcs:
                await remove_service(service)
                result_lines.append(f"{Style.CHECK} Сервис <code>{service}</code> удалён")
            else:
                result_lines.append(f"{Style.CROSS} Сервис <code>{service}</code> не найден")

        elif intent == "remove_all_services":
            await remove_all_services()
            result_lines.append(f"{Style.CHECK} Все сервисы удалены")

        elif intent == "mark_paid":
            withdrawal_id = int(params.get("withdrawal_id", 0))
            if withdrawal_id:
                await mark_withdrawal_paid(withdrawal_id)
                result_lines.append(f"{Style.CHECK} Выплата <code>#{withdrawal_id}</code> отмечена оплаченной")
            else:
                result_lines.append(f"{Style.CROSS} Неверный ID выплаты")

        elif intent == "top_up_balance":
            worker_id = int(params.get("worker_id", 0))
            amount = int(params.get("amount", 0))
            if worker_id and amount > 0:
                await add_user_balance(worker_id, amount)
                new_bal = await get_user_balance(worker_id)
                result_lines.append(
                    f"{Style.CHECK} Баланс <code>{worker_id}</code> пополнен на <code>{amount}$</code>\n"
                    f"{Style.MONEY} Новый баланс: <code>{new_bal}$</code>"
                )
            else:
                result_lines.append(f"{Style.CROSS} Неверные параметры")

        elif intent == "set_worker_price":
            worker_id = int(params.get("worker_id", 0))
            service = params.get("service", "")
            price = float(params.get("price", 0))
            if worker_id and service and price >= 0:
                await set_worker_price(worker_id, service, price)
                result_lines.append(
                    f"{Style.CHECK} Цена скупа <code>{worker_id}</code> для <code>{service}</code>: <code>{price}$</code>"
                )
            else:
                result_lines.append(f"{Style.CROSS} Неверные параметры")

        else:
            result_lines.append(f"{Style.WARNING} Неизвестное действие: <code>{intent}</code>")

    except Exception as e:
        result_lines.append(f"{Style.CROSS} Ошибка: <code>{str(e)[:200]}</code>")

    await callback.message.edit_text("\n".join(result_lines), parse_mode="HTML")
