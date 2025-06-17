import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List

from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import tempfile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State

from bot.services import classify_food, recognize_dish, calculate_macros

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, ForeignKey
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

API_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot.db")

WELCOME_TEXT = (
    "Я — твой AI-диетолог 🧠\n\n"
    "Загрузи фото еды, и за секунды получишь:\n"
    "— Калории\n"
    "— Белки, жиры, углеводы\n"
    "— Быстрый отчёт в историю\n\n"
    "🔍 Готов? Отправь фото."
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    meals = relationship('Meal', back_populates='user')


class Meal(Base):
    __tablename__ = 'meals'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    name = Column(String)
    ingredients = Column(String)
    serving = Column(Float)
    calories = Column(Float)
    protein = Column(Float)
    fat = Column(Float)
    carbs = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user = relationship('User', back_populates='meals')


Base.metadata.create_all(engine)


class EditMeal(StatesGroup):
    waiting_input = State()


def format_meal_message(name: str, serving: float, macros: Dict[str, float]) -> str:
    return (
        f"\U0001F37D {name}\n"
        f"\u2696 {serving} г\n"
        f"\U0001F522 {macros['calories']} ккал / {macros['protein']} г / {macros['fat']} г / {macros['carbs']} г"
    )


def make_bar_chart(totals: Dict[str, float]) -> str:
    max_val = max(totals.values()) if totals else 1
    chart = ""
    for key, val in totals.items():
        bar = '█' * int((val / max_val) * 10)
        chart += f"{key[:1].upper()}: {bar} {val}\n"
    return chart


def meal_actions_kb(meal_id: str) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Уточнить", callback_data=f"edit:{meal_id}")
    builder.button(text="🗑 Удалить", callback_data=f"delete:{meal_id}")
    builder.button(text="💾 Сохранить", callback_data=f"save:{meal_id}")
    builder.adjust(3)
    return builder.as_markup()


def history_nav_kb(offset: int, total: int) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if offset > 0:
        builder.button(text="\u2190", callback_data=f"hist:{offset-1}")
    if offset < total - 1:
        builder.button(text="\u2192", callback_data=f"hist:{offset+1}")
    if builder.buttons:
        builder.adjust(len(builder.buttons))
    return builder.as_markup()


def stats_period_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="День", callback_data="stats:day")
    builder.button(text="Неделя", callback_data="stats:week")
    builder.button(text="Месяц", callback_data="stats:month")
    builder.adjust(3)
    return builder.as_markup()


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Main menu buttons arranged vertically."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="\U0001F4F8 Новое фото")],
            [KeyboardButton(text="\U0001F9FE \u041E\u0442\u0447\u0451\u0442 \u0437\u0430 \u0434\u0435\u043D\u044C")],
            [KeyboardButton(text="\U0001F4CA \u041C\u043E\u0438 \u043F\u0440\u0438\u0451\u043C\u044B")],
            [KeyboardButton(text="\u2753 \u0427\u0430\u0412\u041E")],
        ],
        resize_keyboard=True,
    )


def back_menu_kb() -> ReplyKeyboardMarkup:
    """Single button keyboard to return to main menu."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="\U0001F951 \u0413\u043B\u0430\u0432\u043D\u043E\u0435 \u043C\u0435\u043D\u044E")]],
        resize_keyboard=True,
    )

pending_meals: Dict[str, Dict] = {}


async def cmd_start(message: types.Message):
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    if not user:
        user = User(telegram_id=message.from_user.id)
        session.add(user)
        session.commit()
    session.close()
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())


async def back_to_menu(message: types.Message):
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())


async def request_photo(message: types.Message):
    await message.answer(
        "\U0001F525\u041E\u0442\u043B\u0438\u0447\u043D\u043E! \u041E\u0442\u043F\u0440\u0430\u0432\u044C \u0444\u043E\u0442\u043E \u0435\u0434\u044B \u2014 \u044F \u0432\u0441\u0451 \u043F\u043E\u0441\u0447\u0438\u0442\u0430\u044E \u0441\u0430\u043C.",
        reply_markup=back_menu_kb(),
    )


async def handle_photo(message: types.Message, state: FSMContext):
    await message.reply("Готово! \ud83d\udd0d\nАнализирую фото…")
    photo = message.photo[-1]
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        await message.bot.download(photo.file_id, destination=tmp.name)
        photo_path = tmp.name
    classification = await classify_food(photo_path)
    if not classification['is_food'] or classification['confidence'] < 0.7:
        await message.answer(
            "\ud83e\udd14 \u0415\u0434\u0443 \u043d\u0430 \u044d\u0442\u043e\u043c \u0444\u043e\u0442\u043e \u043d\u0430\u0439\u0442\u0438 \u043d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c.\n"
            "\u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439 \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u0434\u0440\u0443\u0433\u043e\u0435 \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435 \u2014 \u043f\u043e\u0441\u0442\u0430\u0440\u0430\u044e\u0441\u044c \u0440\u0430\u0441\u043f\u043e\u0437\u043d\u0430\u0442\u044c."
        )
        return
    dish = await recognize_dish(photo_path)
    name = dish.get('name')
    ingredients = dish.get('ingredients', [])
    serving = dish.get('serving', 0)
    if not name:
        builder = InlineKeyboardBuilder()
        builder.button(text="✏️ Уточнить", callback_data="refine")
        builder.button(text="🗑 Удалить", callback_data="cancel")
        builder.adjust(2)
        await state.update_data(photo_path=photo_path, ingredients=ingredients, serving=serving)
        await message.answer(
            "\ud83e\udd14 \u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0442\u043e\u0447\u043d\u043e \u0440\u0430\u0441\u043f\u043e\u0437\u043d\u0430\u0442\u044c \u0431\u043b\u044e\u0434\u043e \u043d\u0430 \u0444\u043e\u0442\u043e.\n\u041c\u043e\u0436\u0435\u0448\u044c \u0432\u0432\u0435\u0441\u0442\u0438 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u0438 \u0432\u0435\u0441 \u0432\u0440\u0443\u0447\u043d\u0443\u044e?",
            reply_markup=builder.as_markup(),
        )
        await state.set_state(EditMeal.waiting_input)
        return
    macros = await calculate_macros(ingredients, serving)
    meal_id = f"{message.from_user.id}_{datetime.utcnow().timestamp()}"
    pending_meals[meal_id] = {
        'name': name,
        'ingredients': ingredients,
        'serving': serving,
        'macros': macros,
    }
    await message.answer(
        format_meal_message(name, serving, macros),
        reply_markup=meal_actions_kb(meal_id)
    )


async def cb_edit(query: types.CallbackQuery, state: FSMContext):
    meal_id = query.data.split(':', 1)[1]
    await state.update_data(meal_id=meal_id)
    await query.bot.send_message(query.from_user.id, "Введите название и вес, напр. 'Яблоко 150'")
    await state.set_state(EditMeal.waiting_input)
    await query.answer()


async def cb_refine(query: types.CallbackQuery, state: FSMContext):
    await query.bot.send_message(query.from_user.id, "Введите название и вес, напр. 'Борщ 250'")
    await state.set_state(EditMeal.waiting_input)
    await query.answer()


async def cb_cancel(query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.delete()
    await query.answer("Удалено")

async def process_edit(message: types.Message, state: FSMContext):
    data = await state.get_data()
    meal_id = data.get('meal_id', f"{message.from_user.id}_{datetime.utcnow().timestamp()}")
    parts = message.text.split()
    if len(parts) >= 2 and parts[-1].replace('.', '', 1).isdigit():
        serving = float(parts[-1])
        name = ' '.join(parts[:-1])
    else:
        name = message.text
        serving = 100.0
    ingredients = [name]
    macros = await calculate_macros(ingredients, serving)
    pending_meals[meal_id] = {
        'name': name,
        'ingredients': ingredients,
        'serving': serving,
        'macros': macros,
    }
    await message.answer(
        format_meal_message(name, serving, macros),
        reply_markup=meal_actions_kb(meal_id)
    )
    await state.clear()


async def cb_delete(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    pending_meals.pop(meal_id, None)
    await query.message.delete()
    await query.answer("Удалено")


async def cb_save(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    meal = pending_meals.pop(meal_id, None)
    if not meal:
        await query.answer("Нечего сохранять", show_alert=True)
        return
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=query.from_user.id).first()
    if not user:
        user = User(telegram_id=query.from_user.id)
        session.add(user)
        session.commit()
    new_meal = Meal(
        user_id=user.id,
        name=meal['name'],
        ingredients=','.join(meal['ingredients']),
        serving=meal['serving'],
        calories=meal['macros']['calories'],
        protein=meal['macros']['protein'],
        fat=meal['macros']['fat'],
        carbs=meal['macros']['carbs'],
    )
    session.add(new_meal)
    session.commit()
    session.close()
    await query.answer("Сохранено в историю!")


async def send_history(bot: Bot, user_id: int, chat_id: int, offset: int):
    session = SessionLocal()
    q = session.query(Meal).join(User).filter(User.telegram_id == user_id).order_by(Meal.timestamp.desc())
    total = q.count()
    meal = q.offset(offset).limit(1).first()
    session.close()
    if not meal:
        await bot.send_message(chat_id, "История пуста.")
        return
    await bot.send_message(
        chat_id,
        format_meal_message(
            meal.name,
            meal.serving,
            {
                'calories': meal.calories,
                'protein': meal.protein,
                'fat': meal.fat,
                'carbs': meal.carbs,
            },
        ),
        reply_markup=history_nav_kb(offset, total)
    )


async def cmd_history(message: types.Message):
    await send_history(message.bot, message.from_user.id, message.chat.id, 0)


async def cb_history(query: types.CallbackQuery):
    offset = int(query.data.split(':', 1)[1])
    await query.message.delete()
    await send_history(query.bot, query.from_user.id, query.message.chat.id, offset)
    await query.answer()


async def cmd_stats(message: types.Message):
    await message.answer("Выберите период:", reply_markup=stats_period_kb())


async def cb_stats(query: types.CallbackQuery):
    period = query.data.split(':', 1)[1]
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=query.from_user.id).first()
    if not user:
        await query.answer("Нет данных", show_alert=True)
        session.close()
        return
    now = datetime.utcnow()
    if period == 'day':
        start = now - timedelta(days=1)
    elif period == 'week':
        start = now - timedelta(weeks=1)
    else:
        start = now - timedelta(days=30)
    meals = session.query(Meal).filter(Meal.user_id == user.id, Meal.timestamp >= start).all()
    session.close()
    if not meals:
        await query.message.edit_text("Нет данных за выбранный период.")
        await query.answer()
        return
    totals = {'calories': 0.0, 'protein': 0.0, 'fat': 0.0, 'carbs': 0.0}
    for m in meals:
        totals['calories'] += m.calories
        totals['protein'] += m.protein
        totals['fat'] += m.fat
        totals['carbs'] += m.carbs
    text = (
        f"Всего за период:\n"
        f"{totals['calories']} ккал / {totals['protein']} г / {totals['fat']} г / {totals['carbs']} г\n\n"
        f"{make_bar_chart(totals)}"
    )
    await query.message.edit_text(text)
    await query.answer()


bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

dp.message.register(cmd_start, Command('start'))
dp.message.register(request_photo, F.text == "\U0001F4F8 Новое фото")
dp.message.register(handle_photo, F.photo)
dp.message.register(back_to_menu, F.text == "\U0001F951 \u0413\u043B\u0430\u0432\u043D\u043E\u0435 \u043C\u0435\u043D\u044E")
dp.message.register(cmd_history, Command('history'))
dp.message.register(cmd_stats, Command('stats'))

dp.message.register(process_edit, StateFilter(EditMeal.waiting_input))

dp.callback_query.register(cb_edit, F.data.startswith('edit:'))
dp.callback_query.register(cb_refine, F.data == 'refine')
dp.callback_query.register(cb_cancel, F.data == 'cancel')
dp.callback_query.register(cb_delete, F.data.startswith('delete:'))
dp.callback_query.register(cb_save, F.data.startswith('save:'))
dp.callback_query.register(cb_history, F.data.startswith('hist:'))
dp.callback_query.register(cb_stats, F.data.startswith('stats:'))

async def handle_error(update: types.Update, exception: Exception) -> bool:
    if isinstance(update, types.Message):
        await update.answer("Произошла ошибка на сервере, попробуйте позже.")
    elif isinstance(update, types.CallbackQuery):
        await update.message.answer("Произошла ошибка на сервере, попробуйте позже.")
    return True

dp.errors.register(handle_error)


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
