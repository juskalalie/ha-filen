"""Constants for the Filen integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "filen"

CONF_TWO_FACTOR_CODE = "two_factor_code"

API_BASE_URL = "https://gateway.filen.io"
REQUEST_TIMEOUT = 30
UPDATE_INTERVAL = timedelta(minutes=30)

ATTR_ACCOUNT_ID = "account_id"
ATTR_AVATAR_URL = "avatar_url"
ATTR_BASE_FOLDER_UUID = "base_folder_uuid"
ATTR_DISPLAY_NAME = "display_name"
ATTR_EMAIL = "email"
ATTR_IS_PREMIUM = "is_premium"
ATTR_NICK_NAME = "nick_name"
ATTR_PLAN_NAMES = "plan_names"
