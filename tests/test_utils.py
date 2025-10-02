import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.utils import (  # noqa: E402
    format_meal_message,
    to_float,
    parse_serving,
    make_bar_chart,
    plural_ru_day,
    seconds_until_next_utc_midnight,
    telegram_markdown_to_html,
)


def test_format_meal_message():
    macros = {'calories': 100, 'protein': 10, 'fat': 5, 'carbs': 15}
    result = format_meal_message('Apple', 100.0, macros)
    assert 'Apple' in result
    assert '100.0' in result
    assert '10' in result and '5' in result and '15' in result


def test_to_float():
    assert to_float('12.5g') == 12.5
    assert to_float('нет') == 0.0


def test_parse_serving():
    assert parse_serving('50g') == 50.0
    assert parse_serving('50.25') == 50.2


def test_make_bar_chart():
    totals = {'a': 1, 'b': 2}
    chart = make_bar_chart(totals)
    assert 'A:' in chart and 'B:' in chart


def test_plural_ru_day():
    assert plural_ru_day(1) == 'день'
    assert plural_ru_day(2) == 'дня'
    assert plural_ru_day(5) == 'дней'
    assert plural_ru_day(11) == 'дней'


def test_seconds_until_next_utc_midnight():
    morning = datetime(2024, 1, 1, 8, 0, 0)
    evening = datetime(2024, 1, 1, 23, 30, 0)
    assert seconds_until_next_utc_midnight(morning) == 16 * 3600
    assert seconds_until_next_utc_midnight(evening) == 30 * 60


def test_telegram_markdown_to_html():
    text = "**жирный** __курсив__ ~~зачерк~~ `код`\n```\nмногострочный\nкод\n```"
    rendered = telegram_markdown_to_html(text)
    assert "<b>жирный</b>" in rendered
    assert "<i>курсив</i>" in rendered
    assert "<s>зачерк</s>" in rendered
    assert "<code>код</code>" in rendered
    assert "<pre>\nмногострочный\nкод\n</pre>" in rendered
    assert "<script>" not in rendered
