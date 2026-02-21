# actions/open_folder.py - Open system folders (Downloads, Documents, etc.)

import os
from tts import speak
from core.logger import get_logger

log = get_logger("action.folder")

# Common user folders mapped to their OS paths
FOLDER_MAP = {
    "downloads":   os.path.join(os.path.expanduser("~"), "Downloads"),
    "download":    os.path.join(os.path.expanduser("~"), "Downloads"),
    "documents":   os.path.join(os.path.expanduser("~"), "Documents"),
    "document":    os.path.join(os.path.expanduser("~"), "Documents"),
    "desktop":     os.path.join(os.path.expanduser("~"), "Desktop"),
    "pictures":    os.path.join(os.path.expanduser("~"), "Pictures"),
    "photos":      os.path.join(os.path.expanduser("~"), "Pictures"),
    "music":       os.path.join(os.path.expanduser("~"), "Music"),
    "videos":      os.path.join(os.path.expanduser("~"), "Videos"),
    "video":       os.path.join(os.path.expanduser("~"), "Videos"),
    "home":        os.path.expanduser("~"),
    "user":        os.path.expanduser("~"),
    "appdata":     os.getenv("APPDATA", ""),
    "temp":        os.getenv("TEMP", ""),
    "recycle bin": "shell:RecycleBinFolder",
}


def _normalize_folder(name: str) -> str:
    """Normalize folder name for lookup."""
    return (
        name.lower()
        .strip()
        .replace("folder", "")
        .replace("my ", "")
        .replace("the ", "")
        .strip()
    )


def open_folder(parameters=None, response=None, player=None, session_memory=None, **kwargs):
    """Open a system folder in Windows Explorer."""
    folder_name = (parameters or {}).get("folder_name", "").strip()

    if not folder_name:
        msg = "I couldn't determine which folder to open."
        if player:
            player.write_log(f"Lumen: {msg}")
        speak(msg, player)
        return False

    normalized = _normalize_folder(folder_name)
    path = FOLDER_MAP.get(normalized)

    # If not in map, try as an absolute path
    if not path and os.path.isdir(folder_name):
        path = folder_name

    # Fuzzy match: check if any key contains / is contained by the query
    if not path:
        for key, val in FOLDER_MAP.items():
            if key in normalized or normalized in key:
                path = val
                break

    if not path or (not path.startswith("shell:") and not os.path.isdir(path)):
        msg = f"I couldn't find the {folder_name} folder."
        if player:
            player.write_log(f"Lumen: {msg}")
        speak(msg, player)
        return False

    try:
        os.startfile(path)
        log.info(f"Opened folder: {path}")

        msg = response or f"Opening {folder_name}."
        if player:
            player.write_log(f"Lumen: {msg}")
        speak(msg, player)
        return True

    except Exception as e:
        log.error(f"Failed to open folder '{path}': {e}", exc_info=True)
        msg = f"I failed to open the {folder_name} folder."
        if player:
            player.write_log(f"Lumen: {msg}")
        speak(msg, player)
        return False
