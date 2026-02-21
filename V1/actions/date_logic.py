# actions/date_logic.py - Local date/time computation (no LLM needed)
#
# Handles questions the LLM can't answer accurately because they
# require calendar computation beyond its training data, e.g.
#   "When is the next Friday the 13th?"
#   "How many days until Christmas?"

import re
from datetime import datetime, timedelta
from tts import speak
from core.logger import get_logger

log = get_logger("action.date")


# ── Computation helpers ───────────────────────────────────────

def _next_friday_13(from_date: datetime = None) -> datetime | None:
    """Find the next Friday the 13th on or after *from_date*."""
    d = from_date or datetime.now()
    year, month = d.year, d.month

    # If today is already past the 13th, start from next month
    if d.day > 13 or (d.day == 13 and d.weekday() != 4):
        month += 1
        if month > 12:
            month = 1
            year += 1
    elif d.day == 13 and d.weekday() == 4:
        # Today IS Friday the 13th — return today
        return d

    for _ in range(200):  # safety: ~16 years max
        try:
            candidate = datetime(year, month, 13)
        except ValueError:
            month += 1
            if month > 12:
                month = 1
                year += 1
            continue

        if candidate.weekday() == 4:  # Friday
            return candidate

        month += 1
        if month > 12:
            month = 1
            year += 1

    return None


def _days_until(target_month: int, target_day: int, from_date: datetime = None) -> int:
    """Days remaining until the next occurrence of month/day."""
    now = from_date or datetime.now()
    target = now.replace(month=target_month, day=target_day,
                         hour=0, minute=0, second=0, microsecond=0)
    if target.date() <= now.date():
        target = target.replace(year=now.year + 1)
    return (target.date() - now.date()).days


# Well-known holidays (month, day)
HOLIDAY_MAP = {
    "christmas":        (12, 25),
    "christmas day":    (12, 25),
    "new year":         (1, 1),
    "new years":        (1, 1),
    "new year's":       (1, 1),
    "new year's day":   (1, 1),
    "valentine":        (2, 14),
    "valentines":       (2, 14),
    "valentine's":      (2, 14),
    "valentine's day":  (2, 14),
    "halloween":        (10, 31),
    "independence day": (7, 4),
    "april fools":      (4, 1),
    "st patrick":       (3, 17),
    "st. patrick":      (3, 17),
}

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _handle_days_until(query: str, now: datetime) -> str | None:
    """Handle 'how many days until X' queries."""
    q = query.lower()

    for name, (month, day) in HOLIDAY_MAP.items():
        if name in q:
            days = _days_until(month, day, now)
            year = now.year if days > 0 else now.year + 1
            date_str = datetime(year, month, day).strftime("%B %d, %Y")
            return f"There are {days} days until {name.title()} ({date_str})."

    return None


def _handle_day_of_week(query: str, now: datetime) -> str | None:
    """Handle 'what day is <date>' queries."""
    q = query.lower()

    for month_name, month_num in MONTHS.items():
        match = re.search(rf"{month_name}\s+(\d{{1,2}})\s*,?\s*(\d{{4}})?", q)
        if match:
            day = int(match.group(1))
            year = int(match.group(2)) if match.group(2) else now.year
            try:
                target = datetime(year, month_num, day)
                return f"{month_name.title()} {day}, {year} is a {target.strftime('%A')}."
            except ValueError:
                pass

    return None


# ── Main handler ──────────────────────────────────────────────

def date_query(parameters=None, response=None, player=None, session_memory=None, **kwargs):
    """
    Handle date/time computation queries locally.
    Falls back to the LLM response text if no known pattern matches.
    """
    query = (parameters or {}).get("query", "").strip()
    now = datetime.now()
    answer = None

    q = query.lower()

    # --- Friday the 13th ---
    if "friday the 13" in q or "friday 13" in q:
        f13 = _next_friday_13(now)
        if f13:
            answer = f"The next Friday the 13th is {f13.strftime('%A, %B %d, %Y')}."

    # --- Days until holiday/date ---
    elif any(kw in q for kw in ("days until", "how many days", "how long until", "how long till")):
        answer = _handle_days_until(query, now)

    # --- What day of the week ---
    elif "what day" in q and any(w in q for w in ("is", "was", "will")):
        answer = _handle_day_of_week(query, now)

    # --- Current date/time ---
    elif any(kw in q for kw in ("what time", "current time", "time now", "time is it")):
        answer = f"It's currently {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}."

    elif any(kw in q for kw in ("what date", "today's date", "current date", "what year")):
        answer = f"Today is {now.strftime('%A, %B %d, %Y')}."

    # --- Fallback to LLM response ---
    if not answer:
        answer = response or f"I couldn't compute that, but today is {now.strftime('%A, %B %d, %Y')}."

    log.info(f"Date query: '{query}' → '{answer}'")

    if player:
        player.write_log(f"Lumen: {answer}")
    speak(answer, player)

    if session_memory:
        session_memory.set_last_search(query, answer)

    return answer
