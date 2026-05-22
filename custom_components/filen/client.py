"""Minimal async Filen API client for account/storage sensors."""

from __future__ import annotations

import hashlib
import json as json_lib
import logging
from typing import Any

import aiohttp
from argon2.low_level import Type, hash_secret_raw

from .const import API_BASE_URL, REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class FilenApiError(Exception):
    """Raised when the Filen API returns an error."""


class FilenAuthError(FilenApiError):
    """Raised when Filen authentication fails."""


class FilenClient:
    """Small Filen API client for authentication and account metadata."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
        two_factor_code: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Initialize the client."""
        self.session = session
        self.email = email
        self.password = password
        self.two_factor_code = self._normalize_two_factor_code(two_factor_code)
        self.api_key = api_key
        self.auth_version: int | None = None

    async def authenticate(self) -> None:
        """Authenticate and store the API key for subsequent requests."""
        if self.api_key:
            return

        auth_info = await self._request(
            "POST",
            "/v3/auth/info",
            json={"email": self.email},
            authenticated=False,
        )
        auth_version = int(auth_info["authVersion"])
        salt = auth_info["salt"]
        derived_password = self._derive_password(self.password, salt, auth_version)

        login_response = await self._request(
            "POST",
            "/v3/login",
            json={
                "email": self.email,
                "password": derived_password,
                "twoFactorCode": self.two_factor_code,
                "authVersion": auth_version,
            },
            authenticated=False,
        )

        api_key = login_response.get("apiKey")
        if not api_key:
            raise FilenAuthError("Filen login response did not contain an API key")

        self.api_key = api_key
        self.auth_version = auth_version
        _LOGGER.debug("Authenticated with Filen using auth version %s", auth_version)

    async def async_get_account_data(self) -> dict[str, Any]:
        """Return merged user info and account/storage details."""
        await self._ensure_authenticated()

        user_info = await self._request("GET", "/v3/user/info")

        # /v3/user/account contains richer account fields but is not essential for
        # storage sensors. If it fails, still expose /v3/user/info values.
        try:
            account = await self._request("GET", "/v3/user/account")
        except FilenApiError as err:
            _LOGGER.debug("Could not fetch Filen account details: %s", err)
            account = {}

        storage_used = self._as_int(
            user_info.get("storageUsed", account.get("storage", 0))
        )
        storage_total = self._as_int(
            user_info.get("maxStorage", account.get("maxStorage", 0))
        )
        storage_percentage = (
            round((storage_used / storage_total) * 100, 2) if storage_total > 0 else 0
        )

        plans = account.get("plans") or []
        plan_names = [plan.get("name") for plan in plans if plan.get("name")]

        return {
            "account_id": user_info.get("id"),
            "email": user_info.get("email", self.email),
            "avatar_url": user_info.get("avatarURL") or account.get("avatarURL"),
            "base_folder_uuid": user_info.get("baseFolderUUID"),
            "is_premium": bool(user_info.get("isPremium", account.get("isPremium", 0))),
            "storage_used": storage_used,
            "storage_total": storage_total,
            "storage_percentage": storage_percentage,
            "display_name": account.get("displayName"),
            "nick_name": account.get("nickName"),
            "plan_names": plan_names,
            "raw_user_info": user_info,
            "raw_account": account,
        }

    async def _ensure_authenticated(self) -> None:
        """Authenticate if there is no API key yet."""
        if not self.api_key:
            await self.authenticate()

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        json: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> Any:
        """Call the Filen API and unwrap the common response envelope."""
        headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "ha-filen",
        }
        if authenticated:
            await self._ensure_api_key_present()
            headers["Authorization"] = f"Bearer {self.api_key}"
        else:
            headers["Authorization"] = "Bearer anonymous"

        url = f"{API_BASE_URL}{endpoint}"
        request_kwargs: dict[str, Any] = {}
        if json is not None:
            body = json_lib.dumps(json, separators=(",", ":"))
            headers["Content-Type"] = "application/json"
            headers["Checksum"] = hashlib.sha512(body.encode("utf-8")).hexdigest()
            request_kwargs["data"] = body

        try:
            async with self.session.request(
                method,
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                **request_kwargs,
            ) as response:
                text = await response.text()
                if response.status != 200:
                    raise FilenApiError(
                        f"{method} {endpoint} failed with HTTP {response.status}: {text}"
                    )
                try:
                    payload = await response.json()
                except aiohttp.ContentTypeError as err:
                    raise FilenApiError(
                        f"{method} {endpoint} returned non-JSON response: {text}"
                    ) from err
        except TimeoutError as err:
            raise FilenApiError(f"{method} {endpoint} timed out") from err
        except aiohttp.ClientError as err:
            raise FilenApiError(f"{method} {endpoint} failed: {err}") from err

        if isinstance(payload, dict) and payload.get("status") is False:
            message = payload.get("message") or payload.get("code") or "Unknown error"
            error_cls = FilenAuthError if endpoint in {"/v3/auth/info", "/v3/login"} else FilenApiError
            raise error_cls(str(message))

        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    async def _ensure_api_key_present(self) -> None:
        """Raise if an authenticated request is attempted before login."""
        if not self.api_key:
            raise FilenAuthError("Filen API key is not available; authenticate first")

    @staticmethod
    def _derive_password(raw_password: str, salt: str, auth_version: int) -> str:
        """Derive the login password according to the Filen SDK auth version."""
        if auth_version == 2:
            derived_key = hashlib.pbkdf2_hmac(
                "sha512",
                raw_password.encode("utf-8"),
                salt.encode("utf-8"),
                200_000,
                dklen=64,
            ).hex()
            derived_password = derived_key[len(derived_key) // 2 :]
            return hashlib.sha512(derived_password.encode("utf-8")).hexdigest()

        if auth_version == 3:
            derived = hash_secret_raw(
                raw_password.encode("utf-8"),
                bytes.fromhex(salt),
                time_cost=3,
                memory_cost=65_536,
                parallelism=4,
                hash_len=64,
                type=Type.ID,
                version=0x13,
            ).hex()
            return derived[len(derived) // 2 :]

        raise FilenAuthError(f"Unsupported Filen auth version: {auth_version}")

    @staticmethod
    def _normalize_two_factor_code(two_factor_code: str | None) -> str:
        """Return a Filen-compatible two-factor code value."""
        if two_factor_code is None:
            return "XXXXXX"

        stripped_code = str(two_factor_code).strip().replace(" ", "")
        return stripped_code or "XXXXXX"

    @staticmethod
    def _as_int(value: Any) -> int:
        """Convert API values to int, returning 0 on missing/invalid values."""
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
