"""Son du jeu : fusion ou equipement ?

Chaque action a son bruitage : la fusion fait un souffle large puis une note
grave tenue, l'equipement finit par une montee de frequence tres nette. L'image
voit qu'il se passe quelque chose (flash, grande carte) ; le son tranche.

Capture : uniquement le son du programme du jeu (ePSXe), avec la capture par
processus de Windows 10 2004+ (pas Discord, pas la musique, pas le micro).
Le son doit sortir d'ePSXe (il peut etre coupe dans le casque).
"""

import ctypes
import ctypes.wintypes as wt
import threading
import time
from collections import deque

import numpy as np

SR = 22050                    # analyse en mono 22,05 kHz
HOP, NFFT = 256, 1024
BEFORE, AFTER = 3.0, 0.75     # fenetre autour de la revelation de la carte
BAND = slice(4, 200)          # ~90 Hz .. 4,3 kHz
MIN_SCORE, MIN_MARGIN = 0.08, 0.05


def spec(x):
    win = np.hanning(NFFT).astype(np.float32)
    n = 1 + (len(x) - NFFT) // HOP
    if n <= 0:
        return None
    idx = np.arange(NFFT)[None, :] + HOP * np.arange(n)[:, None]
    m = np.abs(np.fft.rfft(x[idx] * win, axis=1))[:, 1:NFFT // 2 + 1].T
    return np.log1p(m * 50)


def features(x):
    sp = spec(x)
    if sp is None:
        return None
    sp = sp[BAND]
    sp = sp - sp.mean(axis=1, keepdims=True)          # retire le fond (musique, souffle)
    return sp / (np.linalg.norm(sp) + 1e-9)


def best_corr(x, tpl, max_shift=25):
    n = min(x.shape[1], tpl.shape[1])
    best = -1.0
    for d in range(-max_shift, max_shift + 1):
        a, b = (x[:, d:n], tpl[:, :n - d]) if d >= 0 else (x[:, :n + d], tpl[:, -d:n])
        c = float((a * b).sum() / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
        best = max(best, c)
    return best


class Classifier:
    def __init__(self, path):
        data = np.load(path)
        self.tpl = {"fusion": data["F"], "equip": data["E"]}

    def decide(self, samples):
        """'fusion', 'equip' ou None (son absent ou pas net)."""
        if samples is None or float(np.abs(samples).max(initial=0)) < 1e-3:
            return None
        f = features(samples)
        if f is None:
            return None
        cf, ce = best_corr(f, self.tpl["fusion"]), best_corr(f, self.tpl["equip"])
        if max(cf, ce) < MIN_SCORE or abs(cf - ce) < MIN_MARGIN:
            return None
        return "equip" if ce > cf else "fusion"


class FileSource:
    """Son d'une video (tests) : temps = secondes depuis le debut de la video."""

    def __init__(self, wav_path):
        import wave
        with wave.open(wav_path) as w:
            self.a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768

    def window(self, t0, t1):
        s0, s1 = int(round(t0 * SR)), int(round(t0 * SR)) + int(round((t1 - t0) * SR))
        if s0 < 0 or s1 > len(self.a):
            return None
        return self.a[s0:s1]

    def ready(self, t):
        return True

    status = "fichier"


# --- capture du son d'un processus (WASAPI, Windows 10 2004+) ---------------------

class _Capture:
    """Lit le son d'un processus (et de ses enfants) en continu."""

    def __init__(self, pid, on_samples):
        self.pid, self.on_samples = pid, on_samples
        self.stop = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            self._loop()
        except Exception as e:                      # API absente, droits, processus ferme...
            self.error = f"{type(e).__name__}: {e}"

    def _loop(self):
        import comtypes
        from comtypes import COMMETHOD, GUID, HRESULT, IUnknown

        comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)

        class IAudioCaptureClient(IUnknown):
            _iid_ = GUID("{C8ADBD64-E71E-48a0-A4DE-185C395CD317}")
            _methods_ = [
                COMMETHOD([], HRESULT, "GetBuffer", (["out"], ctypes.POINTER(ctypes.POINTER(ctypes.c_byte))),
                          (["out"], ctypes.POINTER(ctypes.c_uint32)), (["out"], ctypes.POINTER(ctypes.c_uint32)),
                          (["out"], ctypes.POINTER(ctypes.c_uint64)), (["out"], ctypes.POINTER(ctypes.c_uint64))),
                COMMETHOD([], HRESULT, "ReleaseBuffer", (["in"], ctypes.c_uint32)),
                COMMETHOD([], HRESULT, "GetNextPacketSize", (["out"], ctypes.POINTER(ctypes.c_uint32))),
            ]

        class WAVEFORMATEX(ctypes.Structure):
            _fields_ = [("wFormatTag", wt.WORD), ("nChannels", wt.WORD), ("nSamplesPerSec", wt.DWORD),
                        ("nAvgBytesPerSec", wt.DWORD), ("nBlockAlign", wt.WORD), ("wBitsPerSample", wt.WORD),
                        ("cbSize", wt.WORD)]

        class IAudioClient(IUnknown):
            _iid_ = GUID("{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}")
            _methods_ = [
                COMMETHOD([], HRESULT, "Initialize", (["in"], ctypes.c_int), (["in"], wt.DWORD),
                          (["in"], ctypes.c_longlong), (["in"], ctypes.c_longlong),
                          (["in"], ctypes.POINTER(WAVEFORMATEX)), (["in"], ctypes.c_void_p)),
                COMMETHOD([], HRESULT, "GetBufferSize", (["out"], ctypes.POINTER(ctypes.c_uint32))),
                COMMETHOD([], HRESULT, "GetStreamLatency", (["out"], ctypes.POINTER(ctypes.c_longlong))),
                COMMETHOD([], HRESULT, "GetCurrentPadding", (["out"], ctypes.POINTER(ctypes.c_uint32))),
                COMMETHOD([], HRESULT, "IsFormatSupported", (["in"], ctypes.c_int), (["in"], ctypes.c_void_p),
                          (["out"], ctypes.POINTER(ctypes.c_void_p))),
                COMMETHOD([], HRESULT, "GetMixFormat", (["out"], ctypes.POINTER(ctypes.c_void_p))),
                COMMETHOD([], HRESULT, "GetDevicePeriod", (["out"], ctypes.POINTER(ctypes.c_longlong)),
                          (["out"], ctypes.POINTER(ctypes.c_longlong))),
                COMMETHOD([], HRESULT, "Start"),
                COMMETHOD([], HRESULT, "Stop"),
                COMMETHOD([], HRESULT, "Reset"),
                COMMETHOD([], HRESULT, "SetEventHandle", (["in"], wt.HANDLE)),
                COMMETHOD([], HRESULT, "GetService", (["in"], ctypes.POINTER(GUID)),
                          (["out"], ctypes.POINTER(ctypes.POINTER(IUnknown)))),
            ]

        class IActivateAudioInterfaceAsyncOperation(IUnknown):
            _iid_ = GUID("{72A22D78-CDE4-431D-B8CC-843A71199B6D}")
            _methods_ = [
                COMMETHOD([], HRESULT, "GetActivateResult", (["out"], ctypes.POINTER(HRESULT)),
                          (["out"], ctypes.POINTER(ctypes.POINTER(IUnknown)))),
            ]

        class IActivateAudioInterfaceCompletionHandler(IUnknown):
            _iid_ = GUID("{41D949AB-9862-444A-80F6-C261334DA5EB}")
            _methods_ = [
                COMMETHOD([], HRESULT, "ActivateCompleted",
                          (["in"], ctypes.POINTER(IActivateAudioInterfaceAsyncOperation))),
            ]

        class IAgileObject(IUnknown):
            _iid_ = GUID("{94ea2b94-e9cc-49e0-c0ff-ee64ca8f5b90}")
            _methods_ = []

        done = threading.Event()

        class Handler(comtypes.COMObject):
            _com_interfaces_ = [IActivateAudioInterfaceCompletionHandler, IAgileObject]

            def ActivateCompleted(self, op):
                done.set()
                return 0

        class PROCESS_LOOPBACK_PARAMS(ctypes.Structure):
            _fields_ = [("TargetProcessId", wt.DWORD), ("ProcessLoopbackMode", ctypes.c_int)]

        class ACTIVATION_PARAMS(ctypes.Structure):
            _fields_ = [("ActivationType", ctypes.c_int), ("ProcessLoopbackParams", PROCESS_LOOPBACK_PARAMS)]

        class BLOB(ctypes.Structure):
            _fields_ = [("cbSize", wt.ULONG), ("pBlobData", ctypes.c_void_p)]

        class PROPVARIANT(ctypes.Structure):
            _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort),
                        ("r3", ctypes.c_ushort), ("blob", BLOB)]

        params = ACTIVATION_PARAMS(1, PROCESS_LOOPBACK_PARAMS(self.pid, 0))   # processus + enfants
        pv = PROPVARIANT()
        pv.vt = 65                                                              # VT_BLOB
        pv.blob = BLOB(ctypes.sizeof(params), ctypes.cast(ctypes.pointer(params), ctypes.c_void_p))
        handler = Handler()
        op = ctypes.POINTER(IActivateAudioInterfaceAsyncOperation)()
        mmdev = ctypes.WinDLL("Mmdevapi.dll")
        fn = mmdev.ActivateAudioInterfaceAsync
        fn.argtypes = [wt.LPCWSTR, ctypes.POINTER(GUID), ctypes.POINTER(PROPVARIANT), ctypes.c_void_p,
                       ctypes.POINTER(ctypes.POINTER(IActivateAudioInterfaceAsyncOperation))]
        fn.restype = HRESULT
        iid = IAudioClient._iid_
        hp = handler.QueryInterface(IActivateAudioInterfaceCompletionHandler)
        fn("VAD\\Process_Loopback", ctypes.byref(iid), ctypes.byref(pv), ctypes.cast(hp, ctypes.c_void_p),
           ctypes.byref(op))
        if not done.wait(5):
            raise TimeoutError("activation du son sans reponse")
        hr, unk = op.GetActivateResult()
        if hr != 0:
            raise OSError(f"activation du son refusee (0x{hr & 0xffffffff:08x})")
        client = unk.QueryInterface(IAudioClient)
        fmt = WAVEFORMATEX(1, 2, 44100, 44100 * 4, 4, 16, 0)                    # PCM 16 bits stereo
        flags = 0x00020000 | 0x00040000 | 0x80000000 | 0x08000000                 # loopback, event, conversion
        client.Initialize(0, flags, 200000, 0, ctypes.byref(fmt), None)
        ev = ctypes.windll.kernel32.CreateEventW(None, False, False, None)
        client.SetEventHandle(ev)
        svc = client.GetService(ctypes.byref(IAudioCaptureClient._iid_))
        cap = svc.QueryInterface(IAudioCaptureClient)
        client.Start()
        try:
            while not self.stop.is_set():
                ctypes.windll.kernel32.WaitForSingleObject(ev, 100)
                while True:
                    n = cap.GetNextPacketSize()
                    if not n:
                        break
                    data, frames, flg, _pos, _qpc = cap.GetBuffer()
                    if frames:
                        if flg & 0x2:                                           # silence
                            pcm = np.zeros((frames, 2), np.float32)
                        else:
                            raw = ctypes.string_at(data, frames * 4)
                            pcm = np.frombuffer(raw, np.int16).reshape(-1, 2).astype(np.float32) / 32768
                        self.on_samples(pcm.mean(axis=1)[::2].copy(), time.monotonic())  # mono 22,05 kHz
                    cap.ReleaseBuffer(frames)
        finally:
            client.Stop()


class LiveSource:
    """Son en direct du processus de la fenetre du jeu, horodate (time.monotonic)."""

    KEEP = 8.0                   # secondes gardees

    def __init__(self):
        self.lock = threading.Lock()
        self.chunks = deque()    # (t_fin, echantillons)
        self.pid = None
        self.capture = None
        self.last_sound = 0.0

    def follow(self, hwnd):
        """A appeler avec la fenetre du jeu : (re)lance la capture si le processus change."""
        if not hwnd:
            return
        pid = wt.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value and pid.value != self.pid:
            if self.capture is not None:
                self.capture.stop.set()
            self.pid = pid.value
            with self.lock:
                self.chunks.clear()
            self.capture = _Capture(self.pid, self._push)

    def _push(self, samples, t_end):
        with self.lock:
            self.chunks.append((t_end, samples))
            if float(np.abs(samples).max(initial=0)) > 1e-3:
                self.last_sound = t_end
            while self.chunks and self.chunks[0][0] < t_end - self.KEEP:
                self.chunks.popleft()

    def ready(self, t):
        with self.lock:
            return bool(self.chunks) and self.chunks[-1][0] >= t

    def window(self, t0, t1):
        with self.lock:
            if not self.chunks:
                return None
            t_end = self.chunks[-1][0]
            allx = np.concatenate([c for _, c in self.chunks])
        n = int(round((t1 - t0) * SR))
        end = len(allx) - int(round((t_end - t1) * SR))
        if end > len(allx) or end - n < 0:
            return None
        return allx[end - n:end]

    @property
    def status(self):
        if self.capture is None:
            return "en attente du jeu"
        if self.capture.error:
            return "indisponible"
        return "OK" if time.monotonic() - self.last_sound < 30 else "silence"
