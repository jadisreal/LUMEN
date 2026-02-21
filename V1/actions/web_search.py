import re
import time
from ddgs import DDGS
from tts import speak
from core.logger import get_logger

log = get_logger("action.search")


MAX_SNIPPETS = 3
MIN_SENTENCE_LENGTH = 30

# Rate-limit delay between searches (seconds)
SEARCH_DELAY = 2
_last_search_time = 0.0

# Keywords that indicate user wants news, not general knowledge
NEWS_KEYWORDS = ["news", "latest", "recent", "headlines", "breaking",
                 "update on", "current events", "what happened"]

NOISE_KEYWORDS = [
    "read more", "learn more", "click here", "infographic",
    "google trends", "year in search", "most searched", "top 100",
    "subscribe", "share this", "advertisement", "ad:",
    "visit our", "visit us", "sign up", "log in",
    "for more information", "for more details",
    "download the app", "get the app", "follow us", "join us",
    "cookies", "privacy policy", "terms of service",
    "copyright", "all rights reserved", "\u00a9",
    "sponsored", "partner content", "promoted",
    "sign up for", "newsletter", "free trial",
]

# Regex patterns that indicate promotional / ad-like sentences
AD_PATTERNS = [
    r"for more (?:information|details|news)[\s,.]",
    r"visit (?:our|us|the)\b",
    r"(?:get|download) the (?:latest|app|full)\b",
    r"(?:sign|log) (?:up|in)\b",
    r"(?:click|tap) (?:here|to)\b",
    r"(?:subscribe|follow) (?:to|us|for)\b",
    r"go to \w+\.(?:com|org|net)",
    r"available (?:on|at|in) (?:the )?\w+ (?:store|app|play)",
    r"check out (?:our|the)\b",
    r"brought to you by\b",
]


def _is_news_query(query: str) -> bool:
    """Check whether the user likely wants news results."""
    q = query.lower()
    return any(kw in q for kw in NEWS_KEYWORDS)


def clean(text: str) -> str:
    """Clean text: remove extra spaces, ..., brackets."""
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\.\.\.+", ".", text)
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    return text.strip()


def split_sentences(text: str):
    """Split text into sentences and avoid very short or incomplete ones."""
    sentences = re.split(r"(?<=[.!?])\s+", text)

    valid_sentences = []
    buffer = ""

    for s in sentences:
        s = clean(s)
        if not s:
            continue

        last_word = s.split()[-1].lower()
        if last_word in [
            "of", "in", "at", "on", "by",
            "after", "before", "with", "for", "to"
        ]:
            buffer += s + " "
            continue

        if buffer:
            s = buffer + s
            buffer = ""

        if len(s) >= MIN_SENTENCE_LENGTH:
            valid_sentences.append(s)

    return valid_sentences


def is_noise(text: str) -> bool:
    """Check if a sentence is noise, irrelevant, or ad-like."""
    t = text.lower()

    if any(kw in t for kw in NOISE_KEYWORDS):
        return True

    for pattern in AD_PATTERNS:
        if re.search(pattern, t):
            return True

    return False


def select_best_sentence(snippets):
    """Combine up to MAX_SNIPPETS and return a single coherent sentence."""
    final_text = ""
    count = 0

    for snippet in snippets:
        if not snippet or is_noise(snippet):
            continue

        sentences = split_sentences(snippet)

        for s in sentences:
            if is_noise(s):
                continue

            final_text = f"{final_text} {s}".strip()
            count += 1

            if count >= MAX_SNIPPETS:
                return final_text

    return final_text if final_text else None


def ddg_answer(query: str) -> str:
    """Perform DuckDuckGo search and return a coherent answer."""
    global _last_search_time

    # Rate-limit: wait if needed
    elapsed = time.time() - _last_search_time
    if elapsed < SEARCH_DELAY:
        time.sleep(SEARCH_DELAY - elapsed)

    try:
        results = DDGS().text(query, max_results=5)
        _last_search_time = time.time()
    except Exception as e:
        log.error(f"DuckDuckGo search failed: {e}", exc_info=True)
        return "The web search failed."

    if not results:
        return "I couldn't find relevant information."

    snippets = [
        r.get("body", "")
        for r in results
        if r.get("body")
    ]

    answer = select_best_sentence(snippets)

    if not answer:
        return "I found information online, but couldn't summarize it clearly."

    return answer


def ddg_news_answer(query: str) -> str:
    """Search DDG news endpoint and return summarised headlines."""
    global _last_search_time

    elapsed = time.time() - _last_search_time
    if elapsed < SEARCH_DELAY:
        time.sleep(SEARCH_DELAY - elapsed)

    try:
        results = DDGS().news(query, max_results=5)
        _last_search_time = time.time()
    except Exception as e:
        log.error(f"DDG news search failed: {e}", exc_info=True)
        return ddg_answer(query)  # fallback to text search

    if not results:
        return ddg_answer(query)  # fallback

    summaries = []
    for r in results[:5]:
        title = clean(r.get("title", ""))
        body = clean(r.get("body", ""))
        source = r.get("source", "").strip()

        if not title or is_noise(title):
            continue

        summary = title
        if body and not is_noise(body):
            # Take the first sentence of the body only
            first_sent = body.split(".")[0].strip()
            if first_sent and len(first_sent) > 20 and not is_noise(first_sent):
                summary += ". " + first_sent + "."
        if source:
            summary += f" ({source})"

        summaries.append(summary)

    if not summaries:
        return ddg_answer(query)  # fallback

    # Return up to 2 headline summaries (keep it brief for TTS)
    return " ".join(summaries[:2])


def web_search(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
    **kwargs
):
    """
    Main web search using DuckDuckGo:
    - Uses the news endpoint for news queries
    - Returns coherent sentences, filtering out ads and noise
    - Combines multiple snippets if needed to avoid cut-offs
    """

    query = (parameters or {}).get("query", "").strip()

    if not query:
        msg = "I couldn't understand the search request."
        if player:
            player.write_log(msg)
        speak(msg, player)
        return msg

    # Route news queries to the DDG news endpoint
    if _is_news_query(query):
        answer = ddg_news_answer(query)
    else:
        answer = ddg_answer(query)

    if player:
        player.write_log(f"Lumen: {answer}")

    speak(answer, player)

    if session_memory:
        session_memory.set_last_search(query, answer)

    return answer
