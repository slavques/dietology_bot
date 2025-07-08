import json
import base64
import re
import asyncio
from typing import Dict, List, Any, Optional
from .logger import log

import openai
from openai import RateLimitError, BadRequestError

from .config import OPENAI_API_KEY
from .utils import parse_serving, to_float
from .prompts import (
    PRO_PHOTO_PROMPT,
    FREE_PHOTO_PROMPT,
    PRO_TEXT_PROMPT,
    FREE_TEXT_PROMPT,
    PRO_HINT_PROMPT_BASE,
    FREE_HINT_PROMPT_BASE,
)

client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Model names for different API methods
MODEL_NAME = "gpt-4o-mini"  # used with the Responses API
COMPLETION_MODEL = "gpt-4o-mini"  # weaker model for Completions


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
        log("prompt", "%s", system_msg)
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
            log("response", "%s", content)
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
    messages: List[Dict], model: str = COMPLETION_MODEL, retries: int = 3, backoff: float = 0.5
) -> str:
    """Call the legacy Completions API for non‑PRO tiers."""
    if not client.api_key:
        return ""
    try:
        system_msg = next(m["content"] for m in messages if m.get("role") == "system")
        log("prompt", "%s", system_msg)
    except Exception:
        system_msg = None
    prompt_parts = []
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            for part in c:
                if part.get("type") == "text":
                    prompt_parts.append(part["text"])
        elif isinstance(c, str):
            prompt_parts.append(c)
    prompt = "\n".join(prompt_parts)
    for attempt in range(retries):
        try:
            resp = await client.completions.create(
                model=model,
                prompt=prompt,
                temperature=0.2,
                max_tokens=350,
                top_p=0.9,
            )
            content = resp.choices[0].text
            log("response", "%s", content)
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
    prompt = PRO_PHOTO_PROMPT if grade == "pro" else FREE_PHOTO_PROMPT
    # The Completions API does not support images, so we always use
    # the Responses API for photo analysis regardless of user tier.
    sender = _chat
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
    prompt = PRO_TEXT_PROMPT if grade == "pro" else FREE_TEXT_PROMPT
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
    hints_text = _format_hints(hints)
    if prev:
        context = f"Ранее ты проанализировал текст и вернул такой JSON:\n{json.dumps(prev, ensure_ascii=False)}"
    else:
        context = "Предыдущего JSON нет."
    base = PRO_HINT_PROMPT_BASE if grade == "pro" else FREE_HINT_PROMPT_BASE
    prompt = base.format(
        context=context,
        hints=hints_text,
        hint=hint,
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
    hints_text = _format_hints(hints)
    if prev:
        context = f"Ранее ты проанализировал изображение и вернул такой JSON:\n{json.dumps(prev, ensure_ascii=False)}"
    else:
        context = "Предыдущего JSON нет."
    base = PRO_HINT_PROMPT_BASE if grade == "pro" else FREE_HINT_PROMPT_BASE
    prompt = base.format(
        context=context,
        hints=hints_text,
        hint=hint,
    )
    # As with the initial photo analysis, hints with photos must always use
    # the Responses API since the Completions endpoint cannot process images.
    sender = _chat
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




