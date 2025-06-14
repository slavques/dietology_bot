from typing import Dict, List

# Stub implementations of AI helpers
async def classify_food(photo_path: str) -> Dict[str, float]:
    """Detect food vs non-food."""
    return {"is_food": True, "confidence": 0.9}

async def recognize_dish(photo_path: str) -> Dict[str, any]:
    """Recognize dish name and ingredients."""
    return {
        "name": "Sample dish",
        "ingredients": ["ingredient1", "ingredient2"],
        "serving": 150,
    }

async def calculate_macros(ingredients: List[str], serving: float) -> Dict[str, float]:
    """Calculate macros for given ingredients."""
    return {"calories": 250, "protein": 20, "fat": 10, "carbs": 30}
