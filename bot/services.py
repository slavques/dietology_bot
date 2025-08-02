import json
import base64
import re
import asyncio
from typing import Dict, List, Any, Optional
import requests
from bs4 import BeautifulSoup
from .logger import log

import openai
from openai import RateLimitError, BadRequestError

from .config import OPENAI_API_KEY
from .utils import parse_serving, to_float
from .prompts import (
    PRO_PHOTO_PROMPT,
    LIGHT_PHOTO_PROMPT,
    FREE_PHOTO_PROMPT,
    PRO_TEXT_PROMPT,
    LIGHT_TEXT_PROMPT,
    FREE_TEXT_PROMPT,
    PRO_HINT_PROMPT_BASE,
    LIGHT_HINT_PROMPT_BASE,
    FREE_HINT_PROMPT_BASE,
)
from .alerts import token_monitor, gpt_error

client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
GPT_SEMAPHORE = asyncio.Semaphore(3)

# Model names for different API methods
MODEL_NAME = "gpt-4.1-mini"
COMPLETION_MODEL = "gpt-4.1-mini"


async def fatsecret_search(query: str) -> List[Dict[str, Any]]:
    """Return up to three search results with macros per 100 g."""
    log("google", "search %s", query)
    loop = asyncio.get_running_loop()
    try:
        url = "http://www.fatsecret.ru/калории-питание/search"
        resp = await loop.run_in_executor(
            None,
            lambda: requests.get(
                url,
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0"},
                verify=False,
                timeout=10,
            ),
        )
        log("google", "request %s status %s", resp.url, resp.status_code)
        soup = BeautifulSoup(resp.text, "html.parser")
        items: List[Dict[str, Any]] = []
        for tr in soup.select("table.searchResult tr"):
            link = tr.select_one("a.prominent")
            info = tr.select_one("div.smallText")
            if not link or not info:
                continue
            text = info.get_text(" ", strip=True)
            weight = None
            m = re.search(
                r"100\s*(?:г|гр)[^\d]*(\d+(?:[\.,]\d+)?)\s*ккал[^\d]*Жир[^\d]*(\d+(?:[\.,]\d+)?)\s*г[^\d]*Углев[^\d]*(\d+(?:[\.,]\d+)?)\s*г[^\d]*Белк[^\d]*(\d+(?:[\.,]\d+)?)\s*г",
                text,
                re.I,
            )
            if not m:
                m = re.search(
                    r"Калории[^\d]*(\d+(?:[\.,]\d+)?)\s*ккал[^\d]*Жир[^\d]*(\d+(?:[\.,]\d+)?)\s*г[^\d]*Углев[^\d]*(\d+(?:[\.,]\d+)?)\s*г[^\d]*Белк[^\d]*(\d+(?:[\.,]\d+)?)\s*г",
                    text,
                    re.I,
                )
                if m:
                    w = re.search(
                        r"1\s*(?:порц[аия]|шт\.?|бургер)[^\d]*(\d+(?:[\.,]\d+)?)\s*(?:г|гр)",
                        text,
                        re.I,
                    )
                    if w:
                        weight = parse_serving(w.group(1))
            if not m:
                continue
            calories, fat, carbs, protein = m.groups()
            item = {
                "name": link.get_text(strip=True),
                "calories": to_float(calories),
                "protein": to_float(protein),
                "fat": to_float(fat),
                "carbs": to_float(carbs),
            }
            if weight:
                item["serving"] = weight
            items.append(item)
            if len(items) >= 3:
                break
        log("google", "results %s", len(items))
        return items
    except Exception as exc:
        log("google", "search failed: %s", exc)
        return []




async def fatsecret_lookup(query: str) -> Optional[Dict[str, Any]]:
    """Return macros for the first FatSecret result, preferring a serving link."""
    log("google", "query %s", query)
    loop = asyncio.get_running_loop()
    try:
        search_url = "http://www.fatsecret.ru/калории-питание/search"
        page = await loop.run_in_executor(
            None,
            lambda: requests.get(
                search_url,
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0"},
                verify=False,
                timeout=10,
            ),
        )
        log("google", "request %s status %s", page.url, page.status_code)
        soup = BeautifulSoup(page.text, "html.parser")

        row = None
        for tr in soup.select("table.searchResult tr"):
            link = tr.select_one("a.prominent")
            href = link.get("href", "") if link else ""
            if href and "100" in href and ("%D0%B3" in href or "g" in href.lower()):
                continue
            if link:
                row = tr
                break
        if not row:
            row = soup.select_one("table.searchResult tr")
        if not row:
            return None

        link = row.select_one("a.prominent")
        item_name = link.get_text(strip=True) if link else query
        href = link.get("href", "") if link else ""
        log("google", "link %s", href)
        item_url = (
            "http://www.fatsecret.ru" + href if href.startswith("/") else href
        )
        item_page = await loop.run_in_executor(
            None,
            lambda: requests.get(
                item_url,
                headers={"User-Agent": "Mozilla/5.0"},
                verify=False,
                timeout=10,
            ),
        )
        log("google", "page %s status %s", item_page.url, item_page.status_code)
        soup_item = BeautifulSoup(item_page.text, "html.parser")
        panel = soup_item.select_one("div.nutrition_facts")
        text = panel.get_text(" ", strip=True) if panel else soup_item.get_text(" ", strip=True)
        log("google", "response %.120s", text)

        m = re.search(
            r"Калории[^\d]*(\d+(?:[\.,]\d+)?)\s*ккал[^\d]*Жир[^\d]*(\d+(?:[\.,]\d+)?)\s*г[^\d]*Углев[^\d]*(\d+(?:[\.,]\d+)?)\s*г[^\d]*Белк[^\d]*(\d+(?:[\.,]\d+)?)\s*г",
            text,
            re.I | re.S,
        )
        if not m:
            return None
        calories, fat, carbs, protein = m.groups()
        macros = {
            "calories": to_float(calories),
            "protein": to_float(protein),
            "fat": to_float(fat),
            "carbs": to_float(carbs),
        }
        log("google", "macros %s", macros)
        return {"name": item_name, **macros}
    except Exception as exc:
        log("google", "lookup failed: %s", exc)
        return None


async def _chat_completion(
    messages: List[Dict],
    model: str = COMPLETION_MODEL,
    retries: int = 3,
    backoff: float = 0.5,
) -> tuple[str, int, int]:
    """Call the Chat Completions API without web search."""
    if not client.api_key:
        return "", 0, 0
    try:
        system_msg = next(
            m["content"] for m in messages if m.get("role") == "system"
        )
        log("prompt", "%s", system_msg)
    except Exception:
        pass
    for attempt in range(retries):
        try:
            async with GPT_SEMAPHORE:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=1000,
                    top_p=0.7,
                )
            content = resp.choices[0].message.content
            log("response", "%s", content)
            usage = getattr(resp, "usage", None)
            tokens_in = tokens_out = 0
            if usage:
                tokens_in = getattr(
                    usage,
                    "prompt_tokens",
                    getattr(usage, "input_tokens", None),
                ) or 0
                tokens_out = getattr(
                    usage,
                    "completion_tokens",
                    getattr(usage, "output_tokens", None),
                ) or 0
                log(
                    "tokens",
                    "in=%s out=%s total=%s",
                    tokens_in,
                    tokens_out,
                    usage.total_tokens,
                )
            return content, tokens_in, tokens_out
        except RateLimitError as exc:
            if attempt < retries - 1:
                await asyncio.sleep(backoff * (2**attempt))
                continue
            await gpt_error(str(exc))
            return "__RATE_LIMIT__", 0, 0
        except BadRequestError as exc:
            await gpt_error(str(exc))
            return "__BAD_REQUEST__", 0, 0
        except Exception as exc:
            await gpt_error(str(exc))
            return "__ERROR__", 0, 0


async def _completion(
    messages: List[Dict],
    model: str = COMPLETION_MODEL,
    retries: int = 3,
    backoff: float = 0.5,
) -> tuple[str, int, int]:
    """Call the legacy Completions API for non‑PRO tiers."""
    if not client.api_key:
        return "", 0, 0
    try:
        system_msg = next(
            m["content"] for m in messages if m.get("role") == "system"
        )
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
            async with GPT_SEMAPHORE:
                resp = await client.completions.create(
                    model=model,
                    prompt=prompt,
                    temperature=0.2,
                    max_tokens=1000,
                    top_p=0.7,
                )
            content = resp.choices[0].text
            log("response", "%s", content)
            usage = getattr(resp, "usage", None)
            tokens_in = tokens_out = 0
            if usage:
                tokens_in = getattr(
                    usage,
                    "prompt_tokens",
                    getattr(usage, "input_tokens", None),
                ) or 0
                tokens_out = getattr(
                    usage,
                    "completion_tokens",
                    getattr(usage, "output_tokens", None),
                ) or 0
                log(
                    "tokens",
                    "in=%s out=%s total=%s",
                    tokens_in,
                    tokens_out,
                    usage.total_tokens,
                )
            return content, tokens_in, tokens_out
        except RateLimitError as exc:
            if attempt < retries - 1:
                await asyncio.sleep(backoff * (2**attempt))
                continue
            await gpt_error(str(exc))
            return "__RATE_LIMIT__", 0, 0
        except BadRequestError as exc:
            await gpt_error(str(exc))
            return "__BAD_REQUEST__", 0, 0
        except Exception as exc:
            await gpt_error(str(exc))
            return "__ERROR__", 0, 0


async def analyze_photo(photo_path: str, grade: str = "pro") -> List[Dict[str, Any]]:
    """Analyze photo in a single GPT request and return dish info and macros."""
    if not client.api_key:
        return [
            {
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
        ]
    try:
        with open(photo_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return {"error": "missing_photo"}
    prompt = PRO_PHOTO_PROMPT
    sender = _chat_completion
    content, tokens_in, tokens_out = await sender(
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
    await token_monitor.add(tokens_in, tokens_out)
    if content in {"__RATE_LIMIT__", "__BAD_REQUEST__", "__ERROR__"}:
        return [{"error": content.strip("_").lower()}]
    try:
        raw = json.loads(content)
        items = raw if isinstance(raw, list) else [raw]
        results: List[Dict[str, Any]] = []
        for data in items:
            if "serving" in data:
                data["serving"] = parse_serving(data["serving"])
            for k in ("calories", "protein", "fat", "carbs"):
                if k in data:
                    data[k] = to_float(data[k])
            if "name" in data and isinstance(data["name"], str):
                data["name"] = data["name"].strip().capitalize()
            if "type" in data and isinstance(data["type"], str):
                data["type"] = data["type"].lower()
            results.append(data)
        return results
    except Exception:
        match = re.findall(r"\{.*?\}", content, re.S)
        if match:
            results = []
            for m in match:
                try:
                    results.append(json.loads(m))
                except Exception:
                    continue
            if results:
                return results
        return [{"error": "parse"}]


async def analyze_text(description: str, grade: str = "pro") -> List[Dict[str, Any]]:
    """Analyze a text description of a meal or drink."""
    if not client.api_key:
        return [
            {
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
        ]
    prompt = PRO_TEXT_PROMPT
    sender = _chat_completion
    content, tokens_in, tokens_out = await sender(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": description},
        ]
    )
    await token_monitor.add(tokens_in, tokens_out)
    if content in {"__RATE_LIMIT__", "__BAD_REQUEST__", "__ERROR__"}:
        return [{"error": content.strip("_").lower()}]
    try:
        raw = json.loads(content)
        items = raw if isinstance(raw, list) else [raw]
        results: List[Dict[str, Any]] = []
        for data in items:
            if "serving" in data:
                data["serving"] = parse_serving(data["serving"])
            for k in ("calories", "protein", "fat", "carbs"):
                if k in data:
                    data[k] = to_float(data[k])
            if "name" in data and isinstance(data["name"], str):
                data["name"] = data["name"].strip().capitalize()
            if "type" in data and isinstance(data["type"], str):
                data["type"] = data["type"].lower()
            results.append(data)
        return results
    except Exception:
        match = re.findall(r"\{.*?\}", content, re.S)
        if match:
            results = []
            for m in match:
                try:
                    results.append(json.loads(m))
                except Exception:
                    continue
            if results:
                return results
        return [{"error": "parse"}]


async def analyze_text_with_hint(
    description: str,
    hint: str,
    grade: str = "pro",
) -> Dict[str, Any]:
    """Clarify text description with additional hint using the original text."""
    if not client.api_key:
        return {
            "is_food": True,
            "name": hint,
            "type": "meal",
            "serving": 200,
            "calories": 250,
            "protein": 15,
            "fat": 10,
            "carbs": 30,
        }
    context = f"Текст из первого запроса: {description}"
    base = PRO_HINT_PROMPT_BASE
    prompt = base.format(
        context=context.replace("{", "{{").replace("}", "}}"),
        hint=hint.replace("{", "{{").replace("}", "}}"),
    )
    sender = _chat_completion
    content, tokens_in, tokens_out = await sender(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": description},
        ]
    )
    await token_monitor.add(tokens_in, tokens_out)
    if content in {"__RATE_LIMIT__", "__BAD_REQUEST__", "__ERROR__"}:
        return {"error": content.strip("_").lower()}
    try:
        raw = json.loads(content)
        items = raw if isinstance(raw, list) else [raw]
        if not items:
            return {"error": "parse"}
        data = items[0]
        if "serving" in data:
            data["serving"] = parse_serving(data["serving"])
        for k in ("calories", "protein", "fat", "carbs"):
            if k in data:
                data[k] = to_float(data[k])
        if "name" in data and isinstance(data["name"], str):
            data["name"] = data["name"].strip().capitalize()
        if "type" in data and isinstance(data["type"], str):
            data["type"] = data["type"].lower()
        return data
    except Exception:
        match = re.findall(r"\{.*?\}", content, re.S)
        if match:
            try:
                data = json.loads(match[0])
            except Exception:
                return {"error": "parse"}
            if "serving" in data:
                data["serving"] = parse_serving(data["serving"])
            for k in ("calories", "protein", "fat", "carbs"):
                if k in data:
                    data[k] = to_float(data[k])
            if "name" in data and isinstance(data["name"], str):
                data["name"] = data["name"].strip().capitalize()
            if "type" in data and isinstance(data["type"], str):
                data["type"] = data["type"].lower()
            return data
        return {"error": "parse"}


async def analyze_photo_with_hint(
    photo_path: str,
    hint: str,
    grade: str = "pro",
    context_json: Optional[Dict[str, Any]] = None,
    all_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Re-analyze a photo using user clarification about the dish or beverage."""
    if not client.api_key:
        # simple stub when API key is missing
        return {
            "is_food": True,
            "name": hint,
            "type": "meal",
            "serving": 200,
            "calories": 250,
            "protein": 15,
            "fat": 10,
            "carbs": 30,
        }
    try:
        with open(photo_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return {"error": "missing_photo"}
    context = "Фото из первого запроса"
    if context_json:
        context += f". Ранее распознано: {context_json.get('name', '')}"
    if all_names:
        context += f" среди других: {', '.join(all_names)}"
    if grade == "pro":
        base = PRO_HINT_PROMPT_BASE
    elif grade == "light":
        base = LIGHT_HINT_PROMPT_BASE
    else:
        base = FREE_HINT_PROMPT_BASE
    prompt = base.format(
        context=context.replace("{", "{{").replace("}", "}}"),
        hint=hint.replace("{", "{{").replace("}", "}}"),
    )
    sender = _chat_completion
    content, tokens_in, tokens_out = await sender(
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
    await token_monitor.add(tokens_in, tokens_out)
    if content in {"__RATE_LIMIT__", "__BAD_REQUEST__", "__ERROR__"}:
        return {"error": content.strip("_").lower()}
    try:
        raw = json.loads(content)
        items = raw if isinstance(raw, list) else [raw]
        if not items:
            return {"error": "parse"}
        data = items[0]
        if "serving" in data:
            data["serving"] = parse_serving(data["serving"])
        for k in ("calories", "protein", "fat", "carbs"):
            if k in data:
                data[k] = to_float(data[k])
        if "name" in data and isinstance(data["name"], str):
            data["name"] = data["name"].strip().capitalize()
        if "type" in data and isinstance(data["type"], str):
            data["type"] = data["type"].lower()
        return data
    except Exception:
        match = re.findall(r"\{.*?\}", content, re.S)
        if match:
            try:
                data = json.loads(match[0])
            except Exception:
                return {"error": "parse"}
            if "serving" in data:
                data["serving"] = parse_serving(data["serving"])
            for k in ("calories", "protein", "fat", "carbs"):
                if k in data:
                    data[k] = to_float(data[k])
            if "name" in data and isinstance(data["name"], str):
                data["name"] = data["name"].strip().capitalize()
            if "type" in data and isinstance(data["type"], str):
                data["type"] = data["type"].lower()
            return data
        return {"error": "parse"}
