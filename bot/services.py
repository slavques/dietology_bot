import json
import base64
import re
import asyncio
import logging
from typing import Dict, List, Any, Optional

import openai
from openai import RateLimitError, BadRequestError

from .config import OPENAI_API_KEY
from .utils import parse_serving, to_float

client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
# Use the standard GPT‑4o model
# Use the lightweight GPT‑4o model as default
MODEL_NAME = "gpt-4o-mini"
BASIC_MODEL = "gpt-3.5-turbo"

# Simplified prompts for free and paid tiers
SIMPLE_PHOTO_PROMPT = (
    "Ты опытный диетолог. Получишь фото и должен вернуть JSON с ключами "
    "is_food, confidence, type, name, serving, calories, protein, fat, carbs."
)
SIMPLE_TEXT_PROMPT = (
    "Ты опытный диетолог. По текстовому описанию определи блюдо и верни тот же "
    "JSON как и для фото."
)
SIMPLE_HINT_PROMPT = (
    "Ты уже дал ответ в JSON и получил уточнение. Обнови значения в JSON по "
    "уточнению и верни обновлённый JSON."
)


def _prepare_input(messages: List[Dict]) -> (Optional[str], List[Dict]):
    """Convert chat messages to the format expected by the Responses API."""
    instructions = None
    input_items: List[Dict] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if role == "system" and isinstance(content, str):
            # Treat the system prompt as instructions for the model
            instructions = content
            continue
        parts: List[Dict] = []
        if isinstance(content, list):
            for part in content:
                if part.get("type") == "image_url":
                    parts.append(
                        {
                            "type": "input_image",
                            "image_url": part["image_url"]["url"],
                            "detail": "auto",
                        }
                    )
                elif part.get("type") == "text":
                    parts.append({"type": "input_text", "text": part["text"]})
        elif isinstance(content, str):
            parts.append({"type": "input_text", "text": content})
        if parts:
            input_items.append({"type": "message", "role": role, "content": parts})
    return instructions, input_items


def _format_hints(hints: Optional[List[str]]) -> str:
    """Format clarification hints as a numbered list."""
    if not hints:
        return ""
    joined = "\n".join(f"{i}) {h}" for i, h in enumerate(hints, start=1))
    return f"Предыдущие уточнения:\n{joined}\n"


async def _chat(messages: List[Dict], retries: int = 3, backoff: float = 0.5) -> str:
    if not client.api_key:
        return ""
    # Log the prompt being sent to OpenAI for easier debugging
    try:
        system_msg = next(m["content"] for m in messages if m.get("role") == "system")
        logging.info("OpenAI prompt: %s", system_msg)
    except Exception:
        pass
    instructions, input_items = _prepare_input(messages)
    for attempt in range(retries):
        try:
            resp = await client.responses.create(
                model=MODEL_NAME,
                instructions=instructions,
                input=input_items,
                text={"format": {"type": "text"}},
                reasoning={},
                tools=[
                    {
                        "type": "web_search_preview",
                        "user_location": {"type": "approximate"},
                        "search_context_size": "low",
                    }
                ],
                temperature=0.2,
                max_output_tokens=350,
                top_p=0.9,
                store=False,
            )
            content = resp.output_text
            logging.info("OpenAI response: %s", content)
            return content
        except RateLimitError:
            if attempt < retries - 1:
                await asyncio.sleep(backoff * (2 ** attempt))
                continue
            return "__RATE_LIMIT__"
        except BadRequestError:
            return "__BAD_REQUEST__"
        except Exception:
            return "__ERROR__"


async def _completion(
    messages: List[Dict], model: str = BASIC_MODEL, retries: int = 3, backoff: float = 0.5
) -> str:
    """Call the Chat Completions API for simpler tiers."""
    if not client.api_key:
        return ""
    try:
        system_msg = next(m["content"] for m in messages if m.get("role") == "system")
        logging.info("OpenAI prompt: %s", system_msg)
    except Exception:
        pass
    for attempt in range(retries):
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
                max_tokens=350,
                top_p=0.9,
            )
            content = resp.choices[0].message.content
            logging.info("OpenAI response: %s", content)
            return content
        except RateLimitError:
            if attempt < retries - 1:
                await asyncio.sleep(backoff * (2 ** attempt))
                continue
            return "__RATE_LIMIT__"
        except BadRequestError:
            return "__BAD_REQUEST__"
        except Exception:
            return "__ERROR__"




async def analyze_photo(photo_path: str, grade: str = "pro") -> Dict[str, Any]:
    """Analyze photo in a single GPT request and return dish info and macros."""
    if not client.api_key:
        return {
            "is_food": True,
            "confidence": 1.0,
            "name": "Пример блюда",
            "type": "meal",
            "serving": 200,
            "calories": 250,
            "protein": 15,
            "fat": 10,
            "carbs": 30,
        }
    with open(photo_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    prompt = (
        SIMPLE_PHOTO_PROMPT
        if grade != "pro"
        else (
            "Ты — профессиональный диетолог/нутрициолог с большим опытом.\n"
            "Тебе придёт фото, и твоя задача:\n\n"
            "1. Определи, есть ли на фото готовая еда, напиток или продукт питания:\n"
            "   • Если еды или напитка нет — верни {\"is_food\": false}.\n\n"
            "2. Если на фото товар в заводской упаковке (банка, бутылка, упаковка, контейнер с этикеткой и т.п.):\n"
            "   Найди этот конкретный продукт в русскоязычной базе FatSecret (site:fatsecret.ru), обязательно используя точное название бренда и продукта, указанные на упаковке.\n"
            "   • Используй КБЖУ и массу нетто порции из FatSecret строго для этого бренда и названия.\n\n"
            "3. Если на фото напиток в стакане или приготовленное блюдо на тарелке (без заводской упаковки):\n"
            "   Визуально определи примерный вес полной порции в граммах и максимально точно рассчитай КБЖУ. При необходимости найди похожие блюда в интернете (в том числе FatSecret), чтобы уточнить расчёт.\n\n"
            "4. Всегда указывай уверенность распознавания от 0.0 до 1.0, тип — drink (напитки, жидкости) или meal (еда, блюда). Название пиши на русском языке с большой буквы.\n\n"
            "5. Старайся давать схожие результаты при повторном анализе одного и того же блюда.\n\n"
            "Ответь строго в JSON без дополнительного текста:\n"
            '{"is_food":, "confidence":, "type":, "name": "", "serving":, "calories":, "protein":, "fat":, "carbs":}'
        )
    )
    sender = _chat if grade == "pro" else _completion
    content = await sender(
        [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    }
                ],
            },
        ]
    )
    if content in {"__RATE_LIMIT__", "__BAD_REQUEST__", "__ERROR__"}:
        return {"error": content.strip("_").lower()}
    try:
        data = json.loads(content)
        if 'serving' in data:
            data['serving'] = parse_serving(data['serving'])
        for k in ('calories', 'protein', 'fat', 'carbs'):
            if k in data:
                data[k] = to_float(data[k])
        if 'name' in data and isinstance(data['name'], str):
            data['name'] = data['name'].strip().capitalize()
        if 'type' in data and isinstance(data['type'], str):
            data['type'] = data['type'].lower()
        return data
    except Exception:
        match = re.search(r"\{.*\}", content, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {"error": "parse"}


async def analyze_text(description: str, grade: str = "pro") -> Dict[str, Any]:
    """Analyze a text description of a meal or drink."""
    if not client.api_key:
        return {
            "is_food": True,
            "confidence": 1.0,
            "name": description,
            "type": "meal",
            "serving": 200,
            "calories": 250,
            "protein": 15,
            "fat": 10,
            "carbs": 30,
        }
    prompt = (
        SIMPLE_TEXT_PROMPT
        if grade != "pro"
        else (
            "Ты — профессиональный диетолог/нутрициолог с большим опытом.\n"
            "Тебе придёт текстовое описание, и твоя задача:\n\n"
            "1. Определи, относится ли описание к готовой еде, напитку или продукту питания:\n"
            "   • Если нет — верни {\"is_food\": false}.\n\n"
            "2. Если в тексте упоминается товар с брендом или названием магазина:\n"
            "   Найди этот конкретный продукт в русскоязычной базе FatSecret (site:fatsecret.ru), обязательно используя точное название бренда и продукта.\n"
            "   • Используй КБЖУ и массу нетто порции из FatSecret строго для этого бренда и названия.\n\n"
            "3. Если в тексте описано приготовленное блюдо или напиток без упаковки:\n"
            "   Визуально (по описанию ингредиентов и объёмов) определи примерный вес порции и максимально точно рассчитай КБЖУ. При необходимости найди похожие блюда в интернете, в том числе на FatSecret.\n\n"
            "4. Всегда указывай уверенность распознавания от 0.0 до 1.0, тип — drink или meal, название по-русски с заглавной буквы.\n\n"
            "5. Старайся давать схожие результаты при повторном анализе одинаковых описаний.\n\n"
            "Ответь строго в JSON без лишнего текста:\n"
            '{"is_food":, "confidence":, "type":, "name":"", "serving":, "calories":, "protein":, "fat":, "carbs":}'
        )
    )
    sender = _chat if grade == "pro" else _completion
    content = await sender([
        {"role": "system", "content": prompt},
        {"role": "user", "content": description},
    ])
    if content in {"__RATE_LIMIT__", "__BAD_REQUEST__", "__ERROR__"}:
        return {"error": content.strip("_").lower()}
    try:
        data = json.loads(content)
        if 'serving' in data:
            data['serving'] = parse_serving(data['serving'])
        for k in ('calories', 'protein', 'fat', 'carbs'):
            if k in data:
                data[k] = to_float(data[k])
        if 'name' in data and isinstance(data['name'], str):
            data['name'] = data['name'].strip().capitalize()
        if 'type' in data and isinstance(data['type'], str):
            data['type'] = data['type'].lower()
        return data
    except Exception:
        match = re.search(r"\{.*\}", content, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {"error": "parse"}


async def analyze_text_with_hint(
    description: str,
    hint: str,
    prev: Optional[Dict[str, Any]] = None,
    hints: Optional[list[str]] = None,
    grade: str = "pro",
) -> Dict[str, Any]:
    """Clarify text description with additional hint."""
    if not client.api_key:
        return {
            "success": True,
            "name": hint,
            "type": "meal",
            "serving": 200,
            "calories": 250,
            "protein": 15,
            "fat": 10,
            "carbs": 30,
        }
    prev_json = json.dumps(prev or {}, ensure_ascii=False)
    hints_text = _format_hints(hints)
    prompt = (
        SIMPLE_HINT_PROMPT
        if grade != "pro"
        else (
            "Ты — профессиональный диетолог/нутрициолог. Ранее ты проанализировал текст и вернул такой JSON:\n"
            f"{prev_json}\n"
            f"{hints_text}Исходное описание: {description}\n"
            f"Теперь пользователь прислал уточнение: «{hint}».\n\n"
            "Твоя задача:\n"
            "1. Обнови информацию, если уточнение касается ингредиентов, состава, бренда, упаковки, веса или типа блюда/напитка.\n"
            "2. Если уточнение касается бренда или продукта в упаковке — найди соответствующий товар в русскоязычной базе FatSecret (site:fatsecret.ru) и обнови `serving`, `calories`, `protein`, `fat`, `carbs` по данным именно для этого бренда.\n"
            "3. Если уточнение касается состава блюда/напитка (например, \"творог 2%\", \"без сахара\", \"без масла\") — пересчитай КБЖУ, исключив или заменив указанные компоненты.\n"
            "4. Если уточнение касается веса:\n   • Если явно просят пересчитать КБЖУ — сделай это.\n   • Если сказано «измени только вес» — обнови только `serving`, КБЖУ оставь как есть.\n"
            "5. Если пользователь указывает сохранить конкретные параметры — обязательно зафиксируй их значение из предыдущего JSON.\n"
            "6. Всегда обновляй `confidence`, `name` и `type`.\n"
            "7. Если в уточнении нет новой информации — верни: {\"success\": false}\n"
            "8. Верни только один JSON строго по шаблону:\n"
            '{"success": true, "is_food": true, "confidence": <0–1>, "type": "<drink|meal>", "name": "<Название>", "serving": <граммы>, "calories": <ккал>, "protein": <г>, "fat": <г>, "carbs": <г>}'
        )
    )
    sender = _chat if grade == "pro" else _completion
    content = await sender([
        {"role": "system", "content": prompt},
        {"role": "user", "content": description},
    ])
    if content in {"__RATE_LIMIT__", "__BAD_REQUEST__", "__ERROR__"}:
        return {"error": content.strip("_").lower()}
    try:
        data = json.loads(content)
        if 'serving' in data:
            data['serving'] = parse_serving(data['serving'])
        for k in ('calories', 'protein', 'fat', 'carbs'):
            if k in data:
                data[k] = to_float(data[k])
        if 'name' in data and isinstance(data['name'], str):
            data['name'] = data['name'].strip().capitalize()
        if 'type' in data and isinstance(data['type'], str):
            data['type'] = data['type'].lower()
        return data
    except Exception:
        match = re.search(r"\{.*\}", content, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {"error": "parse"}


async def analyze_photo_with_hint(
    photo_path: str,
    hint: str,
    prev: Optional[Dict[str, Any]] = None,
    hints: Optional[list[str]] = None,
    grade: str = "pro",
) -> Dict[str, Any]:
    """Re-analyze a photo using user clarification about the dish or beverage."""
    if not client.api_key:
        # simple stub when API key is missing
        return {
            "success": True,
            "name": hint,
            "type": "meal",
            "serving": 200,
            "calories": 250,
            "protein": 15,
            "fat": 10,
            "carbs": 30,
        }
    with open(photo_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    prev_json = json.dumps(prev or {}, ensure_ascii=False)
    hints_text = _format_hints(hints)
    prompt = (
        SIMPLE_HINT_PROMPT
        if grade != "pro"
        else (
            "Ты — профессиональный диетолог/нутрициолог. Ранее ты проанализировал изображение и вернул такой JSON:\n"
            f"{prev_json}\n"
            f"{hints_text}Теперь пользователь прислал уточнение: «{hint}».\n\n"
            "Твоя задача:\n"
            "1. Обнови информацию, если уточнение касается ингредиентов, состава, бренда, упаковки, веса или типа блюда/напитка.\n"
            "2. Если уточнение касается бренда или продукта в упаковке — найди соответствующий товар в русскоязычной базе FatSecret (site:fatsecret.ru) и обнови `serving`, `calories`, `protein`, `fat`, `carbs` по данным именно для этого бренда.\n"
            "3. Если уточнение касается состава блюда/напитка (например, \"творог 2%\", \"без сахара\", \"без масла\") — пересчитай КБЖУ, исключив или заменив указанные компоненты.\n"
            "4. Если уточнение касается веса:\n   • Если явно просят пересчитать КБЖУ — сделай это.\n   • Если сказано «измени только вес» — обнови только `serving`, КБЖУ оставь как есть.\n"
            "5. Если пользователь указывает сохранить конкретные параметры — обязательно зафиксируй их значение из предыдущего JSON (например: «не меняй белки»).\n"
            "6. Всегда обновляй `confidence` (0.0–1.0), `name` (по-русски, с заглавной буквы), `type` (\"meal\" или \"drink\").\n"
            "7. Если в уточнении нет новой информации — верни: {\"success\": false}\n"
            "8. Верни только один JSON строго по шаблону:\n"
            '{"success": true, "is_food": true, "confidence": <0–1>, "type": "<drink|meal>", "name": "<Название>", "serving": <граммы>, "calories": <ккал>, "protein": <г>, "fat": <г>, "carbs": <г>}'
        )
    )
    sender = _chat if grade == "pro" else _completion
    content = await sender(
        [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    }
                ],
            },
        ]
    )
    if content in {"__RATE_LIMIT__", "__BAD_REQUEST__", "__ERROR__"}:
        return {"error": content.strip("_").lower()}
    try:
        data = json.loads(content)
        if 'serving' in data:
            data['serving'] = parse_serving(data['serving'])
        for k in ('calories', 'protein', 'fat', 'carbs'):
            if k in data:
                data[k] = to_float(data[k])
        if 'name' in data and isinstance(data['name'], str):
            data['name'] = data['name'].strip().capitalize()
        if 'type' in data and isinstance(data['type'], str):
            data['type'] = data['type'].lower()
        return data
    except Exception:
        match = re.search(r"\{.*\}", content, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {"error": "parse"}




