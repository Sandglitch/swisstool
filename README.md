# SwissKnife

A local desktop toolbox for everyday file chores with a clean, barebones PySide6 UI and a modular, declarative architecture.

## Implemented Features

- **Architecture**:
  - Declarative parameter schema (`Tool`, `Param`, `Choice`, `Int`, `Float`, `Bool`, `Text`, `Multiline`, `Color`).
  - Auto-discovery tool registry (`swissknife.core.registry`).
  - Collision-safe output path generator (`swissknife.core.naming`), preventing accidental overwrites by default.
  - Background worker thread with cancellation, real-time progress reporting, and logging (`swissknife.core.runner`).
  - App settings & saveable presets management (`swissknife.core.settings`).
  - Native Qt UI (`PySide6`) with category & tool sidebar, drag-and-drop file list table, dynamic parameter form generation, progress bar, log console, preset manager, and a live image preview panel with Before & After side-by-side comparison.

- **Image Tools**:
  1. **Convert Format (`image.convert`)**: PNG, JPEG, WebP, BMP, TIFF, GIF, ICO with quality and optimization control, transparency and mode handling.
  2. **Resize Images (`image.resize`)**: Fit inside bounding box, exact dimensions, or percentage scaling with high-quality resampling filters (Lanczos, Bicubic, Bilinear, Nearest).
  3. **Compress Images (`image.compress`)**: Target maximum file size (KB) or direct quality reduction with smart optimization.
  4. **Crop & Rotate (`image.crop_rotate`)**: 90° CW, 180°, 270° CW, EXIF auto-orientation, horizontal/vertical flipping, square center crop, 16:9 / 4:3 / 1:1 aspect ratios, or custom margins.
  5. **EXIF Metadata (`image.exif`)**: Inspect EXIF tags, strip all metadata, or selectively remove GPS coordinates.
  6. **Watermark Images (`image.watermark`)**: Add text watermarks with position (corners, center, or tiled across image), custom font size, opacity, and color.
  7. **Favicon & ICO Generator (`image.favicon`)**: Generate multi-resolution Windows `.ico` files (standard 16/32/48 or full 16 to 256) with aspect-preserving centering or square stretch.

## Quick Start

### Windows

Double click or run from terminal:
```bat
run.bat
```

Or manually:
```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

### Run Tests

```bat
.venv\Scripts\python tests/test_milestone1.py
```
