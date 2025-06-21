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


async def _chat(messages: List[Dict], retries: int = 3, backoff: float = 0.5) -> str:
    if not client.api_key:
        return ""
    # Log the prompt being sent to OpenAI for easier debugging
    try:
        system_msg = next(m["content"] for m in messages if m.get("role") == "system")
        logging.info("OpenAI prompt: %s", system_msg)
    except Exception:
        pass
    for attempt in range(retries):
        try:
            resp = await client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=200,
                temperature=0.2,
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


async def classify_food(photo_path: str) -> Dict[str, Any]:
    """Determine if the photo contains food and return confidence."""
    if not client.api_key:
        return {"is_food": True, "confidence": 1.0}
    with open(photo_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    prompt = (
        "Определи, есть ли еда на изображении. Ответ только JSON вида "
        "{is_food, confidence}."
    )
    content = await _chat([
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        },
    ])
    if content in {"__RATE_LIMIT__", "__BAD_REQUEST__", "__ERROR__"}:
        return {"error": content.strip("_").lower()}
    try:
        data = json.loads(content)
        if 'serving' in data:
            data['serving'] = parse_serving(data['serving'])
        if 'calories' in data:
            data['calories'] = to_float(data['calories'])
        if 'protein' in data:
            data['protein'] = to_float(data['protein'])
        if 'fat' in data:
            data['fat'] = to_float(data['fat'])
        if 'carbs' in data:
            data['carbs'] = to_float(data['carbs'])
        if 'name' in data and isinstance(data['name'], str):
            data['name'] = data['name'].strip().capitalize()
        return data
    except Exception:
        match = re.search(r"\{.*\}", content, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {"error": "parse"}


async def recognize_dish(photo_path: str) -> Dict[str, Any]:
    """Recognize dish name, ingredients and serving from a photo."""
    if not client.api_key:
        return {"name": "Пример блюда", "ingredients": ["ингредиент"], "serving": 200}
    with open(photo_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    prompt = (
        "Определи название блюда на русском и основные ингредиенты. "
        "Примерный вес порции в граммах. "
        "Ответ только JSON вида {name, ingredients, serving}."
    )
    content = await _chat([
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        },
    ])
    if content in {"__RATE_LIMIT__", "__BAD_REQUEST__", "__ERROR__"}:
        return {"error": content.strip("_").lower()}
    try:
        data = json.loads(content)
        if 'serving' in data:
            data['serving'] = parse_serving(data['serving'])
        if 'calories' in data:
            data['calories'] = to_float(data['calories'])
        if 'protein' in data:
            data['protein'] = to_float(data['protein'])
        if 'fat' in data:
            data['fat'] = to_float(data['fat'])
        if 'carbs' in data:
            data['carbs'] = to_float(data['carbs'])
        if 'name' in data and isinstance(data['name'], str):
            data['name'] = data['name'].strip().capitalize()
        return data
    except Exception:
        match = re.search(r"\{.*\}", content, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {"error": "parse"}


async def analyze_photo(photo_path: str) -> Dict[str, Any]:
    """Analyze photo in a single GPT request and return dish info and macros."""
    if not client.api_key:
        return {
            "is_food": True,
            "confidence": 1.0,
            "name": "Пример блюда",
            "serving": 200,
            "calories": 250,
            "protein": 15,
            "fat": 10,
            "carbs": 30,
        }
    with open(photo_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    prompt = (
        "Ты диетолог/нутрициолог. "
        "Определи, есть ли еда на фото. Если еды нет, верни JSON "
        "{\"is_food\": false}. Если еда есть, назови блюдо по-русски с большой буквы, "
        "оцени уверенность распознавания (0-1), укажи примерный вес полной порции "
        "в граммах целым числом и расчитай калории, белки, жиры и углеводы. "
        "При необходимости используй поиск в интернете для более точной оценки. "
        "Старайся давать схожие результаты при повторном анализе одного и того же блюда. "
        "Ответ только JSON вида {is_food, confidence, name, serving, calories, protein, fat, carbs}."
    )
    content = await _chat(
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
        for k in ('calories', 'protein', 'fat', 'carbs'):
            if k in data:
                data[k] = to_float(data[k])
        return data
    except Exception:
        match = re.search(r"\{.*\}", content, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {"error": "parse"}


async def analyze_photo_with_hint(photo_path: str, hint: str, prev: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Re-analyze photo using user clarification text."""
    if not client.api_key:
        # simple stub when API key is missing
        return {
            "success": True,
            "name": hint,
            "serving": 200,
            "calories": 250,
            "protein": 15,
            "fat": 10,
            "carbs": 30,
        }
    with open(photo_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    prev_json = json.dumps(prev or {}, ensure_ascii=False)
    prompt = (
        "Ты диетолог/нутрициолог. Пользователь уточняет блюдо на фото: "
        f"{hint}. Предыдущие данные анализа: {prev_json}. "
        "Сравни текст с изображением и, если уточнение относится к блюду, "
        "обнови название, вес и подсчитай калории, белки, жиры и углеводы. "
        "При необходимости используй поиск в интернете для более точных расчётов. "
        "Название верни на русском с большой буквы, вес укажи целым числом в граммах "
        "за всю порцию. Старайся выдавать близкие значения при повторной проверке того же фото. "
        "Если уточнение не относится к еде, ответь JSON {success: false}. "
        "В остальных случаях ответь только JSON вида "
        "{success: true, name, serving, calories, protein, fat, carbs}."
    )
    content = await _chat(
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
        return json.loads(content)
    except Exception:
        match = re.search(r"\{.*\}", content, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {"error": "parse"}


async def calculate_macros(ingredients: List[str], serving: float) -> Dict[str, float]:
    """Calculate approximate macros for a dish using GPT-4o."""
    if not client.api_key:
        return {"calories": 250, "protein": 20, "fat": 10, "carbs": 30}
    prompt = (
        "Рассчитай приблизительные калории, белки, жиры и углеводы для блюда "
        f"из ингредиентов {', '.join(ingredients)} весом {serving} г. "
        "Ответ только JSON вида {calories, protein, fat, carbs}."
    )
    content = await _chat([{"role": "system", "content": prompt}])
    if content in {"__RATE_LIMIT__", "__BAD_REQUEST__", "__ERROR__"}:
        return {"error": content.strip("_").lower()}
    try:
        return json.loads(content)
    except Exception:
        match = re.search(r"\{.*\}", content, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {"calories": 0, "protein": 0, "fat": 0, "carbs": 0}


