"""Capture de l'image de la fenetre ePSXe (aucune lecture memoire)."""

import ctypes
import ctypes.wintypes as wt

import numpy as np

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

try:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor v2
except (AttributeError, OSError):
    pass

WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wt.LPARAM]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
user32.GetWindowDC.argtypes = [wt.HWND]
user32.GetWindowDC.restype = wt.HDC
user32.GetDC.argtypes = [wt.HWND]
user32.GetDC.restype = wt.HDC
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.IsIconic.argtypes = [wt.HWND]
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wt.HBITMAP
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.BitBlt.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                         wt.HDC, ctypes.c_int, ctypes.c_int, wt.DWORD]
gdi32.GetDIBits.argtypes = [wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, ctypes.c_void_p,
                            ctypes.c_void_p, wt.UINT]
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]

SRCCOPY = 0x00CC0020
PW_CLIENTONLY = 0x1
PW_RENDERFULLCONTENT = 0x2


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


def find_epsxe_window():
    """Fenetre principale d'ePSXe (titre commencant par 'ePSXe'), la plus grande."""
    found = []

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title, 256)
        if title.value.lower().startswith("epsxe"):
            r = wt.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(r))
            found.append((r.right * r.bottom, hwnd, title.value))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    if not found:
        return None
    found.sort(reverse=True)
    return found[0][1]


def window_title(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def client_rect_on_screen(hwnd):
    r = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    p = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(p))
    return p.x, p.y, r.right, r.bottom


def _grab(hwnd, use_printwindow):
    x, y, w, h = client_rect_on_screen(hwnd)
    if w <= 0 or h <= 0:
        return None
    if use_printwindow:
        src = user32.GetDC(hwnd)
    else:
        src = user32.GetDC(None)
    mem = gdi32.CreateCompatibleDC(src)
    bmp = gdi32.CreateCompatibleBitmap(src, w, h)
    old = gdi32.SelectObject(mem, bmp)
    try:
        if use_printwindow:
            user32.PrintWindow(hwnd, mem, PW_CLIENTONLY | PW_RENDERFULLCONTENT)
        else:
            gdi32.BitBlt(mem, 0, 0, w, h, src, x, y, SRCCOPY)
        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(bmi)
        bmi.biWidth = w
        bmi.biHeight = -h
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        buf = np.empty((h, w, 4), dtype=np.uint8)
        gdi32.GetDIBits(mem, bmp, 0, h, buf.ctypes.data, ctypes.byref(bmi), 0)
        return buf[:, :, :3].copy()  # BGR
    finally:
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(hwnd if use_printwindow else None, src)


user32.WindowFromPoint.argtypes = [wt.POINT]
user32.WindowFromPoint.restype = wt.HWND
user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
user32.GetAncestor.restype = wt.HWND
GA_ROOT = 2


def is_covered(hwnd):
    """Une autre fenetre recouvre-t-elle la zone de jeu ? (la capture copie l'ecran)"""
    x, y, w, h = client_rect_on_screen(hwnd)
    for fx, fy in ((0.5, 0.5), (0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9)):
        top = user32.WindowFromPoint(wt.POINT(int(x + w * fx), int(y + h * fy)))
        if user32.GetAncestor(top, GA_ROOT) != hwnd:
            return True
    return False


class DxgiGrabber:
    """Capture par duplication d'ecran DirectX (dxcam) : ~1 ms par image contre
    ~28 ms pour une copie GDI de 1920x1536, ce qui permet 60 img/s."""

    def __init__(self):
        import dxcam                      # absent -> ImportError, on reste en GDI
        self.dxcam = dxcam
        self.cams = {}
        self.last = None

    def _camera_for(self, x, y, w, h):
        for idx in range(8):
            try:
                cam = self.cams.get(idx) or self.dxcam.create(output_idx=idx, output_color="BGR")
            except Exception:
                return None, None
            if cam is None:
                return None, None
            self.cams[idx] = cam
            d = cam._output.desc.DesktopCoordinates
            if d.left <= x and d.top <= y and x + w <= d.right and y + h <= d.bottom:
                return cam, (x - d.left, y - d.top, x - d.left + w, y - d.top + h)
        return None, None

    def grab(self, rect):
        cam, region = self._camera_for(*rect)
        if cam is None:
            return None                   # fenetre a cheval sur deux ecrans : GDI
        frame = cam.grab(region=region)
        if frame is not None:
            self.last = frame
        # Pas d'image neuve = ecran inchange depuis la derniere capture.
        return self.last if self.last is not None and self.last.shape[:2] == (rect[3], rect[2]) else None


class WindowCapture:
    """Capture la zone client d'ePSXe telle qu'affichee a l'ecran : la fenetre doit
    etre visible (PrintWindow rend une image partielle et figee avec le GPU d'ePSXe).
    DXGI si possible (60 img/s), sinon copie GDI."""

    def __init__(self):
        self.hwnd = None
        self.method = "screen"
        self.covered = False
        try:
            self.dxgi = DxgiGrabber()
        except Exception:
            self.dxgi = None

    def ensure_window(self):
        if self.hwnd and user32.IsWindowVisible(self.hwnd):
            return True
        self.hwnd = find_epsxe_window()
        return self.hwnd is not None

    def grab(self):
        if not self.ensure_window() or user32.IsIconic(self.hwnd):
            return None
        self.covered = is_covered(self.hwnd)
        if self.covered:
            return None  # l'image serait celle de la fenetre du dessus
        if self.dxgi is not None:
            try:
                img = self.dxgi.grab(client_rect_on_screen(self.hwnd))
            except Exception:
                self.dxgi = None          # pilote ou session incompatibles : GDI
                img = None
            if img is not None:
                self.method = "dxgi"
                return img
        img = _grab(self.hwnd, self.method == "printwindow")
        if img is not None and self.method == "printwindow" and img.max() < 8:
            # Rendu OpenGL/D3D non capture par PrintWindow : on bascule sur l'ecran.
            self.method = "screen"
            img = _grab(self.hwnd, False)
        return img
