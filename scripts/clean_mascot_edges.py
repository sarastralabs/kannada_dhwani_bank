"""Remove light specks left under the chin when the poses were cut out of the cream sheet.

    python scripts/clean_mascot_edges.py

Looks only at a thin band just below each face plate (eye highlights are untouched) and
repaints tiny cream islands there with the surrounding dark body colour. Safe to re-run.
"""

from __future__ import annotations

import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "public", "mascot")
POSES = ["greeting", "listening", "thinking", "speaking", "happy", "confused"]


def clean(name: str) -> int:
    path = os.path.join(OUT, f"{name}.png")
    im = Image.open(path).convert("RGBA")
    a = np.array(im).astype(int)
    alpha = a[..., 3] > 200
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    cream = alpha & (r > 200) & (g > 185) & (b > 150) & (r - b < 90)

    lab, n = ndi.label(ndi.binary_closing(cream, iterations=2))
    best = None
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        if len(ys) < 4000 or ys.mean() > 0.62 * im.height:
            continue
        if best is None or len(ys) > best[1]:
            best = (i, len(ys))
    face = lab == best[0]
    ys, xs = np.where(face)
    bottom = ys.max()

    band = np.zeros_like(face)
    band[bottom - 8: bottom + 22, :] = True
    near_face = ndi.binary_dilation(face, iterations=2)
    specks = cream & band & ~near_face
    sl, sn = ndi.label(ndi.binary_dilation(specks, iterations=1))
    fixed = 0
    dark = alpha & ((r + g + b) < 420)
    for i in range(1, sn + 1):
        m = sl == i
        if m.sum() > 160:
            continue  # a real feature, not a speck
        for y, x in zip(*np.where(m & cream)):
            y0, y1, x0, x1 = max(0, y - 4), y + 5, max(0, x - 4), x + 5
            win = dark[y0:y1, x0:x1]
            if win.sum() < 4:
                continue
            px = a[y0:y1, x0:x1][win][:, :3]
            a[y, x, :3] = np.median(px, axis=0)
            fixed += 1
    Image.fromarray(a.astype("uint8"), "RGBA").save(path, optimize=True)
    return fixed


if __name__ == "__main__":
    for pose in POSES:
        print(pose, "specks repainted:", clean(pose))
