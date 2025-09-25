from pathlib import Path

# Configuration for frequently changed parameters

# Telegram support bot username
SUPPORT_HANDLE = "@nomnomly_support"

# Prices for subscription plans in RUB
PLAN_PRICES = {
    "1m": 159,
    "3m": 399,
    "6m": 799,
}

# Discounted prices for promotions in RUB
DISCOUNT_PLAN_PRICES = {
    "1m": 119,
    "3m": 299,
    "6m": 549,
}

# Prices for PRO subscription in RUB
PRO_PLAN_PRICES = {
    "1m": 500,
    "3m": 1400,
    "6m": 2600,
}

# Link to FAQ article
FAQ_LINK = "https://telegra.ph/CHaVO--AI-Dietolog-Bot-08-02"

# Directory with static assets that can be sent to users
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Filename of the illustration that accompanies the body fat question
GOAL_BODY_FAT_IMAGE_NAME = "goal_body_fat.png"
