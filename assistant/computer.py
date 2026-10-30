"""Computer control: open apps, type text, mouse, keyboard, navigation."""
from __future__ import annotations

import io
import os
import subprocess
import urllib.parse
from typing import Optional, Tuple

import pyautogui
from pynput.keyboard import Controller as KeyController, Key
from pynput.mouse import Controller as MouseController

# Prevent pyautogui from failing on multi-monitor or when mouse leaves screen
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

_keyboard = KeyController()
_mouse = MouseController()

# Common app names -> commands/paths (Windows). Add aliases so "open google" works.
COMMON_APPS = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "calc": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "explorer": ["explorer.exe"],
    "file explorer": ["explorer.exe"],
    "cmd": ["cmd.exe"],
    "command prompt": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "browser": ["start", "msedge.exe"],
    "chrome": ["start", "chrome.exe"],
    "google": ["start", "chrome.exe"],
    "google chrome": ["start", "chrome.exe"],
    "edge": ["start", "msedge.exe"],
    "microsoft edge": ["start", "msedge.exe"],
    "firefox": ["start", "firefox.exe"],
    "spotify": ["spotify.exe"],
    "discord": ["discord.exe"],
    "vscode": ["code"],
    "vs code": ["code"],
    "cursor": ["cursor"],
    "settings": ["start", "ms-settings:"],
    "task manager": ["taskmgr.exe"],
    "word": ["start", "winword.exe"],
    "excel": ["start", "excel.exe"],
    "outlook": ["start", "outlook.exe"],
}


def _start_menu_dirs() -> list[str]:
    """Return Start Menu program folders (all users + current user) on Windows."""
    dirs = []
    try:
        all_users = os.environ.get("ProgramData", "C:\\ProgramData")
        sm = os.path.join(all_users, "Microsoft", "Windows", "Start Menu", "Programs")
        if os.path.isdir(sm):
            dirs.append(sm)
        user_profile = os.environ.get("APPDATA", "")
        if user_profile:
            user_sm = os.path.join(user_profile, "..", "Roaming", "Microsoft", "Windows", "Start Menu", "Programs")
            user_sm = os.path.normpath(user_sm)
            if os.path.isdir(user_sm):
                dirs.append(user_sm)
    except Exception:
        pass
    return dirs


def _find_app_in_start_menu(query: str) -> Optional[str]:
    """
    Search Start Menu shortcuts for an app whose name contains the query.
    Returns path to the .lnk file to launch, or None.
    """
    query_lower = query.strip().lower()
    if not query_lower:
        return None
    candidates: list[tuple[str, str]] = []  # (display_name_lower, full_path)
    for start_dir in _start_menu_dirs():
        try:
            for root, _dirs, files in os.walk(start_dir):
                for f in files:
                    if not f.lower().endswith(".lnk"):
                        continue
                    base = os.path.splitext(f)[0]
                    path = os.path.join(root, f)
                    if query_lower in base.lower():
                        candidates.append((base.lower(), path))
        except Exception:
            continue
    if not candidates:
        return None
    # Prefer shortest name (e.g. "Google Chrome" over "Google Chrome (default)")
    candidates.sort(key=lambda x: (len(x[0]), x[0]))
    return candidates[0][1]


# Site names -> URLs for "open google and go to youtube"
COMMON_SITES = {
    "youtube": "https://www.youtube.com",
    "facebook": "https://www.facebook.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "instagram": "https://www.instagram.com",
    "reddit": "https://www.reddit.com",
    "amazon": "https://www.amazon.com",
    "walmart": "https://www.walmart.com",
    "target": "https://www.target.com",
    "bestbuy": "https://www.bestbuy.com",
    "ebay": "https://www.ebay.com",
    "netflix": "https://www.netflix.com",
    "twitch": "https://www.twitch.tv",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "google mail": "https://mail.google.com",
    "maps": "https://www.google.com/maps",
    "google maps": "https://www.google.com/maps",
    "drive": "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "wikipedia": "https://www.wikipedia.org",
    "wiki": "https://www.wikipedia.org",
}

# Search URL patterns for "open [site] and search for [query]". {query} is replaced with URL-encoded query.
SITE_SEARCH_URLS = {
    "youtube": "https://www.youtube.com/results?search_query={query}",
    "reddit": "https://www.reddit.com/search/?q={query}",
    "amazon": "https://www.amazon.com/s?k={query}",
    "walmart": "https://www.walmart.com/search?q={query}",
    "target": "https://www.target.com/s?searchTerm={query}",
    "bestbuy": "https://www.bestbuy.com/site/searchpage.jsp?st={query}",
    "ebay": "https://www.ebay.com/sch/i.html?_nkw={query}",
    "costco": "https://www.costco.com/CatalogSearch?keyword={query}",
    "homedepot": "https://www.homedepot.com/s/{query}",
    "lowes": "https://www.lowes.com/search?searchTerm={query}",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search={query}",
    "wiki": "https://en.wikipedia.org/w/index.php?search={query}",
    "github": "https://github.com/search?q={query}",
    "twitch": "https://www.twitch.tv/search?term={query}",
    "twitter": "https://twitter.com/search?q={query}",
    "x": "https://x.com/search?q={query}",
    "facebook": "https://www.facebook.com/search/top?q={query}",
    "instagram": "https://www.instagram.com/explore/tags/{query}/",
    "imdb": "https://www.imdb.com/find?q={query}",
    "duckduckgo": "https://duckduckgo.com/?q={query}",
    "bing": "https://www.bing.com/search?q={query}",
}


def _site_to_url(site: str) -> str:
    """Turn a site name (e.g. 'youtube') into a full URL."""
    s = site.strip().lower().replace(" ", "")
    if s in COMMON_SITES:
        return COMMON_SITES[s]
    # If it already looks like a URL, return as-is (with scheme if missing)
    if s.startswith("http://") or s.startswith("https://"):
        return site.strip()
    if "." in s:
        return s if s.startswith("http") else "https://" + s
    return "https://www." + s + ".com"


def _site_search_url(site: str, query: str) -> str:
    """Get search URL for a site. Uses known patterns or generic fallback."""
    s = site.strip().lower().replace(" ", "")
    encoded = urllib.parse.quote_plus(query.strip())
    if s in SITE_SEARCH_URLS:
        tpl = SITE_SEARCH_URLS[s]
        for placeholder in ("{query}", "{searchTerm}", "{keyword}", "{st}"):
            tpl = tpl.replace(placeholder, encoded)
        return tpl
    base = COMMON_SITES.get(s, f"https://www.{s}.com")
    base = base.rstrip("/")
    if "?" in base:
        return base + "&q=" + encoded
    return base + "/search?q=" + encoded


def open_browser_url(url: str) -> str:
    """Open the default browser to a URL (e.g. https://youtube.com)."""
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    try:
        subprocess.Popen(f"start {url}", shell=True)
        return f"Opened {url} in your browser."
    except Exception as e:
        return f"Could not open browser: {e}"


def open_browser_search(query: str) -> str:
    """Open the default browser to Google search for the given query."""
    if not query or not query.strip():
        return "No search query given."
    encoded = urllib.parse.quote_plus(query.strip())
    url = "https://www.google.com/search?q=" + encoded
    try:
        subprocess.Popen(f"start {url}", shell=True)
        return f"Opened Google search for: {query}."
    except Exception as e:
        return f"Could not open browser: {e}"


def open_first_youtube_video(query: str) -> str:
    """Search for query and open the first YouTube video result in the browser."""
    try:
        from . import web_search
        results = web_search.search(f"{query.strip()} youtube", max_results=8)
        for r in results:
            url = (r.get("url") or "").strip()
            if "youtube.com/watch" in url or "youtu.be/" in url:
                return open_browser_url(url)
        return f"No YouTube video found for: {query}"
    except Exception as e:
        return f"Could not find YouTube video: {e}"


def search_site_and_add_first_to_cart(site: str, query: str, wait_seconds: Optional[float] = None) -> str:
    """Open site, search for query, wait for load, then click Add to Cart on first result."""
    import time
    import config
    wait_seconds = wait_seconds if wait_seconds is not None else getattr(config, "PAGE_LOAD_WAIT_SECONDS", 4.0)
    url = _site_search_url(site, query)
    try:
        subprocess.Popen(f"start {url}", shell=True)
    except Exception as e:
        return f"Could not open browser: {e}"
    time.sleep(wait_seconds)
    from . import vision
    png = screenshot_bytes(all_monitors=True)
    if not png:
        return f"Opened {site} search for {query}. Could not capture screen to add to cart."
    target = "the Add to Cart, Add to basket, or Buy button for the FIRST product in the search results"
    result = vision.locate_in_screenshot(png, target)
    if result is None:
        return f"Opened {site} and searched for {query}. Could not find Add to Cart for first result."
    if isinstance(result, tuple):
        x, y = result
        sx, sy = _screen_coords_from_image(x, y)
        pyautogui.click(sx, sy)
        return f"Opened {site}, searched for {query}, clicked Add to Cart on first result."
    click_screen_region(result)
    return f"Opened {site}, searched for {query}, clicked Add to Cart region."


def open_site_search(site: str, query: str) -> str:
    """Open the browser to search for 'query' on the given site (e.g. youtube, reddit, amazon)."""
    if not query or not query.strip():
        return "No search query given."
    site_key = site.strip().lower().replace(" ", "")
    encoded = urllib.parse.quote_plus(query.strip())
    if site_key in SITE_SEARCH_URLS:
        url = SITE_SEARCH_URLS[site_key].format(query=encoded)
    else:
        # Fallback: try site homepage + /search?q= or common pattern
        base = COMMON_SITES.get(site_key, f"https://www.{site_key}.com")
        if "?" in base:
            url = base + "&q=" + encoded
        else:
            url = base.rstrip("/") + "/search?q=" + encoded
    try:
        subprocess.Popen(f"start {url}", shell=True)
        return f"Opened {site} and searched for: {query}."
    except Exception as e:
        return f"Could not open browser: {e}"


def open_app(name_or_path: str) -> str:
    """
    Open an application by common name, display name, or path.
    Tries: COMMON_APPS -> path exists -> Start Menu search -> shell.
    Returns a short status message.
    """
    name_lower = name_or_path.strip().lower()
    if name_lower in COMMON_APPS:
        cmd = COMMON_APPS[name_lower]
        try:
            if cmd[0] == "start":
                subprocess.Popen("start " + " ".join(cmd[1:]), shell=True)
            else:
                subprocess.Popen(cmd, shell=False)
            return f"Opened {name_or_path}."
        except Exception as e:
            return f"Could not open {name_or_path}: {e}"

    # Treat as path if it exists
    if os.path.exists(name_or_path):
        try:
            subprocess.Popen([name_or_path], shell=False)
            return f"Opened {name_or_path}."
        except Exception as e:
            return f"Could not open: {e}"

    # Search Start Menu: "open spotify", "open minecraft", "open valorant", etc.
    lnk_path = _find_app_in_start_menu(name_or_path)
    if lnk_path:
        try:
            os.startfile(lnk_path)
            return f"Opened {name_or_path}."
        except Exception as e:
            return f"Could not open {name_or_path}: {e}"

    # Last resort: try as shell command (e.g. "notepad")
    try:
        subprocess.Popen(name_or_path, shell=True)
        return f"Opened {name_or_path}."
    except Exception as e:
        return f"Could not open {name_or_path}: {e}"


def type_text(text: str, interval: float = 0.02) -> str:
    """Type a string using the keyboard (current focus gets the input)."""
    if not text:
        return "No text to type."
    try:
        pyautogui.write(text, interval=interval)
        return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"
    except Exception as e:
        return f"Could not type: {e}"


def press_key(key_name: str) -> str:
    """Press a key or key combo (e.g. 'enter', 'ctrl+c', 'alt+tab')."""
    key_map = {
        "enter": Key.enter,
        "tab": Key.tab,
        "space": Key.space,
        "backspace": Key.backspace,
        "escape": Key.esc,
        "up": Key.up,
        "down": Key.down,
        "left": Key.left,
        "right": Key.right,
        "home": Key.home,
        "end": Key.end,
        "page up": Key.page_up,
        "page down": Key.page_down,
    }
    key_name = key_name.strip().lower()
    if key_name in key_map:
        try:
            _keyboard.press(key_map[key_name])
            _keyboard.release(key_map[key_name])
            return f"Pressed {key_name}."
        except Exception as e:
            return f"Could not press key: {e}"

    # Combo like ctrl+c
    parts = [p.strip().lower() for p in key_name.split("+")]
    mods = []
    for p in parts[:-1]:
        if p == "ctrl":
            mods.append(Key.ctrl)
        elif p == "alt":
            mods.append(Key.alt)
        elif p == "shift":
            mods.append(Key.shift)
        elif p == "win":
            mods.append(Key.cmd)  # Windows key
    if not mods and len(parts) == 1:
        return f"Unknown key: {key_name}"
    try:
        with _keyboard.pressed(*mods):
            last = parts[-1]
            if last in key_map:
                _keyboard.press(key_map[last])
                _keyboard.release(key_map[last])
            else:
                _keyboard.press(last)
                _keyboard.release(last)
        return f"Pressed {key_name}."
    except Exception as e:
        return f"Could not press key: {e}"


def mouse_move(x: Optional[int] = None, y: Optional[int] = None, relative: bool = False) -> str:
    """Move mouse to (x,y). If relative=True, move by delta."""
    try:
        if relative:
            pyautogui.moveRel(x or 0, y or 0)
        else:
            pyautogui.moveTo(x or 0, y or 0)
        return "Mouse moved."
    except Exception as e:
        return f"Could not move mouse: {e}"


def mouse_click(button: str = "left", clicks: int = 1) -> str:
    """Click mouse button: left, right, or middle."""
    try:
        pyautogui.click(button=button, clicks=clicks)
        return f"Clicked {button} {clicks} time(s)."
    except Exception as e:
        return f"Could not click: {e}"


def screenshot_bytes(all_monitors: bool = True) -> Optional[bytes]:
    """Capture the screen as PNG bytes for vision analysis. On Windows, all_monitors=True captures every monitor."""
    try:
        if all_monitors and os.name == "nt":
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab(all_screens=True)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()
            except (ImportError, TypeError, Exception):
                pass
        img = pyautogui.screenshot()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def get_screen_size() -> Tuple[int, int]:
    """Return (width, height) of the virtual screen (all monitors combined)."""
    if os.name == "nt":
        try:
            import ctypes
            u32 = ctypes.windll.user32
            w = u32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
            h = u32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
            if w > 0 and h > 0:
                return (w, h)
        except Exception:
            pass
    w, h = pyautogui.size()
    return (w, h)


def _screen_coords_from_image(x: int, y: int) -> Tuple[int, int]:
    """Convert image coords (0,0 = top-left of capture) to actual screen coords for click."""
    if os.name == "nt":
        try:
            import ctypes
            u32 = ctypes.windll.user32
            ox = u32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
            oy = u32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
            return (x + ox, y + oy)
        except Exception:
            pass
    return (x, y)


def click_at(x: int, y: int) -> str:
    """Click at pixel coordinates (works across all monitors)."""
    try:
        pyautogui.click(x, y)
        return f"Clicked at ({x}, {y})."
    except Exception as e:
        return f"Could not click: {e}"


def click_screen_region(region: str) -> str:
    """Click at a screen region. Uses virtual screen size for multi-monitor."""
    try:
        w, h = get_screen_size()
        regions = {
            "topleft": (w // 4, h // 4),
            "topcenter": (w // 2, h // 4),
            "topright": (3 * w // 4, h // 4),
            "middleleft": (w // 4, h // 2),
            "center": (w // 2, h // 2),
            "middleright": (3 * w // 4, h // 2),
            "bottomleft": (w // 4, 3 * h // 4),
            "bottomcenter": (w // 2, 3 * h // 4),
            "bottomright": (3 * w // 4, 3 * h // 4),
        }
        key = region.strip().lower().replace(" ", "").replace("-", "")
        if key not in regions:
            return f"Unknown region: {region}. Use: topleft, topcenter, center, etc."
        x, y = regions[key]
        sx, sy = _screen_coords_from_image(x, y)
        pyautogui.click(sx, sy)
        return f"Clicked at {region}."
    except Exception as e:
        return f"Could not click: {e}"


def click_on_screen(target: str) -> str:
    """Use vision to find target on screen and click at its location. Works across all monitors."""
    try:
        from . import vision
        png = screenshot_bytes(all_monitors=True)
        if not png:
            return "Could not capture the screen."
        result = vision.locate_in_screenshot(png, target)
        if result is None:
            return f"Could not find '{target}' on the screen."
        if isinstance(result, tuple):
            x, y = result
            sx, sy = _screen_coords_from_image(x, y)
            return click_at(sx, sy)
        return click_screen_region(result)
    except Exception as e:
        return f"Could not click on {target}: {e}"


def mouse_scroll(delta: int, x: Optional[int] = None, y: Optional[int] = None) -> str:
    """Scroll. delta: positive = up, negative = down. Optional (x,y) position."""
    try:
        if x is not None and y is not None:
            pyautogui.scroll(delta, x=x, y=y)
        else:
            pyautogui.scroll(delta)
        return "Scrolled."
    except Exception as e:
        return f"Could not scroll: {e}"


def take_screenshot(save_path: Optional[str] = None) -> str:
    """Take a screenshot. If save_path given, save there; else save to screenshot.png."""
    try:
        path = save_path or "screenshot.png"
        pyautogui.screenshot(path)
        return f"Screenshot saved to {path}."
    except Exception as e:
        return f"Screenshot failed: {e}"


def get_system_info() -> str:
    """Return a short string with CPU and memory usage."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        return f"CPU: {cpu}% | RAM: {mem.percent}% used ({mem.used // (1024**3)}GB / {mem.total // (1024**3)}GB)"
    except Exception as e:
        return f"Could not get system info: {e}"


def get_clipboard() -> str:
    """Return current clipboard text."""
    try:
        import pyperclip
        return pyperclip.paste() or "(empty)"
    except Exception as e:
        return f"Could not read clipboard: {e}"


def set_clipboard(text: str) -> str:
    """Set clipboard to the given text."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return "Clipboard updated."
    except Exception as e:
        return f"Could not set clipboard: {e}"


def lock_pc() -> str:
    """Lock the workstation (Windows)."""
    try:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return "PC locked."
    except Exception as e:
        return f"Could not lock: {e}"


def volume_up() -> str:
    """Increase system volume (Windows: simulate volume up key)."""
    try:
        import pyautogui
        pyautogui.press("volumeup", presses=3)
        return "Volume up."
    except Exception as e:
        return f"Could not change volume: {e}"


def volume_down() -> str:
    """Decrease system volume."""
    try:
        pyautogui.press("volumedown", presses=3)
        return "Volume down."
    except Exception as e:
        return f"Could not change volume: {e}"


def volume_mute() -> str:
    """Toggle mute."""
    try:
        pyautogui.press("volumemute")
        return "Mute toggled."
    except Exception as e:
        return f"Could not mute: {e}"


def set_volume_percent(percent: int) -> str:
    """Set system volume to 0-100 percent. Uses pycaw on Windows if available: pip install pycaw comtypes"""
    percent = max(0, min(100, int(percent)))
    if os.name == "nt":
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(percent / 100.0, None)
            return f"Volume set to {percent}%."
        except ImportError:
            pass
        except Exception:
            pass
    presses = max(1, min(10, int(percent / 10)))
    try:
        pyautogui.press("volumeup", presses=presses)
        return f"Volume adjusted. For precise control: pip install pycaw comtypes"
    except Exception as e:
        return f"Could not set volume: {e}"


def list_directory(folder: str = "") -> str:
    """List contents of a folder. Default: user's home or Desktop."""
    try:
        if not folder or folder.strip().lower() in ("desktop", "my desktop"):
            folder = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
        elif folder.strip().lower() in ("downloads", "download"):
            folder = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Downloads")
        elif folder.strip().lower() in ("documents", "docs"):
            folder = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Documents")
        else:
            folder = os.path.expanduser(folder.strip())
        if not os.path.isdir(folder):
            return f"Folder not found: {folder}"
        names = os.listdir(folder)
        names.sort(key=lambda x: (not os.path.isdir(os.path.join(folder, x)), x.lower()))
        lines = [f"Contents of {os.path.basename(folder) or folder}:"]
        for n in names[:50]:
            path = os.path.join(folder, n)
            lines.append(f"  {'[DIR] ' if os.path.isdir(path) else ''}{n}")
        if len(names) > 50:
            lines.append(f"  ... and {len(names) - 50} more")
        return "\n".join(lines)
    except Exception as e:
        return f"Could not list folder: {e}"


def create_folder(path: str) -> str:
    """Create a folder. Path can be 'Desktop\\MyFolder' or full path."""
    try:
        path = path.strip()
        if not os.path.isabs(path):
            path = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop", path)
        path = os.path.normpath(path)
        os.makedirs(path, exist_ok=True)
        return f"Created folder: {path}."
    except Exception as e:
        return f"Could not create folder: {e}"


def open_folder(path: str) -> str:
    """Open a folder in Explorer. Path can be 'Desktop', 'Downloads', or path."""
    try:
        path = path.strip()
        if path.lower() in ("desktop", "my desktop"):
            path = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
        elif path.lower() in ("downloads", "download"):
            path = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Downloads")
        elif path.lower() in ("documents", "docs"):
            path = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Documents")
        else:
            path = os.path.expanduser(path)
        path = os.path.normpath(path)
        if os.path.isdir(path):
            os.startfile(path)
            return f"Opened folder."
        if os.path.isfile(path):
            os.startfile(path)
            return "Opened file."
        return f"Not found: {path}"
    except Exception as e:
        return f"Could not open: {e}"
