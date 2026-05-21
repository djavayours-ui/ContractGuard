import random
import string
import re
import time

def utf16len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2

def generate_code() -> str:
    return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

def format_time(seconds: int) -> str:
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    return f"{days}d {hours}h {minutes}m"

def parse_duration_str(s: str) -> int | None:
    s = s.strip().lower()
    try:
        if s.endswith("d"):
            return int(s[:-1]) * 86400
        if s.endswith("h"):
            return int(s[:-1]) * 3600
        if s.endswith("m"):
            return int(s[:-1]) * 60
        if s.endswith("s"):
            return int(s[:-1])
    except Exception:
        pass
    return None

def extract_link(text: str) -> str | None:
    pattern = (
        r"(https?:\/\/t\.me\/\+[^\s]+|"
        r"https?:\/\/t\.me\/joinchat\/[^\s]+|"
        r"t\.me\/\+[^\s]+|"
        r"t\.me\/joinchat\/[^\s]+|"
        r"https?:\/\/t\.me\/[^\s]+|"
        r"t\.me\/[^\s]+|"
        r"@[A-Za-z0-9_]+)"
    )
    match = re.search(pattern, text)
    return match.group(0) if match else None
