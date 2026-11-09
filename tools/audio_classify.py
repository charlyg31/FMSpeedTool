"""Fusion ou equipement, au son. Modeles construits sur une run de reference
(evenements valides par l'image), puis testes sur d'autres runs.

python tools/audio_classify.py REF_WAV REF_LOG [AUTRE_WAV AUTRE_LOG ...]
"""

import os
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
import audio_lab as al  # noqa: E402

BEFORE, AFTER = 3.0, 0.75     # fenetre autour de l'evenement (l'image le voit a la revelation)
BAND = slice(4, 200)          # ~90 Hz .. 4,3 kHz


def feat(a, t):
    s0 = int(round((t - BEFORE) * al.SR))
    s1 = s0 + int(round((BEFORE + AFTER) * al.SR))   # longueur fixe
    if s0 < 0 or s1 > len(a):
        return None
    sp = al.spec(a[s0:s1])[BAND]
    sp = sp - sp.mean(axis=1, keepdims=True)          # retire le fond (musique, souffle)
    return sp / (np.linalg.norm(sp) + 1e-9)


def best_corr(x, tpl, max_shift=25):
    """Correlation max en decalant dans le temps (+-max_shift colonnes ~ +-0,3 s)."""
    n = min(x.shape[1], tpl.shape[1])
    best = -1.0
    for d in range(-max_shift, max_shift + 1):
        if d >= 0:
            a, b = x[:, d:n], tpl[:, :n - d]
        else:
            a, b = x[:, :n + d], tpl[:, -d:n]
        c = float((a * b).sum() / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
        best = max(best, c)
    return best


def collect(wav, log):
    a = al.load(wav)
    out = []
    for t, kind in al.events(log):
        if kind in "FE":
            f = feat(a, t)
            if f is not None:
                out.append((t, kind, f))
    return out


def templates(items):
    return {k: np.mean([f for _, kk, f in items if kk == k], axis=0) for k in "FE"}


def classify(f, tpl):
    cf, ce = best_corr(f, tpl["F"]), best_corr(f, tpl["E"])
    return ("E" if ce > cf else "F"), cf, ce


def report(name, items, tpl, loo=False):
    ok = n = 0
    wrong = []
    for i, (t, kind, f) in enumerate(items):
        use = tpl
        if loo:                                       # modele sans cet evenement
            rest = items[:i] + items[i + 1:]
            use = templates(rest)
        guess, cf, ce = classify(f, use)
        n += 1
        ok += guess == kind
        if guess != kind:
            wrong.append(f"{t:7.1f}s image={kind} son={guess} (F {cf:.2f} / E {ce:.2f})")
    nf = sum(k == "F" for _, k, _ in items)
    print(f"{name}: {ok}/{n} d'accord avec l'image ({nf} fusions, {n - nf} equipements)")
    for w in wrong[:15]:
        print("   ", w)


ref = collect(sys.argv[1], sys.argv[2])
tpl = templates(ref)
report("reference (chaque evenement exclu de son modele)", ref, tpl, loo=True)
for i in range(3, len(sys.argv), 2):
    report(sys.argv[i], collect(sys.argv[i], sys.argv[i + 1]), tpl)
np.savez(os.path.join(os.environ.get("TEMP", "."), "audio_templates_test.npz"), F=tpl["F"], E=tpl["E"])
