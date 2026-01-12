# utils/text_helpers.py
import re
def unescape_description(value: str) -> str:
    if not value:
        return ""
    # Ersetze nur einzelne Backslashes vor n oder , (aber nicht doppelte)
    value = re.sub(r'(?<!\\)\\n', '\n', value)
    value = re.sub(r'(?<!\\)\\,', ',', value)
    return value
