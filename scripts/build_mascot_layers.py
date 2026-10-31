"""Cut blink and mouth layers out of the mascot poses (frontend/public/mascot/*.png).

    python scripts/build_mascot_layers.py

Writes, next to the poses:
  blink-<pose>.png        eyelids shut (cream patch + lash line) for every pose with open eyes
  mouth-speaking-0..3.png closed / small / medium / wide mouth for the "speaking" pose
  layers.json             what was generated

Each layer is a full 512x512 transparent overlay, so it lines up with its pose with no maths.
Run it again whenever the pose artwork changes. Needs numpy, scipy, Pillow.
"""

from __future__ import annotations

import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "frontend", "public", "mascot")
OPEN_EYED = ["greeting", "listening", "thinking", "speaking", "confused"]  # "happy" already has closed eyes
SS = 4  # supersampling for smooth drawn edges
INK = (38, 34, 62, 255)
LIP = (113, 40, 34, 255)


def analyse(name: str):
    im = Image.open(os.path.join(OUT, f"{name}.png")).convert("RGBA")
    a = np.array(im).astype(int)
    alpha = a[..., 3] > 200
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    cream = alpha & (r > 222) & (g > 200) & (b > 165) & (r - b < 65)
    lab, n = ndi.label(ndi.binary_closing(cream, iterations=2))
    best = None
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        if len(ys) < 4000 or ys.mean() > 0.62 * im.height:
            continue
        if best is None or len(ys) > best[1]:
            best = (i, len(ys))
    face = lab == best[0]
    filled = ndi.binary_fill_holes(ndi.binary_closing(face, iterations=3))
    hl, hn = ndi.label(filled & ~face)
    holes = []
    for i in range(1, hn + 1):
        m = hl == i
        ys, xs = np.where(m)
        if len(ys) < 150:
            continue
        holes.append({"mask": m, "area": len(ys), "box": (xs.min(), ys.min(), xs.max(), ys.max()), "rgb": a[m][:, :3].mean(axis=0)})
    eyes = sorted([h for h in holes if h["rgb"].sum() < 260 and h["rgb"][0] < 80], key=lambda h: -h["area"])[:2]
    mouth = [h for h in holes if h["rgb"][0] > 85 and h["rgb"][1] < 70 and h["rgb"][2] < 70]
    mouth = max(mouth, key=lambda h: h["area"]) if mouth else None
    return im, a, face, sorted(eyes, key=lambda h: h["box"][0]), mouth


def skin_colour(a: np.ndarray, face: np.ndarray, box, pad=14) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    sub = face[max(0, y0 - pad): y1 + pad, max(0, x0 - pad): x1 + pad]
    px = a[max(0, y0 - pad): y1 + pad, max(0, x0 - pad): x1 + pad][sub][:, :3]
    return tuple(int(v) for v in np.median(px, axis=0)) + (255,)


def new_layer(size):
    return Image.new("RGBA", (size[0] * SS, size[1] * SS), (0, 0, 0, 0))


def finish(layer: Image.Image, size) -> Image.Image:
    return layer.resize(size, Image.LANCZOS)


def soft_patch(size, ellipses, skin, blur=2.6) -> Image.Image:
    """Skin-coloured patch with a feathered edge, so it melts into the face (no visible ring)."""
    mask = Image.new("L", (size[0] * SS, size[1] * SS), 0)
    d = ImageDraw.Draw(mask)
    for box in ellipses:
        d.ellipse([v * SS for v in box], fill=255)
    mask = mask.resize(size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(blur))
    patch = Image.new("RGBA", size, skin)
    patch.putalpha(mask)
    return patch


def build_blink(name: str) -> dict:
    im, a, face, eyes, _ = analyse(name)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    detail = new_layer(im.size)
    d = ImageDraw.Draw(detail)
    for e in eyes:
        x0, y0, x1, y1 = e["box"]
        skin = skin_colour(a, face, e["box"])
        pad = 8  # also covers the faint socket outline just outside the dark eye
        out.alpha_composite(soft_patch(im.size, [(x0 - pad, y0 - pad, x1 + pad, y1 + pad)], skin, blur=3.4))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 + (y1 - y0) * 0.08
        w, h = (x1 - x0) * 0.46, (y1 - y0) * 0.16
        # lash line: a shallow "smile" arc, like a closed cartoon eye
        d.arc([(cx - w) * SS, (cy - h * 2) * SS, (cx + w) * SS, (cy + h * 2) * SS], 20, 160, fill=INK, width=int(3.4 * SS))
    out.alpha_composite(finish(detail, im.size))
    out.save(os.path.join(OUT, f"blink-{name}.png"), optimize=True)
    return {"eyes": [list(map(int, e["box"])) for e in eyes]}


def build_mouths(name: str = "speaking") -> dict:
    im, a, face, _, mouth = analyse(name)
    assert mouth is not None, "no mouth found"
    x0, y0, x1, y1 = (int(v) for v in mouth["box"])
    skin = skin_colour(a, face, mouth["box"], pad=18)
    # the original mouth, cut out with its own soft edge
    m = Image.fromarray((ndi.binary_dilation(mouth["mask"], iterations=1) * 255).astype("uint8"))
    m = m.filter(__import__("PIL.ImageFilter", fromlist=["x"]).GaussianBlur(0.8))
    crop_rgb = im.crop((x0 - 2, y0 - 2, x1 + 3, y1 + 3))
    crop_a = m.crop((x0 - 2, y0 - 2, x1 + 3, y1 + 3))
    crop = crop_rgb.copy()
    crop.putalpha(crop_a)
    cw, ch = crop.size
    cx = (x0 + x1) / 2
    top = y0
    frames = []
    # (width scale, height scale): closed is drawn as a smile line instead of a squashed mouth
    shapes = [None, (0.82, 0.42), (0.95, 0.78), (1.08, 1.12)]
    for i, shape in enumerate(shapes):
        out = soft_patch(im.size, [(x0 - 13, y0 - 9, x1 + 13, y1 + 17)], skin)
        layer = new_layer(im.size)
        d = ImageDraw.Draw(layer)
        if shape is None:
            w = (x1 - x0) * 0.46
            cy = top + ch * 0.18
            d.arc([(cx - w) * SS, (cy - 7) * SS, (cx + w) * SS, (cy + 9) * SS], 18, 162, fill=LIP, width=int(3.4 * SS))
        else:
            sw, sh = shape
            scaled = crop.resize((max(1, int(cw * sw * SS)), max(1, int(ch * sh * SS))), Image.LANCZOS)
            layer.alpha_composite(scaled, (int((cx - cw * sw / 2) * SS), int((top - 2) * SS)))
        out.alpha_composite(finish(layer, im.size))
        out.save(os.path.join(OUT, f"mouth-{name}-{i}.png"), optimize=True)
        frames.append(i)
    return {"box": [x0, y0, x1, y1], "frames": frames}


def main() -> None:
    info = {"blink": {}, "mouth": {}}
    for pose in OPEN_EYED:
        info["blink"][pose] = build_blink(pose)
        print("blink", pose, info["blink"][pose]["eyes"])
    info["mouth"]["speaking"] = build_mouths("speaking")
    print("mouth", info["mouth"]["speaking"])
    with open(os.path.join(OUT, "layers.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)


if __name__ == "__main__":
    main()
