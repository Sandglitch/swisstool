"""Milestone 1: Image tools for SwissKnife.

Includes:
- Convert (PNG, JPEG, WebP, BMP, TIFF, GIF, ICO)
- Resize (Fit inside, Exact, Percent)
- Compress to target (target KB or quality)
- Crop & Rotate (rotation, flip, aspect/square/margins)
- EXIF (view, strip all, remove GPS)
- Watermark (text, position, opacity, color)
- Favicon / ICO generator
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, ImageDraw, ImageFont
from PIL.ExifTags import TAGS, GPSTAGS

# Optional HEIC support
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass

from ..core.tool import (
    Tool,
    Category,
    Param,
    Choice,
    Int,
    Bool,
    Text,
    JobContext,
    RunResult,
    ToolError,
)


def _open_image_rgb_or_rgba(src: Path) -> Image.Image:
    """Open an image, ensuring proper handling of modes."""
    try:
        img = Image.open(src)
        img.load()
        return img
    except Exception as e:
        raise ToolError(f"Could not open image '{src.name}': {e}")


def _rgba_to_rgb(img: Image.Image, bg_color: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    """Convert an RGBA or palette image to RGB with a solid background."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        converted = img.convert("RGBA")
        background = Image.new("RGB", converted.size, bg_color)
        background.paste(converted, mask=converted.split()[-1])
        return background
    elif img.mode != "RGB":
        return img.convert("RGB")
    return img


# =============================================================================
# 1. Convert Image Format
# =============================================================================

class ConvertImageTool(Tool):
    id = "image.convert"
    name = "Convert Format"
    category = Category.IMAGES
    description = "Convert images between formats (PNG, JPEG, WebP, BMP, TIFF, GIF, ICO)."
    accepts = ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp", "*.tiff", "*.tif", "*.gif", "*.ico", "*.heic"]
    params = [
        Choice("target_format", "Target format", ["PNG", "JPEG", "WebP", "BMP", "TIFF", "GIF", "ICO"], default="PNG"),
        Int("quality", "Quality (JPEG / WebP)", default=90, minimum=1, maximum=100, suffix="%"),
        Bool("optimize", "Optimize output file", default=True),
    ]

    def plan(self, files: list[Path], params: dict[str, Any], ctx: JobContext) -> list[str]:
        fmt = params.get("target_format", "PNG").lower()
        ext = ".jpg" if fmt == "jpeg" else f".{fmt}"
        return [f"{f.name} -> {ctx.out_path(f, ext=ext).name}" for f in files]

    def preview(self, file: Path, params: dict[str, Any]) -> Image.Image | None:
        try:
            with _open_image_rgb_or_rgba(file) as img:
                fmt_name = params.get("target_format", "PNG")
                if fmt_name in ("JPEG", "BMP"):
                    return _rgba_to_rgb(img)
                return img.copy()
        except Exception:
            return None

    def run(self, files: list[Path], params: dict[str, Any], ctx: JobContext) -> RunResult:
        if not files:
            raise ToolError("No files selected to convert.")

        fmt_name = params.get("target_format", "PNG")
        quality = int(params.get("quality", 90))
        optimize = bool(params.get("optimize", True))

        fmt_lower = fmt_name.lower()
        ext = ".jpg" if fmt_lower == "jpeg" else f".{fmt_lower}"
        pil_format = "JPEG" if fmt_lower == "jpeg" else fmt_name.upper()

        outputs: list[Path] = []
        total = len(files)

        for i, src in enumerate(files):
            ctx.check_cancelled()
            ctx.progress(i, total, f"Converting {src.name}...")

            with _open_image_rgb_or_rgba(src) as img:
                out = ctx.out_path(src, ext=ext)

                save_kw: dict[str, Any] = {}
                if pil_format in ("JPEG", "WEBP"):
                    save_kw["quality"] = quality
                if pil_format in ("JPEG", "PNG", "WEBP"):
                    save_kw["optimize"] = optimize

                # Formats like JPEG and BMP cannot take RGBA
                if pil_format in ("JPEG", "BMP"):
                    save_img = _rgba_to_rgb(img)
                elif pil_format == "ICO":
                    save_img = img.resize((256, 256), Image.Resampling.LANCZOS)
                else:
                    save_img = img

                save_img.save(out, format=pil_format, **save_kw)
                outputs.append(out)
                ctx.log(f"Converted: {src.name} -> {out.name}")

        ctx.progress(total, total, "Finished conversion.")
        return RunResult(outputs=outputs, message=f"Successfully converted {len(outputs)} image(s).")


# =============================================================================
# 2. Resize Images
# =============================================================================

class ResizeImageTool(Tool):
    id = "image.resize"
    name = "Resize Images"
    category = Category.IMAGES
    description = "Resize images by pixel dimensions, percentage, or fit inside a bounding box."
    accepts = ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp", "*.tiff", "*.tif", "*.gif"]
    params = [
        Choice("mode", "Mode", ["Fit inside box", "Exact dimensions", "Percentage"], default="Fit inside box"),
        Int("width", "Width", default=1280, minimum=1, maximum=50000, suffix="px / %"),
        Int("height", "Height", default=720, minimum=1, maximum=50000, suffix="px / %"),
        Bool("keep_aspect", "Keep aspect ratio", default=True),
        Choice("resample", "Resampling quality", ["Lanczos (High quality)", "Bicubic", "Bilinear", "Nearest"], default="Lanczos (High quality)"),
    ]

    _FILTERS = {
        "Lanczos (High quality)": Image.Resampling.LANCZOS,
        "Bicubic": Image.Resampling.BICUBIC,
        "Bilinear": Image.Resampling.BILINEAR,
        "Nearest": Image.Resampling.NEAREST,
    }

    def plan(self, files: list[Path], params: dict[str, Any], ctx: JobContext) -> list[str]:
        mode = params.get("mode", "Fit inside box")
        w = params.get("width", 1280)
        h = params.get("height", 720)
        return [f"{f.name} -> {ctx.out_path(f, suffix='_resized').name} ({mode}: {w}x{h})" for f in files]

    def preview(self, file: Path, params: dict[str, Any]) -> Image.Image | None:
        try:
            with _open_image_rgb_or_rgba(file) as img:
                mode = params.get("mode", "Fit inside box")
                target_w = int(params.get("width", 1280))
                target_h = int(params.get("height", 720))
                keep_aspect = bool(params.get("keep_aspect", True))
                filter_choice = self._FILTERS.get(params.get("resample", ""), Image.Resampling.LANCZOS)

                orig_w, orig_h = img.size

                if mode == "Percentage":
                    scale_x = target_w / 100.0
                    scale_y = (target_w if keep_aspect else target_h) / 100.0
                    new_w = max(1, int(orig_w * scale_x))
                    new_h = max(1, int(orig_h * scale_y))
                elif mode == "Fit inside box":
                    ratio = min(target_w / orig_w, target_h / orig_h)
                    new_w = max(1, int(orig_w * ratio))
                    new_h = max(1, int(orig_h * ratio))
                else:  # Exact dimensions
                    if keep_aspect:
                        ratio = min(target_w / orig_w, target_h / orig_h)
                        new_w = max(1, int(orig_w * ratio))
                        new_h = max(1, int(orig_h * ratio))
                    else:
                        new_w, new_h = target_w, target_h

                return img.resize((new_w, new_h), filter_choice)
        except Exception:
            return None

    def run(self, files: list[Path], params: dict[str, Any], ctx: JobContext) -> RunResult:
        if not files:
            raise ToolError("No files selected to resize.")

        mode = params.get("mode", "Fit inside box")
        target_w = int(params.get("width", 1280))
        target_h = int(params.get("height", 720))
        keep_aspect = bool(params.get("keep_aspect", True))
        filter_choice = self._FILTERS.get(params.get("resample", ""), Image.Resampling.LANCZOS)

        outputs: list[Path] = []
        total = len(files)

        for i, src in enumerate(files):
            ctx.check_cancelled()
            ctx.progress(i, total, f"Resizing {src.name}...")

            with _open_image_rgb_or_rgba(src) as img:
                orig_w, orig_h = img.size

                if mode == "Percentage":
                    scale_x = target_w / 100.0
                    scale_y = (target_w if keep_aspect else target_h) / 100.0
                    new_w = max(1, int(orig_w * scale_x))
                    new_h = max(1, int(orig_h * scale_y))

                elif mode == "Fit inside box":
                    ratio = min(target_w / orig_w, target_h / orig_h)
                    new_w = max(1, int(orig_w * ratio))
                    new_h = max(1, int(orig_h * ratio))

                else:  # Exact dimensions
                    if keep_aspect:
                        ratio = min(target_w / orig_w, target_h / orig_h)
                        new_w = max(1, int(orig_w * ratio))
                        new_h = max(1, int(orig_h * ratio))
                    else:
                        new_w, new_h = target_w, target_h

                resized = img.resize((new_w, new_h), filter_choice)
                out = ctx.out_path(src, suffix="_resized")

                save_kw: dict[str, Any] = {}
                if img.format in ("JPEG", "WEBP"):
                    save_kw["quality"] = 92

                resized.save(out, format=img.format or "PNG", **save_kw)
                outputs.append(out)
                ctx.log(f"Resized: {src.name} ({orig_w}x{orig_h} -> {new_w}x{new_h}) -> {out.name}")

        ctx.progress(total, total, "Finished resizing.")
        return RunResult(outputs=outputs, message=f"Successfully resized {len(outputs)} image(s).")


# =============================================================================
# 3. Compress Image (Target Size / Quality)
# =============================================================================

class CompressImageTool(Tool):
    id = "image.compress"
    name = "Compress Images"
    category = Category.IMAGES
    description = "Compress images to meet a target file size (KB) or quality reduction."
    accepts = ["*.jpg", "*.jpeg", "*.webp", "*.png"]
    params = [
        Choice("mode", "Compression mode", ["Target file size (KB)", "Quality reduction"], default="Target file size (KB)"),
        Int("target_kb", "Target maximum size", default=300, minimum=10, maximum=100000, suffix="KB"),
        Int("quality", "Quality (for Quality mode)", default=75, minimum=1, maximum=95, suffix="%"),
        Bool("strip_metadata", "Strip EXIF / metadata", default=True),
    ]

    def plan(self, files: list[Path], params: dict[str, Any], ctx: JobContext) -> list[str]:
        mode = params.get("mode", "Target file size (KB)")
        target = f"{params.get('target_kb', 300)} KB" if mode.startswith("Target") else f"Quality {params.get('quality', 75)}%"
        return [f"{f.name} ({f.stat().st_size // 1024} KB) -> {ctx.out_path(f, suffix='_compressed').name} [{target}]" for f in files if f.exists()]

    def preview(self, file: Path, params: dict[str, Any]) -> Image.Image | None:
        try:
            with _open_image_rgb_or_rgba(file) as img:
                return img.copy()
        except Exception:
            return None

    def run(self, files: list[Path], params: dict[str, Any], ctx: JobContext) -> RunResult:
        if not files:
            raise ToolError("No files selected to compress.")

        mode = params.get("mode", "Target file size (KB)")
        target_kb = int(params.get("target_kb", 300))
        target_bytes = target_kb * 1024
        fixed_quality = int(params.get("quality", 75))

        outputs: list[Path] = []
        total = len(files)

        for i, src in enumerate(files):
            ctx.check_cancelled()
            ctx.progress(i, total, f"Compressing {src.name}...")

            orig_size = src.stat().st_size
            with _open_image_rgb_or_rgba(src) as img:
                out = ctx.out_path(src, suffix="_compressed")
                fmt = img.format or "JPEG"

                if mode == "Quality reduction":
                    if fmt == "PNG":
                        p_img = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
                        p_img.save(out, format="PNG", optimize=True)
                    else:
                        save_img = _rgba_to_rgb(img) if fmt == "JPEG" else img
                        save_img.save(out, format=fmt, quality=fixed_quality, optimize=True)
                else:
                    if fmt == "PNG":
                        buf = io.BytesIO()
                        img.save(buf, format="PNG", optimize=True)
                        if buf.tell() <= target_bytes:
                            with open(out, "wb") as f_out:
                                f_out.write(buf.getvalue())
                        else:
                            buf = io.BytesIO()
                            p_img = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
                            p_img.save(buf, format="PNG", optimize=True)
                            with open(out, "wb") as f_out:
                                f_out.write(buf.getvalue())
                    else:
                        save_img = _rgba_to_rgb(img) if fmt == "JPEG" else img
                        low, high = 10, 95
                        best_data: bytes | None = None
                        best_quality = low

                        while low <= high:
                            mid = (low + high) // 2
                            buf = io.BytesIO()
                            save_img.save(buf, format=fmt, quality=mid, optimize=True)
                            size = buf.tell()
                            if size <= target_bytes:
                                best_data = buf.getvalue()
                                best_quality = mid
                                low = mid + 1
                            else:
                                high = mid - 1

                        if best_data is None:
                            curr_img = save_img
                            while curr_img.width > 200 and curr_img.height > 200:
                                curr_img = curr_img.resize(
                                    (int(curr_img.width * 0.8), int(curr_img.height * 0.8)),
                                    Image.Resampling.LANCZOS,
                                )
                                buf = io.BytesIO()
                                curr_img.save(buf, format=fmt, quality=15, optimize=True)
                                if buf.tell() <= target_bytes:
                                    best_data = buf.getvalue()
                                    break
                            if best_data is None:
                                best_data = buf.getvalue()

                        with open(out, "wb") as f_out:
                            f_out.write(best_data)

                new_size = out.stat().st_size
                outputs.append(out)
                saved_pct = max(0, int((orig_size - new_size) / orig_size * 100))
                ctx.log(f"Compressed {src.name}: {orig_size // 1024} KB -> {new_size // 1024} KB (-{saved_pct}%)")

        ctx.progress(total, total, "Finished compression.")
        return RunResult(outputs=outputs, message=f"Compressed {len(outputs)} image(s).")


# =============================================================================
# 4. Crop & Rotate
# =============================================================================

class CropRotateImageTool(Tool):
    id = "image.crop_rotate"
    name = "Crop & Rotate"
    category = Category.IMAGES
    description = "Crop margins or aspect ratios, rotate, flip, and auto-orient images."
    accepts = ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp", "*.tiff"]
    params = [
        Choice("rotation", "Rotation", ["None", "90° Clockwise", "180°", "270° Clockwise", "Auto-orient (from EXIF)"], default="None"),
        Choice("flip", "Flip", ["None", "Horizontal", "Vertical"], default="None"),
        Choice("crop_mode", "Crop mode", ["None", "Square (Center)", "Aspect 16:9", "Aspect 4:3", "Aspect 1:1", "Custom pixel margins"], default="None"),
        Int("margin_left", "Margin Left", default=0, minimum=0, maximum=10000, suffix="px"),
        Int("margin_top", "Margin Top", default=0, minimum=0, maximum=10000, suffix="px"),
        Int("margin_right", "Margin Right", default=0, minimum=0, maximum=10000, suffix="px"),
        Int("margin_bottom", "Margin Bottom", default=0, minimum=0, maximum=10000, suffix="px"),
    ]

    def plan(self, files: list[Path], params: dict[str, Any], ctx: JobContext) -> list[str]:
        rot = params.get("rotation", "None")
        crop = params.get("crop_mode", "None")
        return [f"{f.name} -> {ctx.out_path(f, suffix='_modified').name} (Rot: {rot}, Crop: {crop})" for f in files]

    def preview(self, file: Path, params: dict[str, Any]) -> Image.Image | None:
        try:
            with _open_image_rgb_or_rgba(file) as img:
                rotation = params.get("rotation", "None")
                flip = params.get("flip", "None")
                crop_mode = params.get("crop_mode", "None")
                m_left = int(params.get("margin_left", 0))
                m_top = int(params.get("margin_top", 0))
                m_right = int(params.get("margin_right", 0))
                m_bottom = int(params.get("margin_bottom", 0))

                res = img

                # 1. Orientation / Rotation
                if rotation == "Auto-orient (from EXIF)":
                    res = ImageOps.exif_transpose(res) or res
                elif rotation == "90° Clockwise":
                    res = res.rotate(270, expand=True)
                elif rotation == "180°":
                    res = res.rotate(180, expand=True)
                elif rotation == "270° Clockwise":
                    res = res.rotate(90, expand=True)

                # 2. Flip
                if flip == "Horizontal":
                    res = res.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                elif flip == "Vertical":
                    res = res.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

                # 3. Crop
                w, h = res.size
                if crop_mode in ("Square (Center)", "Aspect 1:1"):
                    side = min(w, h)
                    left = (w - side) // 2
                    top = (h - side) // 2
                    res = res.crop((left, top, left + side, top + side))

                elif crop_mode == "Aspect 16:9":
                    target_ratio = 16.0 / 9.0
                    curr_ratio = w / h
                    if curr_ratio > target_ratio:
                        new_w = int(h * target_ratio)
                        left = (w - new_w) // 2
                        res = res.crop((left, 0, left + new_w, h))
                    else:
                        new_h = int(w / target_ratio)
                        top = (h - new_h) // 2
                        res = res.crop((0, top, w, top + new_h))

                elif crop_mode == "Aspect 4:3":
                    target_ratio = 4.0 / 3.0
                    curr_ratio = w / h
                    if curr_ratio > target_ratio:
                        new_w = int(h * target_ratio)
                        left = (w - new_w) // 2
                        res = res.crop((left, 0, left + new_w, h))
                    else:
                        new_h = int(w / target_ratio)
                        top = (h - new_h) // 2
                        res = res.crop((0, top, w, top + new_h))

                elif crop_mode == "Custom pixel margins":
                    box = (m_left, m_top, max(m_left + 1, w - m_right), max(m_top + 1, h - m_bottom))
                    res = res.crop(box)

                return res.copy()
        except Exception:
            return None

    def run(self, files: list[Path], params: dict[str, Any], ctx: JobContext) -> RunResult:
        if not files:
            raise ToolError("No files selected to modify.")

        rotation = params.get("rotation", "None")
        flip = params.get("flip", "None")
        crop_mode = params.get("crop_mode", "None")
        m_left = int(params.get("margin_left", 0))
        m_top = int(params.get("margin_top", 0))
        m_right = int(params.get("margin_right", 0))
        m_bottom = int(params.get("margin_bottom", 0))

        outputs: list[Path] = []
        total = len(files)

        for i, src in enumerate(files):
            ctx.check_cancelled()
            ctx.progress(i, total, f"Processing {src.name}...")

            with _open_image_rgb_or_rgba(src) as img:
                res = img

                # 1. Orientation / Rotation
                if rotation == "Auto-orient (from EXIF)":
                    res = ImageOps.exif_transpose(res) or res
                elif rotation == "90° Clockwise":
                    res = res.rotate(270, expand=True)
                elif rotation == "180°":
                    res = res.rotate(180, expand=True)
                elif rotation == "270° Clockwise":
                    res = res.rotate(90, expand=True)

                # 2. Flip
                if flip == "Horizontal":
                    res = res.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                elif flip == "Vertical":
                    res = res.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

                # 3. Crop
                w, h = res.size
                if crop_mode in ("Square (Center)", "Aspect 1:1"):
                    side = min(w, h)
                    left = (w - side) // 2
                    top = (h - side) // 2
                    res = res.crop((left, top, left + side, top + side))

                elif crop_mode == "Aspect 16:9":
                    target_ratio = 16.0 / 9.0
                    curr_ratio = w / h
                    if curr_ratio > target_ratio:
                        new_w = int(h * target_ratio)
                        left = (w - new_w) // 2
                        res = res.crop((left, 0, left + new_w, h))
                    else:
                        new_h = int(w / target_ratio)
                        top = (h - new_h) // 2
                        res = res.crop((0, top, w, top + new_h))

                elif crop_mode == "Aspect 4:3":
                    target_ratio = 4.0 / 3.0
                    curr_ratio = w / h
                    if curr_ratio > target_ratio:
                        new_w = int(h * target_ratio)
                        left = (w - new_w) // 2
                        res = res.crop((left, 0, left + new_w, h))
                    else:
                        new_h = int(w / target_ratio)
                        top = (h - new_h) // 2
                        res = res.crop((0, top, w, top + new_h))

                elif crop_mode == "Custom pixel margins":
                    box = (m_left, m_top, max(m_left + 1, w - m_right), max(m_top + 1, h - m_bottom))
                    res = res.crop(box)

                out = ctx.out_path(src, suffix="_modified")
                res.save(out, format=img.format or "PNG")
                outputs.append(out)
                ctx.log(f"Processed: {src.name} -> {out.name} ({res.width}x{res.height})")

        ctx.progress(total, total, "Finished crop & rotate.")
        return RunResult(outputs=outputs, message=f"Processed {len(outputs)} image(s).")


# =============================================================================
# 5. EXIF Metadata (View / Strip / Remove GPS)
# =============================================================================

class ExifTool(Tool):
    id = "image.exif"
    name = "EXIF Metadata"
    category = Category.IMAGES
    description = "View image EXIF metadata, strip all metadata, or remove GPS tags."
    accepts = ["*.jpg", "*.jpeg", "*.tiff", "*.webp", "*.png"]
    params = [
        Choice("action", "Action", ["View metadata", "Strip all metadata", "Remove GPS tags only"], default="View metadata"),
    ]

    def preview(self, file: Path, params: dict[str, Any]) -> Image.Image | None:
        try:
            with _open_image_rgb_or_rgba(file) as img:
                return img.copy()
        except Exception:
            return None

    def run(self, files: list[Path], params: dict[str, Any], ctx: JobContext) -> RunResult:
        if not files:
            raise ToolError("No files selected.")

        action = params.get("action", "View metadata")
        outputs: list[Path] = []
        log_lines: list[str] = []
        total = len(files)

        for i, src in enumerate(files):
            ctx.check_cancelled()
            ctx.progress(i, total, f"Reading EXIF for {src.name}...")

            with Image.open(src) as img:
                exif = img.getexif()

                if action == "View metadata":
                    log_lines.append(f"=== {src.name} ===")
                    if not exif:
                        log_lines.append("  No EXIF metadata found.")
                    else:
                        has_tags = False
                        for tag_id, value in exif.items():
                            tag_name = TAGS.get(tag_id, str(tag_id))
                            if isinstance(value, bytes) and len(value) > 32:
                                value = f"<{len(value)} bytes binary>"
                            log_lines.append(f"  {tag_name}: {value}")
                            has_tags = True
                        if not has_tags:
                            log_lines.append("  EXIF table is empty.")
                    log_lines.append("")

                elif action == "Strip all metadata":
                    out = ctx.out_path(src, suffix="_stripped")
                    data = list(img.getdata())
                    clean_img = Image.new(img.mode, img.size)
                    clean_img.putdata(data)
                    clean_img.save(out)
                    outputs.append(out)
                    ctx.log(f"Stripped all EXIF: {src.name} -> {out.name}")

                elif action == "Remove GPS tags only":
                    out = ctx.out_path(src, suffix="_no_gps")
                    if 0x8825 in exif:
                        del exif[0x8825]
                    img.save(out, exif=exif)
                    outputs.append(out)
                    ctx.log(f"Removed GPS info: {src.name} -> {out.name}")

        ctx.progress(total, total, "EXIF operation complete.")
        msg = f"Extracted EXIF from {total} file(s)." if action == "View metadata" else f"Processed {len(outputs)} file(s)."
        return RunResult(outputs=outputs, text="\n".join(log_lines), message=msg)


# =============================================================================
# 6. Watermark Images
# =============================================================================

class WatermarkImageTool(Tool):
    id = "image.watermark"
    name = "Watermark Images"
    category = Category.IMAGES
    description = "Add customizable text watermarks to images with position and opacity control."
    accepts = ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp"]
    params = [
        Text("text", "Watermark text", default="CONFIDENTIAL", placeholder="Enter watermark text"),
        Choice("position", "Position", ["Bottom-right", "Bottom-left", "Top-right", "Top-left", "Center", "Tiled across image"], default="Bottom-right"),
        Int("font_size", "Font size", default=36, minimum=10, maximum=300, suffix="pt"),
        Int("opacity", "Opacity", default=40, minimum=5, maximum=100, suffix="%"),
        Choice("color", "Text color", ["White", "Black", "Red", "Yellow", "Custom Hex"], default="White"),
        Text("custom_hex", "Custom hex color (if Custom selected)", default="#FFFFFF", placeholder="#RRGGBB"),
        Int("margin", "Edge margin", default=24, minimum=0, maximum=500, suffix="px"),
    ]

    _COLOR_MAP = {
        "White": (255, 255, 255),
        "Black": (0, 0, 0),
        "Red": (230, 40, 40),
        "Yellow": (255, 220, 0),
    }

    def _get_font(self, size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
        font_candidates = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        for path in font_candidates:
            if Path(path).exists():
                try:
                    return ImageFont.truetype(path, size=size)
                except Exception:
                    pass
        try:
            return ImageFont.load_default(size=size)
        except Exception:
            return ImageFont.load_default()

    def preview(self, file: Path, params: dict[str, Any]) -> Image.Image | None:
        try:
            with _open_image_rgb_or_rgba(file) as img:
                watermark_text = params.get("text", "CONFIDENTIAL").strip()
                if not watermark_text:
                    return img.copy()

                pos_choice = params.get("position", "Bottom-right")
                font_size = int(params.get("font_size", 36))
                opacity_pct = int(params.get("opacity", 40))
                alpha = int(255 * (opacity_pct / 100.0))
                color_choice = params.get("color", "White")
                margin = int(params.get("margin", 24))

                if color_choice == "Custom Hex":
                    hex_str = params.get("custom_hex", "#FFFFFF").strip().lstrip("#")
                    if len(hex_str) == 6:
                        r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
                    else:
                        r, g, b = 255, 255, 255
                else:
                    r, g, b = self._COLOR_MAP.get(color_choice, (255, 255, 255))

                fill_color = (r, g, b, alpha)
                font = self._get_font(font_size)

                base = img.convert("RGBA")
                overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
                draw = ImageDraw.Draw(overlay)

                bbox = draw.textbbox((0, 0), watermark_text, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                w, h = base.size

                if pos_choice == "Tiled across image":
                    step_x = tw + margin * 3
                    step_y = th + margin * 3
                    for x in range(margin, w, max(1, step_x)):
                        for y in range(margin, h, max(1, step_y)):
                            draw.text((x, y), watermark_text, font=font, fill=fill_color)
                else:
                    if pos_choice == "Bottom-right":
                        x, y = w - tw - margin, h - th - margin
                    elif pos_choice == "Bottom-left":
                        x, y = margin, h - th - margin
                    elif pos_choice == "Top-right":
                        x, y = w - tw - margin, margin
                    elif pos_choice == "Top-left":
                        x, y = margin, margin
                    else:  # Center
                        x, y = (w - tw) // 2, (h - th) // 2

                    draw.text((x, y), watermark_text, font=font, fill=fill_color)

                return Image.alpha_composite(base, overlay)
        except Exception:
            return None

    def run(self, files: list[Path], params: dict[str, Any], ctx: JobContext) -> RunResult:
        if not files:
            raise ToolError("No files selected to watermark.")

        watermark_text = params.get("text", "CONFIDENTIAL").strip()
        if not watermark_text:
            raise ToolError("Watermark text cannot be empty.")

        pos_choice = params.get("position", "Bottom-right")
        font_size = int(params.get("font_size", 36))
        opacity_pct = int(params.get("opacity", 40))
        alpha = int(255 * (opacity_pct / 100.0))
        color_choice = params.get("color", "White")
        margin = int(params.get("margin", 24))

        if color_choice == "Custom Hex":
            hex_str = params.get("custom_hex", "#FFFFFF").strip().lstrip("#")
            if len(hex_str) == 6:
                r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
            else:
                r, g, b = 255, 255, 255
        else:
            r, g, b = self._COLOR_MAP.get(color_choice, (255, 255, 255))

        fill_color = (r, g, b, alpha)
        font = self._get_font(font_size)

        outputs: list[Path] = []
        total = len(files)

        for i, src in enumerate(files):
            ctx.check_cancelled()
            ctx.progress(i, total, f"Watermarking {src.name}...")

            with _open_image_rgb_or_rgba(src) as img:
                base = img.convert("RGBA")
                overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
                draw = ImageDraw.Draw(overlay)

                # Measure text bounding box
                bbox = draw.textbbox((0, 0), watermark_text, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]

                w, h = base.size

                if pos_choice == "Tiled across image":
                    step_x = tw + margin * 3
                    step_y = th + margin * 3
                    for x in range(margin, w, max(1, step_x)):
                        for y in range(margin, h, max(1, step_y)):
                            draw.text((x, y), watermark_text, font=font, fill=fill_color)
                else:
                    if pos_choice == "Bottom-right":
                        x, y = w - tw - margin, h - th - margin
                    elif pos_choice == "Bottom-left":
                        x, y = margin, h - th - margin
                    elif pos_choice == "Top-right":
                        x, y = w - tw - margin, margin
                    elif pos_choice == "Top-left":
                        x, y = margin, margin
                    else:  # Center
                        x, y = (w - tw) // 2, (h - th) // 2

                    draw.text((x, y), watermark_text, font=font, fill=fill_color)

                watermarked = Image.alpha_composite(base, overlay)
                out = ctx.out_path(src, suffix="_watermarked")

                if img.format == "JPEG":
                    watermarked = _rgba_to_rgb(watermarked)
                    watermarked.save(out, format="JPEG", quality=92)
                else:
                    watermarked.save(out, format=img.format or "PNG")

                outputs.append(out)
                ctx.log(f"Watermarked: {src.name} -> {out.name}")

        ctx.progress(total, total, "Finished watermarking.")
        return RunResult(outputs=outputs, message=f"Watermarked {len(outputs)} image(s).")


# =============================================================================
# 7. Favicon / ICO Generator
# =============================================================================

class FaviconIcoTool(Tool):
    id = "image.favicon"
    name = "Favicon & ICO Generator"
    category = Category.IMAGES
    description = "Generate multi-resolution .ico icon files from any image."
    accepts = ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp", "*.svg"]
    params = [
        Choice("sizes", "Icon sizes", [
            "Standard (16, 32, 48)",
            "Full (16, 32, 48, 64, 128, 256)",
            "Single 32x32",
            "Single 64x64",
            "Single 256x256",
        ], default="Standard (16, 32, 48)"),
        Choice("fit", "Fitting mode", ["Fit inside square (keep aspect)", "Stretch to square"], default="Fit inside square (keep aspect)"),
    ]

    _SIZES_MAP = {
        "Standard (16, 32, 48)": [(16, 16), (32, 32), (48, 48)],
        "Full (16, 32, 48, 64, 128, 256)": [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        "Single 32x32": [(32, 32)],
        "Single 64x64": [(64, 64)],
        "Single 256x256": [(256, 256)],
    }

    def plan(self, files: list[Path], params: dict[str, Any], ctx: JobContext) -> list[str]:
        sizes = params.get("sizes", "Standard (16, 32, 48)")
        return [f"{f.name} -> {ctx.out_path(f, ext='.ico').name} ({sizes})" for f in files]

    def preview(self, file: Path, params: dict[str, Any]) -> Image.Image | None:
        try:
            with _open_image_rgb_or_rgba(file) as img:
                img_rgba = img.convert("RGBA")
                max_dim = 128
                fit_mode = params.get("fit", "Fit inside square (keep aspect)")
                if fit_mode == "Stretch to square":
                    return img_rgba.resize((max_dim, max_dim), Image.Resampling.LANCZOS)
                else:
                    master = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
                    w, h = img_rgba.size
                    scale = min(max_dim / w, max_dim / h)
                    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
                    scaled = img_rgba.resize((nw, nh), Image.Resampling.LANCZOS)
                    master.paste(scaled, ((max_dim - nw) // 2, (max_dim - nh) // 2))
                    return master
        except Exception:
            return None

    def run(self, files: list[Path], params: dict[str, Any], ctx: JobContext) -> RunResult:
        if not files:
            raise ToolError("No files selected to generate favicon.")

        size_key = params.get("sizes", "Standard (16, 32, 48)")
        icon_sizes = self._SIZES_MAP.get(size_key, [(16, 16), (32, 32), (48, 48)])
        fit_mode = params.get("fit", "Fit inside square (keep aspect)")

        outputs: list[Path] = []
        total = len(files)

        for i, src in enumerate(files):
            ctx.check_cancelled()
            ctx.progress(i, total, f"Creating ICO for {src.name}...")

            with _open_image_rgb_or_rgba(src) as img:
                img_rgba = img.convert("RGBA")
                max_dim = max(s[0] for s in icon_sizes)

                if fit_mode == "Stretch to square":
                    master = img_rgba.resize((max_dim, max_dim), Image.Resampling.LANCZOS)
                else:
                    master = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
                    w, h = img_rgba.size
                    scale = min(max_dim / w, max_dim / h)
                    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
                    scaled = img_rgba.resize((nw, nh), Image.Resampling.LANCZOS)
                    master.paste(scaled, ((max_dim - nw) // 2, (max_dim - nh) // 2))

                out = ctx.out_path(src, ext=".ico")
                master.save(out, format="ICO", sizes=icon_sizes)
                outputs.append(out)
                ctx.log(f"Generated ICO: {src.name} -> {out.name} with sizes {icon_sizes}")

        ctx.progress(total, total, "Finished generating icons.")
        return RunResult(outputs=outputs, message=f"Generated {len(outputs)} ICO file(s).")
