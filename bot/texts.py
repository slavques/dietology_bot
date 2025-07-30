# Text constants for bot messages
from datetime import date

MONTHS_RU = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def format_date_ru(dt: date) -> str:
    month = MONTHS_RU.get(dt.month, dt.strftime("%B"))
    return f"{dt.day} {month}"


INTRO_BASE = (
    "🍞 <b>Разблокируй ритм!</b>\n\n"
    "Текущий тариф: {plan}\n\n"
    "Не считай запросы.\n"
    "Не сбивайся.\n"
    "Просто продолжай — в том же темпе.\n"
    "Оставь еду под контролем — без лишнего напряга."
)

PLAN_TEXT = (
    "Тариф: <b>{grade}</b>\n\n"
    "📉 Чем дольше срок — тем ниже цена!\n"
    "Подключение и оплата — в пару кликов."
)

SUB_END_7D = (
    "📅 До окончания подписки осталось 7 дней.\n\n"
    "Не дай еде стать тайной — продли подписку и продолжай получать КБЖУ в кликов!\n\n"
    "🔥Всего за {price} ₽/мес."
)

SUB_END_3D = (
    "📅 3 дня до финиша подписки.\n\n"
    "Твоя тарелка всё ещё под наблюдением. Хочешь сохранить ритм? Продли на следующий период.\n\n"
    "🔥Всего за {price} ₽/мес."
)

SUB_END_1D = (
    "📅 Последний день подписки.\n\n"
    "Завтра ты проснёшься без помощника. Без мгновенного КБЖУ, без истории, без разбора приёмов пищи.\n\n"
    "Хочешь — я продолжу. Просто продли подписку 👇\n\n"
    "🔥Всего за {price} ₽/мес."
)

SUB_PAUSED = (
    "🔴 Подписка приостановлена.\n\n"
    "Я по-прежнему с тобой, но теперь могу отвечать только ограниченно.\n\n"
    "Хочешь, чтобы всё снова было как раньше?\nПродли подписку 👇\n\n"
    "🔥Всего за {price} ₽/мес."
)

FREE_DAY_TEXT = (
    "🎯Новый день — новые запросы\n"
    "Твои 20 бесплатных КБЖУ-анализов доступны!\n\n"
    "Готов продолжить?"
)

LIMIT_REACHED_TEXT = (
    "⚠️ Лимит на запросы исчерпан.\n"
    "Новые запросы появятся: <b>{date}</b>.\n\n"
    "А пока можешь перейти на безлимит — и продолжить прямо сейчас 👇"
)
PAID_DAILY_LIMIT_TEXT = (
    "Превышен дневной лимит запросов. Пишите в поддержку {support}"
)

# Template for meal info message
MEAL_TEMPLATE = (
    "🍽 {name}\n"
    "⚖️ Вес: {serving} г\n"
    "🔥 Калории: {calories} ккал\n"
    "Белки: {protein} г\n"
    "Жиры: {fat} г\n"
    "Углеводы: {carbs} г"
)
# Button labels
BTN_EDIT = "✏️ Уточнить"
BTN_DELETE = "🗑 Удалить"
BTN_SAVE = "💾 Сохранить"
BTN_FULL_PORTION = "🟩 Полная порция"
BTN_HALF_PORTION = "🟨 Половина порции"
BTN_QUARTER_PORTION = "🟦 1/4 Порции"
BTN_THREEQ_PORTION = "🟧 3/4 Порции"
BTN_BACK = "🔙 Назад"
BTN_ADD = "Добавить"
BTN_LEFT_HISTORY = "⬅️ Записи ранее"
BTN_RIGHT_HISTORY = "Записи позже ➡️"
BTN_DAY = "День"
BTN_WEEK = "Неделя"
BTN_MONTH = "Месяц"
BTN_REPORT_DAY = "🧾 Отчёт за день"
BTN_MY_MEALS = "📊 Мои приёмы"
BTN_STATS = "📈 Статистика"
BTN_SUBSCRIPTION = "⚡ Подписка"
BTN_FAQ = "❓ ЧаВО"
BTN_MAIN_MENU = "🥑 Главное меню"
MENU_STUB = "🥑"
BTN_PAY = "🪙Оплатить"
BTN_BACK_TEXT = "🔙 Назад"
BTN_BANK_CARD = "💳 Банковская карта"
BTN_TELEGRAM_STARS = "Telegram Stars"
BTN_CRYPTO = "Crypto"
BTN_BROADCAST = "Рассылка"
BTN_COMMENT = "Оставить комментарий"
BTN_PRO_MODE = "⚡ Pro-режим"
BTN_LIGHT_MODE = "🔸 Старт"
BTN_MANUAL = "✏️ Ручной ввод"
BTN_SETTINGS = "⚙️ Настройки"
BTN_REMINDERS = "Напоминания"
BTN_GOALS = "Цели питания"
BTN_UPDATE_TIME = "Обновить время"
BTN_MORNING = "Утро"
BTN_DAY_REM = "День"
BTN_EVENING = "Вечер"

TZ_PROMPT = (
    "Текущее время по UTC - {utc_time}\n"
    "Напиши в чат сколько у тебя сейчас время в формате 10:00"
)
TIME_CURRENT = "Твоё текущее время: {local_time}"
REMINDER_ON = "✅ {name} напоминание включено"
REMINDER_OFF = "🔕 {name} напоминание выключено"
SET_TIME_PROMPT = "Введи новое время для «{name}» в формате 10:00"
INVALID_TIME = "Неверный формат времени. Попробуйте ещё раз 10:00"
SETTINGS_TITLE = "Настройки"

# Reminder notification texts
REM_TEXT_MORNING = "Доброе утро! Не забудь сфоткать еду"
REM_TEXT_DAY = "Не забудь сфоткать еду если еще не пообедал"
REM_TEXT_EVENING = "Не забудь сфоткать свой ужин"

DEV_FEATURE = "Функционал в разработке"
FEATURE_DISABLED = "Функционал временно недоступен"

# Portion prefixes used when saving partial servings
PREFIX_FULL = ""
PREFIX_HALF = "1/2 "
PREFIX_QUARTER = "1/4 "
PREFIX_THREEQ = "3/4 "
PORTION_PREFIXES = {
    1.0: PREFIX_FULL,
    0.5: PREFIX_HALF,
    0.25: PREFIX_QUARTER,
    0.75: PREFIX_THREEQ,
}
# Common messages
WELCOME_BASE = (
    "Я — твой AI-диетолог 🧠\n\n"
    "Загрузи фото еды, и за секунды получишь:\n"
    "— Калории\n"
    "— Белки, жиры, углеводы\n"
    "— Быстрый отчёт в историю\n\n"
    "🔍 Готов? Отправь фото."
)
REMAINING_FREE = "(осталось бесплатных запросов: {remaining})"
REMAINING_DAYS = "(осталось дней подписки: {days})"
REQUEST_PHOTO = "🔥Отлично! Отправь фото еды — я всё посчитаю сам."
PHOTO_ANALYZING = "Готово! 🔍\nАнализирую фото…"
MULTI_PHOTO_ERROR = (
    "🤖 Хм… похоже, ты отправил сразу несколько изображений или файл в неподдерживаемом формате.\n\n"
    "Пришли, пожалуйста, одно фото блюда — и я всё рассчитаю!"
)
RECOGNITION_ERROR = "Сервис распознавания недоступен. Попробуйте позднее."
NO_FOOD_ERROR = (
    "🤔 Еду на этом фото найти не удалось.\n"
    "Попробуй отправить другое изображение — постараюсь распознать."
)
SUB_REQUIRED = (
    "⚡ Анализ фото и текста доступен только по подписке.\n"
    "Подключи тариф \U0001F538 Старт — и продолжай без ограничений."
)
CLARIFY_PROMPT = (
    "🤔 Не удалось точно распознать блюдо на фото.\n\n"
    "Хочешь ввести название и вес вручную?"
)
MANUAL_PROMPT = (
    "<b>✏️ Введи блюдо вручную</b>\n"
    "Напиши, что ты ел и, если знаешь, укажи примерный вес или состав.\n\n"
    "Примеры:\n"
    "• «Гречка с курицей, 300 г» \n"
    "• «Яйца (2 шт), авокадо, хлеб цельнозерновой (1 ломтик)»  \n"
    "• «Овсянка на молоке без сахара, 200 г»\n\n"
    "Я проанализирую и скажу, сколько в этом КБЖУ 🔍"
)
MANUAL_ERROR = (
    "🤔 Не удалось распознать описание блюда.\n"
    "Попробуй ещё раз."
)

# FatSecret lookup flow
LOOKUP_PROMPT = (
    "Мы нашли несколько продуктов, выбери наиболее подходящее из списка или уточни полное название и мы попробуем ещё раз!\n\n"
    "КБЖУ указано за 100гр"
)
LOOKUP_WEIGHT = (
    "{name}\n"
    "КБЖУ за 100 г: {calories} ккал, Б: {protein} г, Ж: {fat} г, У: {carbs} г\n\n"
    "Напиши в чат сколько грамм добавим?"
)
DELETE_NOTIFY = "🗑 Запись удалена.\nЕсли хочешь отправить другое блюдо — просто пришли фото"
SESSION_EXPIRED = "Сессия устарела"
SESSION_EXPIRED_RETRY = "Сессия устарела. Отправьте фото заново."
SAVE_DONE = (
    "✅ Готово! Блюдо добавлено в историю.\n"
    "📂 Хочешь посмотреть приёмы за сегодня — они отобразятся в  \n"
    "🧾 Отчёте за день"
)
SERVER_ERROR = "Произошла ошибка на сервере, попробуйте позже."

# Admin texts
ADMIN_MODE = "Админ режим"
ADMIN_UNAVAILABLE = "Недоступно"
BROADCAST_PROMPT = "Введите сообщение"
BROADCAST_ERROR = "Ошибка при отправке сообщения"
BROADCAST_DONE = "Рассылка отправлена"
BTN_DAYS = "Дни"
BTN_ONE = "Одному"
BTN_ALL = "Всем"
BTN_BLOCK = "Блокировка"
BTN_BLOCKED_USERS = "Заблокированные"
BTN_STATS_ADMIN = "Статистика"
BTN_USER = "Пользователь"
ADMIN_CHOOSE_ACTION = "Выберите действие"
ADMIN_ENTER_ID = "Введите telegram_id"
ADMIN_ENTER_DAYS = "Введите количество дней"
ADMIN_DAYS_DONE = "Дни начислены"
BTN_GRADE = "Грейд"
ADMIN_GRADE_DONE = "Грейд активирован"
ADMIN_BLOCK_DONE = "Пользователь заблокирован"
ADMIN_UNBLOCK_DONE = "Пользователь разблокирован"
ADMIN_USER_NOT_FOUND = "Пользователь не найден"
ADMIN_ENTER_COMMENT = "Введите комментарий"
ADMIN_COMMENT_SAVED = "Комментарий сохранен"
ADMIN_BLOCKED_TITLE = "Заблокированные пользователи:"
ADMIN_BLOCKED_EMPTY = "Нет заблокированных пользователей"
ADMIN_STATS = (
    "Всего пользователей: {total}\n"
    "Старт: {light}\n"
    "PRO: {pro}\n"
    "Пробная PRO: {trial_pro}\n"
    "Пробная Старт: {trial_light}\n"
    "Free с запросами: {used}"
)
BTN_FEATURES = "Функционал"
BTN_METHODS = "Методы оплаты"
BTN_GRADES = "Грейды"
BTN_GRADE_START = "Старт"
BTN_GRADE_PRO = "PRO"
ADMIN_METHODS_TITLE = "Методы оплаты"
ADMIN_GRADES_TITLE = "Грейды"
BTN_TRIAL = "Пробный период"
BTN_TRIAL_START = "Стартовый режим"
BTN_STATUS = "Состояние"
BTN_TRIAL_DAYS = "Дни: {days}"
TRIAL_STARTED = "Тебе подключён тариф <b>{grade}</b> на {days} {day_word} бесплатно!"
TRIAL_ENDED = (
    "Твой пробный период закончился, но ты можешь приобрести подписку. "
    "А пока у тебя есть 20 бесплатных запросов ежемесячно."
)
TRIAL_PRO_ENDED_START = (
    "Твой пробный ⚡ Pro-режим закончился, но у тебя ещё остались дни в тарифе 🔸Старт."
)
SUB_SWITCHED = "Твой тариф {old} закончился, но у тебя ещё остались дни в тарифе {new}."
ADMIN_TRIAL_DONE = "Пробный период активирован"
BLOCKED_TEXT = "Вы заблокированы, для решения проблемы обратитесь в поддержку {support}"

# Edit/refine texts
REFINE_BASE = (
    "✏️ Хорошо!\n"
    "Уточни что есть в твоем приёме.\n"
    "Можешь также указать вес, метод приготовления и другие нюансы. \n\n"
    "Например: Сырники жареные на масле 200гр со сметаной 10% 30гр и вишневым джемом 30гр."
)
REFINE_TOO_LONG = "Уточнение должно быть текстом до {max} символов."
REFINE_BAD_ATTEMPT = "Ваше уточнение некорректно. Попробуйте ещё раз."
NOTHING_TO_SAVE = "Нечего сохранять"

# Stats texts
STATS_CHOOSE_PERIOD = "Выберите период:"
STATS_NO_DATA = "Нет данных"
STATS_NO_DATA_PERIOD = "Нет данных за выбранный период."
STATS_MENU_TEXT = (
    "📊 <b>Твоя статистика — под рукой!</b>\n"
    " Посмотри, как ты питаешься: \n"
    "за сегодня или за любые \n"
    "даты.\n\n"
    "Выбери, что хочешь посмотреть:"
)
STATS_TOTALS = (
    "Всего за период:\n"
    "{calories} ккал / {protein} г / {fat} г / {carbs} г\n\n"
    "{chart}"
)
REPORT_EMPTY = (
    "🧾 Отчёт за день\n\n"
    "Пока нет ни одного приёма пищи.\n\n"
    "📸 Отправь фото еды — и я добавлю первую запись!"
)
REPORT_HEADER = "🧾 Отчёт за день"
REPORT_TOTAL = "📊 Итого:"
REPORT_LINE_CAL = "🔥 Калории: {cal} ккал"
REPORT_LINE_P = "• Белки: {protein} г  "
REPORT_LINE_F = "• Жиры: {fat} г  "
REPORT_LINE_C = "• Углеводы: {carbs} г  "
REPORT_MEALS_TITLE = "📂 Приёмы пищи:"
MEAL_LINE = (
    "• {icon} {name}\n"
    "(Калории: {calories} ккал / Белки: {protein} г / Жиры: {fat} г  / Углеводы: {carbs} г)"
)

# History texts
HISTORY_HEADER = "📊 Мои приёмы"
HISTORY_NO_MEALS = "Нет ни одного приёма пищи."
HISTORY_DAY_HEADER = "📊 Итого за {day} {month}:"
HISTORY_LINE_CAL = "🔥 Калории: {cal} ккал"
HISTORY_LINE_P = "• Белки: {protein} г"
HISTORY_LINE_F = "• Жиры: {fat} г"
HISTORY_LINE_C = "• Углеводы: {carbs} г"
HISTORY_EMPTY = "История пуста."

# Subscription texts
SUB_INVALID_PLAN = "Чтобы оформить подписку, свяжитесь с поддержкой."
SUB_METHOD_TEXT = (
    "<b>Создали запрос на покупку.</b>\n"
    "💳 Банковская карта\n"
    "({plan})\n\n"
    'Оплата доступна по кнопке "Оплатить"'
)
SUB_SUCCESS = (
    "🫶 Спасибо за доверие!\n\n"
    "Ты на шаг ближе к понятному, стабильному и осознанному питанию — без пауз и ограничений."
)
SUB_CANCELLED = "Оплата отменена."
NOTIFY_SENT = "Уведомления отправлены"
BTN_PLAN_1M = "🚶‍♂️1 месяц - {price}₽"
BTN_PLAN_3M = "🏃‍♂️3 месяца - {price}₽"
BTN_PLAN_6M = "🧘‍♂️6 месяцев - {price}₽"
PLAN_TITLE_1M = "1 месяц"
PLAN_TITLE_3M = "3 месяца"
PLAN_TITLE_6M = "6 месяцев"
INVOICE_LABEL = "К оплате"
INVOICE_TITLE = "Подписка"

# Additional buttons
BTN_RENEW_SUB = "🔄Продлить подписку"
BTN_REMOVE_LIMITS = "⚡ Снять ограничения"
BTN_REMOVE_LIMIT = "⚡Снять ограничение"

# FAQ text
FAQ_TEXT = (
    "❓ Что, как и почему?\n"
    "Мы собрали все частые вопросы в одной статье: от распознавания еды до подписки.\n\n"
    "👇 Загляни в ЧаВо — там всё просто\n"
    '❓<b><a href="{link}">ЧаВо</a></b>\n\n'
    "📬 Есть вопросы? Напишите нам: {support}\n\n"
    "Ваш код для обращения в тех. поддержку: <code>{telegram_id}</code>"
)
