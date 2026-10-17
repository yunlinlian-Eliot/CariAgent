"""Compatibility helpers for the English-only branch."""


def is_english() -> bool:
    """Both application entry points in this branch use English."""
    return True


def localized(source: str, english: str) -> str:
    """Return English text for callers using the earlier localization API."""
    return english
