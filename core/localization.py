"""Process-level language selection for separately deployed app editions."""
import os


def is_english() -> bool:
    return os.getenv('CARIAGENT_LANGUAGE', 'zh').lower() == 'en'


def localized(chinese: str, english: str) -> str:
    return english if is_english() else chinese
