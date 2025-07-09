import argparse
import asyncio
import os
import json

from bot.services import (
    analyze_photo,
    analyze_photo_with_hint,
    analyze_text,
    analyze_text_with_hint,
)


def print_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


async def main():
    parser = argparse.ArgumentParser(description="Test analysis prompts")
    parser.add_argument("source", help="Photo path or text to analyze")
    parser.add_argument("--hint", help="Clarification text", default=None)
    parser.add_argument(
        "--text",
        action="store_true",
        help="Treat source as text instead of photo",
    )
    args = parser.parse_args()

    if args.text:
        if args.hint:
            result = await analyze_text_with_hint(args.source, args.hint)
        else:
            result = await analyze_text(args.source)
    else:
        if not os.path.exists(args.source):
            parser.error(f"File not found: {args.source}")
        if args.hint:
            result = await analyze_photo_with_hint(args.source, args.hint)
        else:
            result = await analyze_photo(args.source)

    print_json(result)


if __name__ == "__main__":
    asyncio.run(main())
