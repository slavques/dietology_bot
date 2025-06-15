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


async def classify_food(photo_path: str) -> Dict[str, float]:
    """Detect food vs non-food using GPT-4o. Returns JSON."""
    if not client.api_key:
        return {"is_food": True, "confidence": 0.9}
    with open(photo_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    content = await _chat([
        {
            "role": "system",
            "content": (
                "Определи, изображена ли еда на фото. "
                "Ответ только JSON вида {\"is_food\": bool, \"confidence\": 0-1}."
            ),
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{b64}",
                }
            ],
        },
    ])

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
        return {"is_food": False, "confidence": 0.0}


async def recognize_dish(photo_path: str) -> Dict[str, any]:
    """Recognize dish name and ingredients via GPT-4o."""
    if not client.api_key:
        return {
            "name": "Sample dish",
            "ingredients": ["ingredient1", "ingredient2"],
            "serving": 150,
        }
    with open(photo_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    content = await _chat([
        {
            "role": "system",
            "content": (
                "Определи блюдо на фото и перечисли основные ингредиенты "
                "и примерный вес порции в граммах. "
                "Ответ только JSON вида {name, ingredients, serving}."
            ),
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{b64}",
                }
            ],
        },
    ])

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
        return {"name": None, "ingredients": [], "serving": 0}


async def calculate_macros(ingredients: List[str], serving: float) -> Dict[str, float]:
    """Calculate approximate macros via GPT-4o."""
    if not client.api_key:
        return {"calories": 250, "protein": 20, "fat": 10, "carbs": 30}
    prompt = (
        "Рассчитай приблизительные калории, белки, жиры и углеводы для блюда "
        f"из ингредиентов {', '.join(ingredients)} весом {serving} г. "
        "Ответ только JSON вида {calories, protein, fat, carbs}."
    )
    content = await _chat([
        {"role": "system", "content": prompt}
    ])

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
