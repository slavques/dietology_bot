LOG_FLAGS = {
    # OpenAI prompts sent for analysis or clarifications
    'prompt': True,
    # Raw responses from OpenAI
    'response': True,
    # Notifications about subscriptions, limits and payments
    'notification': True,
    # Payment events (success or failure)
    'payment': True,
    # When user request limits reset or are exhausted
    'limit': True,
    # Saving meals to the database
    'meal_save': True,
    # Token usage statistics from OpenAI responses
    'tokens': True,
    # Mass messaging events
    'broadcast': True,
    # Admin actions to extend subscriptions
    'days': True,
    # Enabling or disabling features
    'feature': True,
    # Trial period management
    'trial': True,
    # User blocking or unblocking
    'block': True,
    # Google Programmable Search lookups
    'google': True,
}
