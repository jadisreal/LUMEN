import os
import time
import subprocess
import pyautogui
from tts import speak


# Direct launch paths/commands - much faster & more reliable than Windows Search
# Maps normalized name -> (method, target)
# method: "path" = direct exe, "shell" = shell command, "search" = fallback to Windows Search
APP_REGISTRY = {
    "whatsapp":        ("search", "WhatsApp"),
    "opera":           ("search", "Opera GX"),
    "opera gx":        ("search", "Opera GX"),
    "discord":         ("search", "Discord"),
    "steam":           ("search", "Steam"),
    "brave":           ("search", "Brave"),
    "brave browser":   ("search", "Brave"),
    "spotify":         ("search", "Spotify"),
    "powershell":      ("shell", "start powershell"),
    "cmd":             ("shell", "start powershell"),
    "command prompt":  ("shell", "start powershell"),
    "terminal":        ("shell", "start powershell"),
    "vscode":          ("shell", "code"),
    "vs code":         ("shell", "code"),
    "visual studio code": ("shell", "code"),
    "lm studio":       ("search", "LM Studio"),
    "calculator":      ("shell", "calc"),
    "calc":            ("shell", "calc"),
    "capcut":          ("search", "CapCut"),
    "canva":           ("search", "Canva"),
    "epic games":      ("search", "Epic Games"),
    "epic":            ("search", "Epic Games"),
    "epic games launcher": ("search", "Epic Games"),
    "github desktop":  ("search", "GitHub Desktop"),
    "github":          ("search", "GitHub Desktop"),
    "paint":           ("shell", "mspaint"),
    "obs":             ("search", "OBS Studio"),
    "obs studio":      ("search", "OBS Studio"),
    "osu":             ("search", "osu!"),
}


def _normalize(name: str) -> str:
    return name.lower().strip().replace("'", "").replace("'", "")


def _launch_shell(command: str) -> bool:
    try:
        subprocess.Popen(command, shell=True)
        return True
    except Exception:
        return False


def _launch_search(search_term: str) -> bool:
    try:
        pyautogui.PAUSE = 0.1
        pyautogui.press("win")
        time.sleep(0.4)
        pyautogui.write(search_term, interval=0.03)
        time.sleep(0.3)
        pyautogui.press("enter")
        return True
    except Exception:
        return False


def open_app(
    parameters: dict,
    response: str | None = None,
    player=None,
    session_memory=None
) -> bool:
    app_name = (parameters or {}).get("app_name", "").strip()

    if not app_name and session_memory:
        app_name = session_memory.open_app or ""

    if not app_name:
        msg = "I couldn't determine which application to open, Chart."
        if player:
            player.write_log(msg)
        speak(msg, player)
        return False

    if response:
        if player:
            player.write_log(response)
        speak(response, player)

    normalized = _normalize(app_name)

    # Check registry for direct launch
    if normalized in APP_REGISTRY:
        method, target = APP_REGISTRY[normalized]
        if method == "shell":
            success = _launch_shell(target)
        elif method == "path":
            success = _launch_shell(f'start "" "{target}"')
        else:
            success = _launch_search(target)
    else:
        # Fallback: Windows Search
        success = _launch_search(app_name)

    if success:
        if session_memory:
            session_memory.set_open_app(app_name)
        return True
    else:
        msg = f"I failed to open {app_name}."
        if player:
            player.write_log(msg)
        speak(msg, player)
        return False
