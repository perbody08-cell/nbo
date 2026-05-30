from aiogram.fsm.state import State, StatesGroup


class OrderState(StatesGroup):
    choosing_service = State()
    choosing_other_service = State()
    entering_number = State()


class AdminState(StatesGroup):
    adding_worker = State()
    removing_worker_services = State()
    deleting_user = State()
    setting_price = State()
    searching_orders = State()
    adding_service = State()
    removing_service = State()
    setting_worker_price = State()
    topping_up_worker_balance = State()
    entering_withdrawal_details = State()
    ai_assistant_chat = State()
