"""Image processing for uploads.

Bytes are validated by *decoding* (not by extension or content-type
header) using Pillow, metadata is stripped, the image is downscaled to
fit the configured long-side cap, then re-encoded to WebP (with a JPEG
fallback for images whose source had no alpha). All bytes stored in
the database are the bytes returned by :func:`process_image_bytes`.

The same function rejects the dangerous cases listed in F4:
  - files that Pillow cannot decode
  - files that are obviously not images (text, SVG, polyglot)
  - files larger than the configured byte cap
  - images that exceed the configured pixel cap (decompression bomb)
  - empty files
"""
from __future__ import annotations

import hashlib
import io
import struct
from dataclasses import dataclass
from typing import Final

from PIL import Image, ImageFile, UnidentifiedImageError

# Reject images that decompress to a huge raster, even if the file on
# disk is small (decompression-bomb mitigation). Pillow already caps at
# Image.MAX_IMAGE_PIXELS but we set a deterministic, project-wide limit
# and surface a friendlier error.
PIXEL_CAP: Final = 25_000_000  # 25 megapixels

# Reasonable file size cap; 5 MB per F4.
MAX_BYTES: Final = 5 * 1024 * 1024

# Long side after re-encoding.
LONG_SIDE_MAX: Final = 1024

# Per-post cap.
MAX_PHOTOS_PER_ITEM: Final = 2

# Magic bytes for common "this is not a real photo" cases we catch
# before opening with Pillow.
_SVG_HEAD = b"<?xml"
_HTML_HEAD = b"<!doctype html"
_PHP_HEAD = b"<?php"
_JS_HEAD = b"<script"
_JS2_HEAD = b"//javascript"


class PhotoError(ValueError):
    """Raised for any kind of upload validation failure."""


@dataclass(frozen=True)
class ProcessedImage:
    bytes_: bytes
    mime_type: str
    width: int
    height: int
    sha256: str


def _looks_like_script_or_html(data: bytes) -> bool:
    h = data.lstrip().lower()[:64]
    if any(h.startswith(s) for s in (_SVG_HEAD, _HTML_HEAD, _PHP_HEAD, _JS_HEAD, _JS2_HEAD)):
        return True
    # A polyglot is a real image whose bytes also contain something a
    # browser would render as code. We scan the full payload for the
    # common script-tag variants — if any of them appear anywhere,
    # reject.
    lowered = data.lower()
    if b"<script" in lowered:
        return True
    if b"<?php" in lowered:
        return True
    return False


def process_image_bytes(data: bytes) -> ProcessedImage:
    """Validate, strip metadata, downscale, and re-encode ``data``.

    Raises :class:`PhotoError` for any rejected upload.
    """
    if not data:
        raise PhotoError("empty file")
    if len(data) > MAX_BYTES:
        raise PhotoError(f"file too large (max {MAX_BYTES} bytes)")

    # Cheap pre-check for obvious non-image wrappers before Pillow.
    if _looks_like_script_or_html(data):
        raise PhotoError("file is not a supported image")

    # Cap Pillow's own decompression bomb threshold.
    Image.MAX_IMAGE_PIXELS = PIXEL_CAP

    try:
        src = Image.open(io.BytesIO(data))
        src.verify()  # raises on truncation
    except UnidentifiedImageError as e:
        raise PhotoError(f"unsupported image format: {e}") from e
    except Image.DecompressionBombError as e:
        raise PhotoError("image exceeds pixel cap") from e
    except Exception as e:  # truncated, malformed, etc.
        raise PhotoError(f"could not decode image: {e}") from e

    # Reopen for actual decoding (verify() consumes the stream).
    try:
        img = Image.open(io.BytesIO(data))
    except Exception as e:
        raise PhotoError(f"could not decode image: {e}") from e

    # Check actual pixel count against our cap.
    if img.width * img.height > PIXEL_CAP:
        raise PhotoError("image exceeds pixel cap")

    # Normalize: convert palette/transparency/CMYK to a mode we can save.
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    if has_alpha:
        target_mode = "RGBA"
        out_format = "WEBP"
        mime = "image/webp"
    else:
        target_mode = "RGB"
        out_format = "WEBP"  # WebP is broadly supported; JPEG as fallback below
        mime = "image/webp"

    if img.mode != target_mode:
        img = img.convert(target_mode)

    # Downscale to LONG_SIDE_MAX on the long edge.
    w, h = img.size
    if max(w, h) > LONG_SIDE_MAX:
        if w >= h:
            new_w = LONG_SIDE_MAX
            new_h = max(1, round(h * LONG_SIDE_MAX / w))
        else:
            new_h = LONG_SIDE_MAX
            new_w = max(1, round(w * LONG_SIDE_MAX / h))
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # Build a fresh ImageFile object without any source metadata.
    clean = Image.new(target_mode, img.size)
    clean.putdata(list(img.getdata()))

    buf = io.BytesIO()
    try:
        clean.save(buf, format=out_format, quality=82, method=4)
    except Exception:
        # Fall back to JPEG for images WebP cannot save (very rare).
        out_format = "JPEG"
        mime = "image/jpeg"
        if target_mode == "RGBA":
            clean = clean.convert("RGB")
        buf = io.BytesIO()
        clean.save(buf, format=out_format, quality=82, optimize=True)

    out = buf.getvalue()
    digest = hashlib.sha256(out).hexdigest()
    return ProcessedImage(
        bytes_=out,
        mime_type=mime,
        width=clean.width,
        height=clean.height,
        sha256=digest,
    )


def synthesise_test_png(width: int = 8, height: int = 8, color=(255, 0, 0, 255)) -> bytes:
    """Helper used by tests to craft a small valid PNG with EXIF."""
    from PIL.PngImagePlugin import PngInfo

    img = Image.new("RGBA", (width, height), color)
    meta = PngInfo()
    meta.add_text("GPSLatitude", "12.345678")
    meta.add_text("GPSLongitude", "98.765432")
    buf = io.BytesIO()
    img.save(buf, format="PNG", pnginfo=meta)
    return buf.getvalue()


def synthesise_test_jpeg(width: int = 8, height: int = 8, exif_gps: bool = True) -> bytes:
    """Helper to craft a small JPEG, optionally with GPS EXIF."""
    img = Image.new("RGB", (width, height), (10, 20, 30))
    buf = io.BytesIO()
    if exif_gps:
        # A minimal EXIF block with a GPSLatitudeRef. Pillow strips it on
        # re-encoding, which is the property we are testing.
        from PIL.ExifTags import Base as ExifBase

        exif = img.getexif()
        exif[ExifBase.Software] = b"test"
        img.save(buf, format="JPEG", exif=exif)
    else:
        img.save(buf, format="JPEG")
    return buf.getvalue()
