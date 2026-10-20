"""Screenshot helpers: downscaling for the model, data URLs, and before/after difference images."""
from __future__ import annotations

import base64
import io
from pathlib import Path

import numpy as np
from PIL import Image


def png_size(png: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(png)) as im:
        return im.size


def downscale_png(png: bytes, size: tuple[int, int]) -> bytes:
    """Resize to the screenshot size the model sees (VisualSkill: 1920x1080 native -> 1280x720, Lanczos)."""
    with Image.open(io.BytesIO(png)) as im:
        im = im.convert("RGB")
        if im.size != tuple(size):
            im = im.resize(tuple(size), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return buf.getvalue()


def data_url(png: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64," + base64.b64encode(png).decode()


def file_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
    return data_url(path.read_bytes(), mime)


def effect_images(before: Path, after: Path, out_prefix: Path, ignore: list | tuple = (),
                  threshold: int = 16, min_fraction: float = 0.0005, margin: int = 24) -> dict:
    """Compare two native screenshots.  When more than `min_fraction` of the pixels changed by more than
    `threshold` (outside the `ignore` boxes, e.g. the clock in the top bar), save crops of the changed region:
    <prefix>_before.png, <prefix>_after.png and <prefix>_diff.png (red = magnitude of change)."""
    with Image.open(before) as ia, Image.open(after) as ib:
        a_img, b_img = ia.convert("RGB"), ib.convert("RGB")
    if a_img.size != b_img.size:
        return {"changed_fraction": None, "note": f"size changed {a_img.size} -> {b_img.size}"}
    a = np.asarray(a_img, dtype=np.int16)
    b = np.asarray(b_img, dtype=np.int16)
    d = np.abs(a - b).max(axis=2)
    mask = d > threshold
    for x0, y0, x1, y1 in ignore:
        mask[y0:y1, x0:x1] = False
    frac = float(mask.mean())
    out = {"changed_fraction": round(frac, 6)}
    if frac < min_fraction:
        return out
    ys, xs = np.nonzero(mask)
    h, w = mask.shape
    x0, x1 = max(int(xs.min()) - margin, 0), min(int(xs.max()) + margin + 1, w)
    y0, y1 = max(int(ys.min()) - margin, 0), min(int(ys.max()) + margin + 1, h)
    box = (x0, y0, x1, y1)
    a_crop, b_crop = a_img.crop(box), b_img.crop(box)
    gray = (np.asarray(b_crop.convert("L"), dtype=np.uint16) // 3).astype(np.uint8)
    red = np.clip(d[y0:y1, x0:x1].astype(np.int32) * 4, 0, 255).astype(np.uint8)
    heat = Image.fromarray(np.stack([np.maximum(gray, red), gray, gray], axis=2), "RGB")
    paths = {}
    for name, im in (("before", a_crop), ("after", b_crop), ("diff", heat)):
        p = out_prefix.parent / f"{out_prefix.name}_{name}.png"
        im.save(p)
        paths[name] = p
    out.update({"bbox": [x0, y0, x1, y1], "paths": paths})
    return out
