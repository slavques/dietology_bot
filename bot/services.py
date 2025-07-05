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
MODEL_NAME = "gpt-4o"


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
                max_output_tokens=200,
                temperature=0.2,
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
        "Ты — профессиональный диетолог/нутрициолог с большим опытом. Тебе придёт изображение, и твоя задача:\n\n"
        "Определи, есть ли на фото готовая еда или напиток.\n"
        "• Если нет — верни {\"is_food\": false}.\n\n"
        "Если на фото товар в заводской упаковке (банка, бутылка, контейнер и т. п.) — найди этот продукт в русскоязычной базе FatSecret (site:fatsecret.ru) и возьми оттуда массу нетто и КБЖУ на всю порцию.\n\n"
        "Если на фото напиток или приготовленное блюдо — оцени визуально примерный вес порции в граммах и рассчитай КБЖУ.\n\n"
        "Оцени уверенность распознавания от 0.0 до 1.0. Тип определи drink (напитки, жидкости) это или meal (еда, блюда). Название пиши на русском языке с большой буквы\n\n"
        "Ответь только одним JSON:\n"
        '{"is_food":, "confidence":, "type":, "name": "", "serving":, "calories":, "protein":, "fat":, "carbs":}'
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
        "Ты — профессиональный диетолог/нутрициолог. Ранее ты проанализировал фото и вернул JSON:\n"
        f"{prev_json}\n"
        f"Теперь пользователь прислал уточнение: «{hint}».\n\n"
        "Твоя задача:\n"
        "1. Игнорируй любые упоминания о технических деталях — только визуальный контекст и текст.\n"
        "2. Если уточнение меняет название блюда/напитка — обнови `name` (по-русски, с заглавной буквы).\n"
        "3. Если просят поменять вес, то просто обнови `serving` без перерасчета кбжу. А если просят поменять вес и сделать перерасчет явно, то делай полный перерасчет.\n"
        "4. Если уточнение добавляет или уточняет ингредиенты или указывает на заводскую упаковку — скорректируй `type` и возьми массу нетто из FatSecret (для упакованного товара).\n"
        "5. Пересчитай с точностью до десятых `calories`, `protein`, `fat`, `carbs`.\n"
        "6. Оцени новую `confidence` (0.0–1.0).\n"
        "7. Верни только один JSON:\n"
        '{"success": true, "is_food": true, "confidence": <0–1>, "type": "<drink|meal>", "name": "<Название>", "serving": <граммы>, "calories": <ккал>, "protein": <г>, "fat": <г>, "carbs": <г>}\n'
        "8. Если в уточнении нет никакой новой информации, верни:\n"
        '{"success": false}'
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




