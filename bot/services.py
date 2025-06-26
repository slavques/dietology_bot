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




async def analyze_photo(photo_path: str) -> Dict[str, Any]:
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
        "Ты диетолог/нутрициолог. "
        "Определи, есть ли еда на фото. Если еды нет, верни JSON "
        "{\"is_food\": false}. Если еда есть, назови блюдо по-русски с большой буквы, "
        "оцени уверенность распознавания (0-1), укажи примерный вес полной порции "
        "в граммах целым числом, определи тип — drink или meal, и расчитай калории, белки, жиры и углеводы. "
        "При необходимости используй поиск в интернете для более точной оценки. "
        "Старайся давать схожие результаты при повторном анализе одного и того же блюда. "
        "Ответ только JSON вида {is_food, confidence, type, name, serving, calories, protein, fat, carbs}."
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


async def analyze_photo_with_hint(photo_path: str, hint: str, prev: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
    prompt = (
        "Ты — ассистент-диетолог с поддержкой анализа изображений. "
        "Тебе придут три элемента:\n"
        "1) фото блюда или напитка,\n"
        "2) предыдущий JSON-анализ,\n"
        "3) уточнение пользователя.\n\n"
        "Инструкции:\n"
        "1. Объедини визуальные данные, предыдущий JSON и уточнение.\n"
        "2. Название пиши по-русски с заглавной буквы.\n"
        "3. Укажи примерный вес порции в граммах (целое число).\n"
        "4. Определи тип — drink или meal.\n"
        "5. Рассчитай КБЖУ: calories (ккал), protein, fat, carbs (в граммах).\n"
        "6. Верни только один JSON:\n"
        '{"success": true, "type": "drink", "name": "<Название>", "serving": <Вес>, "calories": <Ккал>, "protein": <Белки>, "fat": <Жиры>, "carbs": <Углеводы>}\n'
        "Если в уточнении нет новой информации о блюде/напитке, верни: {\"success\": false}.\n"
        "При необходимости используй поиск в интернете для более точной оценки"
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
            {"role": "user", "content": "Previous analysis:\n" + prev_json},
            {"role": "user", "content": "User clarification:\n" + hint},
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




