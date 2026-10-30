"""Camera capture and image description using Ollama LLaVA (vision) model."""
from __future__ import annotations

import base64
import io
import re
from typing import Optional, Tuple, Union

import config

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

try:
    import numpy as _np  # used for gesture helpers
except Exception:
    _np = None

try:
    import ollama
    _OLLAMA_AVAILABLE = True
except ImportError:
    _OLLAMA_AVAILABLE = False

# Max dimension for image sent to vision model (keeps inference fast)
_VISION_MAX_DIM = getattr(config, "VISION_MAX_DIM", 768)

# Optional: latest frame from live preview (set by main.py to avoid camera conflict)
_preview_frame: dict = {"frame": None}


def set_preview_frame(frame_bgr) -> None:
    """Register the latest frame from the live camera preview. Vision queries will use this if available."""
    _preview_frame["frame"] = frame_bgr


def clear_preview_frame() -> None:
    """Clear the preview frame (call when camera preview stops)."""
    _preview_frame["frame"] = None


def capture_frame(camera_index: Optional[int] = None) -> Optional[bytes]:
    """
    Capture a single frame from the webcam as PNG bytes.
    Uses the live preview frame if available (avoids camera conflict).
    Returns None if camera or OpenCV not available.
    """
    if not _CV2_AVAILABLE:
        return None
    frame = _preview_frame.get("frame")
    if frame is not None:
        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            from PIL import Image
            pil = Image.fromarray(frame_rgb)
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            pass
    idx = camera_index if camera_index is not None else config.CAMERA_INDEX
    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        return None
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        return None
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    from PIL import Image
    pil = Image.fromarray(frame_rgb)
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


def describe_image(image_bytes: bytes, prompt: str = "Describe what you see in this image in one or two sentences.") -> str:
    """
    Send image to Ollama vision model and return description.
    """
    if not _OLLAMA_AVAILABLE:
        return "Ollama is not installed or not available."
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    try:
        response = ollama.chat(
            model=config.OLLAMA_VISION_MODEL,
            keep_alive=getattr(config, "OLLAMA_KEEP_ALIVE", "30m"),
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "images": [b64],
                }
            ],
        )
        return (response.get("message", {}).get("content") or "No description.").strip()
    except Exception as e:
        return f"Vision model error: {e}"


def what_do_you_see(camera_index: Optional[int] = None, question: Optional[str] = None) -> str:
    """
    Capture from webcam and describe using the vision model.
    If question is provided, asks that specific question about the image.
    """
    png_bytes = capture_frame(camera_index)
    if png_bytes is None:
        return "Could not access the camera. Start the camera preview first, or ensure the webcam is connected and not in use."
    if question and question.strip():
        prompt = f"Answer this question about the image in one or two sentences: {question.strip()}"
        return describe_image(png_bytes, prompt=prompt)
    return describe_image(png_bytes)


def open_camera_stream(camera_index: Optional[int] = None):
    """
    Simple generator yielding BGR frames from the camera.
    The caller is responsible for releasing the capture.
    """
    if not _CV2_AVAILABLE:
        return None
    idx = camera_index if camera_index is not None else config.CAMERA_INDEX
    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        return None
    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            yield frame
    finally:
        cap.release()


def bgr_to_tk_image(frame_bgr, size: Optional[Tuple[int, int]] = None):
    """
    Convert an OpenCV BGR frame to a Pillow Image usable by Tkinter/CTk.
    """
    if frame_bgr is None:
        return None
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    from PIL import Image

    img = Image.fromarray(frame_rgb)
    if size:
        img = img.resize(size)
    return img


def count_fingers_simple(frame_bgr) -> Optional[int]:
    """
    Very lightweight, best-effort finger counter using contour/convex hull.
    This is not perfect but works reasonably for a hand against a simple background.
    """
    if not _CV2_AVAILABLE or _np is None or frame_bgr is None:
        return None
    frame = cv2.resize(frame_bgr, (320, 240))
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thresh = cv2.bitwise_not(thresh)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    cnt = max(contours, key=cv2.contourArea)
    if cv2.contourArea(cnt) < 1000:
        return None
    hull = cv2.convexHull(cnt, returnPoints=False)
    if hull is None or len(hull) < 3:
        return None
    defects = cv2.convexityDefects(cnt, hull)
    if defects is None:
        return None
    finger_gaps = 0
    for i in range(defects.shape[0]):
        s, e, f, d = defects[i, 0]
        start = tuple(cnt[s][0])
        end = tuple(cnt[e][0])
        far = tuple(cnt[f][0])
        a = _np.linalg.norm(_np.array(end) - _np.array(start))
        b = _np.linalg.norm(_np.array(far) - _np.array(start))
        c = _np.linalg.norm(_np.array(end) - _np.array(far))
        if b * c == 0:
            continue
        angle = _np.degrees(_np.arccos((b**2 + c**2 - a**2) / (2 * b * c)))
        if angle < 80 and d > 1000:
            finger_gaps += 1
    fingers = min(finger_gaps + 1, 5)
    if fingers <= 0:
        return None
    return fingers


def locate_in_screenshot(
    image_bytes: bytes, target_description: str
) -> Optional[Union[Tuple[int, int], str]]:
    """
    Use vision model to find where a target element is on screen.
    Returns (x, y) pixel coordinates if found, or a region name as fallback.
    Returns None if target not found or vision fails.
    """
    if not _OLLAMA_AVAILABLE:
        return None
    if not _PIL_AVAILABLE:
        return _locate_region_fallback(image_bytes, target_description)

    try:
        img = Image.open(io.BytesIO(image_bytes))
        orig_w, orig_h = img.size
        scale = 1.0
        max_dim = _VISION_MAX_DIM
        if max(orig_w, orig_h) > max_dim:
            scale = max_dim / max(orig_w, orig_h)
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        scaled_bytes = buf.getvalue()
        img_w, img_h = img.size

        prompt = (
            f"Click target: {target_description}. Image size {img_w}x{img_h}. "
            "Reply ONLY with: X Y (pixel coords of center). Example: 450 320"
        )
        b64 = base64.b64encode(scaled_bytes).decode("utf-8")
        response = ollama.chat(
            model=config.OLLAMA_VISION_MODEL,
            keep_alive=getattr(config, "OLLAMA_KEEP_ALIVE", "30m"),
            messages=[{"role": "user", "content": prompt, "images": [b64]}],
        )
        raw = (response.get("message", {}).get("content") or "").strip()

        coords = _parse_coordinates(raw, img_w, img_h)
        if coords:
            x, y = coords
            real_x = int(x / scale)
            real_y = int(y / scale)
            real_x = max(0, min(orig_w - 1, real_x))
            real_y = max(0, min(orig_h - 1, real_y))
            return (real_x, real_y)

        return _locate_region_fallback(image_bytes, target_description)
    except Exception:
        return _locate_region_fallback(image_bytes, target_description)


def _parse_coordinates(text: str, max_x: int, max_y: int) -> Optional[Tuple[int, int]]:
    """Extract x,y from model response. Expects formats like '450 320' or '450, 320'."""
    if not text:
        return None
    match = re.search(r"(\d+)\s*[,x]\s*(\d+)", text, re.I)
    if match:
        try:
            x = int(match.group(1))
            y = int(match.group(2))
            x = max(0, min(max_x - 1, x))
            y = max(0, min(max_y - 1, y))
            return (x, y)
        except (ValueError, IndexError):
            pass
    parts = re.findall(r"\d+", text)
    if len(parts) >= 2:
        try:
            x = int(parts[0])
            y = int(parts[1])
            x = max(0, min(max_x - 1, x))
            y = max(0, min(max_y - 1, y))
            return (x, y)
        except (ValueError, IndexError):
            pass
    return None


def _locate_region_fallback(image_bytes: bytes, target_description: str) -> Optional[str]:
    """Fallback: ask for region name instead of coordinates."""
    if not _OLLAMA_AVAILABLE:
        return None
    prompt = (
        f"Click: {target_description}. Region? Reply one word: topleft,topcenter,topright,"
        "middleleft,center,middleright,bottomleft,bottomcenter,bottomright"
    )
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    try:
        response = ollama.chat(
            model=config.OLLAMA_VISION_MODEL,
            keep_alive=getattr(config, "OLLAMA_KEEP_ALIVE", "30m"),
            messages=[{"role": "user", "content": prompt, "images": [b64]}],
        )
        raw = (response.get("message", {}).get("content") or "").strip().lower()
        regions = ["topleft", "topcenter", "topright", "middleleft", "center", "middleright",
                   "bottomleft", "bottomcenter", "bottomright"]
        for r in regions:
            if r in raw or r.replace("middle", "mid") in raw:
                return r
        if "top left" in raw or "top-left" in raw:
            return "topleft"
        if "top right" in raw or "top-right" in raw:
            return "topright"
        if "top center" in raw or "top-center" in raw:
            return "topcenter"
        if "bottom left" in raw or "bottom-left" in raw:
            return "bottomleft"
        if "bottom right" in raw or "bottom-right" in raw:
            return "bottomright"
        if "bottom center" in raw or "bottom-center" in raw:
            return "bottomcenter"
        if "middle left" in raw or "mid left" in raw:
            return "middleleft"
        if "middle right" in raw or "mid right" in raw:
            return "middleright"
        if "centre" in raw or "center" in raw:
            return "center"
    except Exception:
        pass
    return None


def describe_screen(question: Optional[str] = None) -> str:
    """Capture the screen (all monitors) and describe it using the vision model."""
    try:
        from . import computer
        png = computer.screenshot_bytes(all_monitors=True)
        if not png:
            return "Could not capture the screen."
        png = _resize_for_vision(png)
        if question and question.strip():
            prompt = f"Screenshot. Answer: {question.strip()}"
        else:
            prompt = "Describe this screenshot in 1-2 sentences."
        return describe_image(png, prompt=prompt)
    except Exception as e:
        return f"Could not describe screen: {e}"


def _resize_for_vision(image_bytes: bytes) -> bytes:
    """Resize image to max dimension for faster vision inference."""
    if not _PIL_AVAILABLE:
        return image_bytes
    try:
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size
        if max(w, h) <= _VISION_MAX_DIM:
            return image_bytes
        scale = _VISION_MAX_DIM / max(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return image_bytes


def describe_hand_gesture() -> str:
    """
    Capture one frame and try to describe how many fingers are extended.
    Uses the live preview frame if available.
    """
    if not _CV2_AVAILABLE:
        return "Hand gesture detection requires OpenCV. Please install opencv-python."
    frame = _preview_frame.get("frame")
    if frame is None:
        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if not cap.isOpened():
            return "Could not access the camera. Start the camera preview first, or ensure the webcam is connected."
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            return "Could not capture an image for gesture detection."
    fingers = count_fingers_simple(frame)
    if fingers is None:
        return "I couldn't confidently detect your hand or fingers. Try moving closer and using a plain background."
    if fingers == 1:
        return "It looks like you are holding up 1 finger."
    return f"It looks like you are holding up {fingers} fingers."
