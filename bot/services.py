import json
import base64
import re
import asyncio
from typing import Dict, List

import openai
from openai import RateLimitError, BadRequestError

from .config import OPENAI_API_KEY

client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)


async def _chat(messages: List[Dict], retries: int = 3, backoff: float = 0.5) -> str:
    if not client.api_key:
        return ""
    for attempt in range(retries):
        try:
            resp = await client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=200,
            )
            return resp.choices[0].message.content
        except RateLimitError:
            if attempt < retries - 1:
                await asyncio.sleep(backoff * (2 ** attempt))
                continue
            return "__RATE_LIMIT__"
        except BadRequestError:
            return "__BAD_REQUEST__"
        except Exception:
            return "__ERROR__"


async def analyze_photo(photo_path: str) -> Dict[str, any]:
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
        "Определи, есть ли еда на фото. Если еды нет, верни JSON "
        "{\"is_food\": false}. Если еда есть, назови блюдо по-русски, "
        "оцени уверенность распознавания в диапазоне 0-1, приблизительный "
        "вес порции и расчитай калории, белки, жиры и углеводы. "
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
        return json.loads(content)
    except Exception:
        match = re.search(r"\{.*\}", content)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {"error": "parse"}


async def analyze_photo_with_hint(photo_path: str, hint: str) -> Dict[str, any]:
    """Re-analyze photo using user clarification text."""
    if not client.api_key:
        # simple stub when API key is missing
        return {
            "name": hint,
            "serving": 200,
            "calories": 250,
            "protein": 15,
            "fat": 10,
            "carbs": 30,
        }
    with open(photo_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    prompt = (
        "Ты диетолог. На фото изображено блюдо. Пользователь уточнил: "
        f"{hint}. Используя это уточнение, определи название блюда по-русски, "
        "примерный вес порции и рассчитай калории, белки, жиры и углеводы. "
        "Ответ только JSON вида {name, serving, calories, protein, fat, carbs}."
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
        match = re.search(r"\{.*\}", content)
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
        match = re.search(r"\{.*\}", content)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {"calories": 0, "protein": 0, "fat": 0, "carbs": 0}


