"""Capture de la fenetre du jeu : version Windows (capture_win) ou Linux X11 (capture_x11).
Les deux offrent la meme chose : WindowCapture (grab, set_source, reset, hwnd, covered) et
list_windows."""

import sys

if sys.platform == "win32":
    from capture_win import WindowCapture, list_windows  # noqa: F401
else:
    from capture_x11 import WindowCapture, list_windows  # noqa: F401
