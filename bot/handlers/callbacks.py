from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from ..database import SessionLocal, User, Meal
from ..services import analyze_photo_with_hint, analyze_text_with_hint
from ..subscriptions import ensure_user, notify_trial_end

from ..utils import format_meal_message, parse_serving, to_float
from ..keyboards import (
    meal_actions_kb,
    save_options_kb,
    confirm_save_kb,
    main_menu_kb,
    refine_back_kb,
)
from ..states import EditMeal
from ..storage import pending_meals
from ..texts import (
    DELETE_NOTIFY,
    SESSION_EXPIRED,
    SAVE_DONE,
    REFINE_BASE,
    REFINE_TOO_LONG,
    REFINE_BAD_ATTEMPT,
    NOTHING_TO_SAVE,
    SESSION_EXPIRED_RETRY,
    PORTION_PREFIXES,
)
from ..logger import log


async def cb_refine(query: types.CallbackQuery, state: FSMContext):
    """Prompt user to enter name and weight manually."""
    data = await state.get_data()
    meal_id = data.get("meal_id")
    text = REFINE_BASE
    await query.message.edit_text(text, reply_markup=refine_back_kb(meal_id))
    await state.set_state(EditMeal.waiting_input)
    await query.answer()


async def cb_cancel(query: types.CallbackQuery, state: FSMContext):
    """Cancel current operation."""
    data = await state.get_data()
    meal_id = data.get('meal_id')
    if meal_id:
        pending_meals.pop(meal_id, None)
    await state.clear()
    await query.message.delete()
    await query.answer()
    await query.bot.send_message(
        query.from_user.id,
        DELETE_NOTIFY
    )

async def cb_edit(query: types.CallbackQuery, state: FSMContext):
    meal_id = query.data.split(':', 1)[1]
    await state.update_data(meal_id=meal_id)
    text = REFINE_BASE
    await query.message.edit_text(text, reply_markup=refine_back_kb(meal_id))
    await state.set_state(EditMeal.waiting_input)
    await query.answer()

async def process_edit(message: types.Message, state: FSMContext):
    data = await state.get_data()
    meal_id = data.get('meal_id')
    if not meal_id or meal_id not in pending_meals:
        await message.answer(SESSION_EXPIRED_RETRY)
        await state.clear()
        return
    meal = pending_meals[meal_id]
    session = SessionLocal()
    user = ensure_user(session, message.from_user.id)
    await notify_trial_end(message.bot, session, user)
    if user.blocked:
        from ..settings import SUPPORT_HANDLE
        from ..texts import BLOCKED_TEXT

        await message.answer(BLOCKED_TEXT.format(support=SUPPORT_HANDLE))
        session.close()
        await state.clear()
        return
    grade = user.grade
    session.close()
    MAX_LEN = 200
    if not message.text or len(message.text) > MAX_LEN:
        await message.answer(
            REFINE_TOO_LONG.format(max=MAX_LEN)
        )
        return

    prev_json = meal.get('initial_json', meal)
    if meal.get('photo_path'):
        result = await analyze_photo_with_hint(
            meal['photo_path'], message.text, grade
        )
    else:
        result = await analyze_text_with_hint(
            meal.get('text', ''), message.text, grade
        )
    log("prompt", "clarification analyzed for %s", message.from_user.id)
    if result.get('error') or result.get('is_food') is False or not any(
        k in result for k in ('name', 'serving', 'calories', 'protein', 'fat', 'carbs')
    ):
        if meal.get('error_msg'):
            try:
                await message.bot.delete_message(message.chat.id, meal['error_msg'])
            except Exception:
                pass
            meal.pop('error_msg', None)
        err = await message.answer(REFINE_BAD_ATTEMPT)
        meal['error_msg'] = err.message_id
        log("prompt", "clarification failed for %s", message.from_user.id)
        try:
            await message.delete()
        except Exception:
            pass
        await message.bot.edit_message_text(
            text=format_meal_message(meal['name'], meal['serving'], meal['macros']),
            chat_id=meal['chat_id'],
            message_id=meal['message_id'],
            reply_markup=meal_actions_kb(meal_id)
        )
        await state.clear()
        return
    serving = parse_serving(result.get('serving', meal['serving']))
    macros = {
        'calories': to_float(result.get('calories', meal['macros']['calories'])),
        'protein': to_float(result.get('protein', meal['macros']['protein'])),
        'fat': to_float(result.get('fat', meal['macros']['fat'])),
        'carbs': to_float(result.get('carbs', meal['macros']['carbs'])),
    }
    meal.update({
        'name': result.get('name', meal['name']),
        'type': result.get('type', meal.get('type', 'meal')),
        'serving': serving,
        'orig_serving': serving,
        'macros': macros,
        'orig_macros': macros.copy(),
    })
    if meal.get('error_msg'):
        try:
            await message.bot.delete_message(message.chat.id, meal['error_msg'])
        except Exception:
            pass
        meal.pop('error_msg', None)
    await message.delete()
    await message.bot.edit_message_text(
        text=format_meal_message(meal['name'], meal['serving'], meal['macros']),
        chat_id=meal['chat_id'],
        message_id=meal['message_id'],
        reply_markup=meal_actions_kb(meal_id)
    )
    await state.clear()

async def cb_delete(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    pending_meals.pop(meal_id, None)
    await query.message.delete()
    await query.answer()
    await query.bot.send_message(
        query.from_user.id,
        DELETE_NOTIFY
    )

async def cb_save(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    if meal_id not in pending_meals:
        await query.answer(SESSION_EXPIRED, show_alert=True)
        return
    pending_meals[meal_id].pop('portion', None)
    await query.message.edit_reply_markup(reply_markup=save_options_kb(meal_id))
    await query.answer()


async def _final_save(query: types.CallbackQuery, meal_id: str, fraction: float = 1.0):
    meal = pending_meals.pop(meal_id, None)
    if not meal:
        await query.answer(NOTHING_TO_SAVE, show_alert=True)
        return
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=query.from_user.id).first()
    if not user:
        user = User(telegram_id=query.from_user.id)
        session.add(user)
        session.commit()
    if user.blocked:
        from ..settings import SUPPORT_HANDLE
        from ..texts import BLOCKED_TEXT

        await query.message.answer(BLOCKED_TEXT.format(support=SUPPORT_HANDLE))
        session.close()
        return
    serving = round(parse_serving(meal.get('orig_serving', meal['serving'])) * fraction, 1)
    macros = {
        k: round(to_float(v) * fraction, 1)
        for k, v in meal.get('orig_macros', meal['macros']).items()
    }
    name = PORTION_PREFIXES.get(fraction, "") + meal['name']
    new_meal = Meal(
        user_id=user.id,
        name=name,
        ingredients=','.join(meal['ingredients']),
        type=meal.get('type', 'meal'),
        serving=serving,
        calories=macros['calories'],
        protein=macros['protein'],
        fat=macros['fat'],
        carbs=macros['carbs'],
    )
    session.add(new_meal)
    session.commit()
    log("meal_save", "meal saved for %s: %s %s g", query.from_user.id, name, serving)
    session.close()
    await query.message.edit_reply_markup(reply_markup=None)
    await query.answer()
    await query.bot.send_message(
        query.from_user.id,
        SAVE_DONE,
        reply_markup=main_menu_kb(),
    )

async def cb_save_full(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    meal = pending_meals.get(meal_id)
    if not meal:
        await query.answer(SESSION_EXPIRED, show_alert=True)
        return
    meal['portion'] = 1.0
    serving = round(meal.get('orig_serving', meal['serving']) * 1.0, 1)
    macros = {
        k: round(v * 1.0, 1)
        for k, v in meal.get('orig_macros', meal['macros']).items()
    }
    meal['serving'] = serving
    meal['macros'] = macros
    await query.message.edit_text(
        format_meal_message(meal['name'], serving, macros),
        reply_markup=confirm_save_kb(meal_id),
    )
    await query.answer()


async def cb_save_half(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    meal = pending_meals.get(meal_id)
    if not meal:
        await query.answer(SESSION_EXPIRED, show_alert=True)
        return
    meal['portion'] = 0.5
    serving = round(meal.get('orig_serving', meal['serving']) * 0.5, 1)
    macros = {
        k: round(v * 0.5, 1)
        for k, v in meal.get('orig_macros', meal['macros']).items()
    }
    meal['serving'] = serving
    meal['macros'] = macros
    await query.message.edit_text(
        format_meal_message(meal['name'], serving, macros),
        reply_markup=confirm_save_kb(meal_id),
    )
    await query.answer()


async def cb_save_quarter(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    meal = pending_meals.get(meal_id)
    if not meal:
        await query.answer(SESSION_EXPIRED, show_alert=True)
        return
    meal['portion'] = 0.25
    serving = round(meal.get('orig_serving', meal['serving']) * 0.25, 1)
    macros = {
        k: round(v * 0.25, 1)
        for k, v in meal.get('orig_macros', meal['macros']).items()
    }
    meal['serving'] = serving
    meal['macros'] = macros
    await query.message.edit_text(
        format_meal_message(meal['name'], serving, macros),
        reply_markup=confirm_save_kb(meal_id),
    )
    await query.answer()


async def cb_save_threeq(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    meal = pending_meals.get(meal_id)
    if not meal:
        await query.answer(SESSION_EXPIRED, show_alert=True)
        return
    meal['portion'] = 0.75
    serving = round(meal.get('orig_serving', meal['serving']) * 0.75, 1)
    macros = {
        k: round(v * 0.75, 1)
        for k, v in meal.get('orig_macros', meal['macros']).items()
    }
    meal['serving'] = serving
    meal['macros'] = macros
    await query.message.edit_text(
        format_meal_message(meal['name'], serving, macros),
        reply_markup=confirm_save_kb(meal_id),
    )
    await query.answer()


async def cb_save_back(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    meal = pending_meals.get(meal_id)
    if meal:
        if 'portion' in meal:
            meal.pop('portion', None)
            meal['serving'] = meal.get('orig_serving', meal['serving'])
            meal['macros'] = meal.get('orig_macros', meal['macros'])
            await query.message.edit_text(
                format_meal_message(meal['name'], meal['serving'], meal['macros']),
                reply_markup=save_options_kb(meal_id),
            )
        else:
            await query.message.edit_text(
                format_meal_message(meal['name'], meal['serving'], meal['macros']),
                reply_markup=meal_actions_kb(meal_id),
            )
    await query.answer()


async def cb_add(query: types.CallbackQuery):
    meal_id = query.data.split(':', 1)[1]
    meal = pending_meals.get(meal_id)
    if not meal:
        await query.answer(SESSION_EXPIRED, show_alert=True)
        return
    fraction = meal.pop('portion', 1.0)
    await _final_save(query, meal_id, fraction)


def register(dp: Dispatcher):
    dp.callback_query.register(cb_edit, F.data.startswith('edit:'))
    dp.callback_query.register(cb_refine, F.data == 'refine')
    dp.callback_query.register(cb_cancel, F.data == 'cancel')
    dp.message.register(process_edit, StateFilter(EditMeal.waiting_input), F.text)
    dp.callback_query.register(cb_delete, F.data.startswith('delete:'))
    dp.callback_query.register(cb_save, F.data.startswith('save:'))
    dp.callback_query.register(cb_save_full, F.data.startswith('full:'))
    dp.callback_query.register(cb_save_half, F.data.startswith('half:'))
    dp.callback_query.register(cb_save_quarter, F.data.startswith('quarter:'))
    dp.callback_query.register(cb_save_threeq, F.data.startswith('threeq:'))
    dp.callback_query.register(cb_save_back, F.data.startswith('back:'))
    dp.callback_query.register(cb_add, F.data.startswith('add:'))
