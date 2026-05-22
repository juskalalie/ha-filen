# Filen for Home Assistant

A small HACS custom integration that exposes Filen account and storage information as Home Assistant sensors.

## Sensors

The integration creates these sensors for one Filen account:

- Storage used
- Storage total
- Storage used percentage

Each sensor also exposes account attributes when Filen returns them, including email, account ID, premium status, base folder UUID, avatar URL, display name, nickname, and plan names.

## Installation with HACS

1. Add this repository to HACS as a custom integration repository.
2. Install the integration from HACS.
3. Restart Home Assistant.
4. Go to Settings -> Devices & services -> Add integration -> Filen.
5. Enter your Filen email, password, and optional two-factor code.

## Notes

This integration uses Filen's public web API endpoints used by the official SDK for account metadata:

- `/v3/auth/info`
- `/v3/login`
- `/v3/user/info`
- `/v3/user/account`

It supports Filen auth version 2 and version 3 password derivation. Version 3 requires `argon2-cffi`, which Home Assistant installs from the manifest requirements.
