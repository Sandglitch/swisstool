"""Milestone 1 Test Suite.

Tests:
1. Registry & tool auto-discovery
2. Safe naming & collision resolution
3. Settings & Preset management
4. End-to-end execution of all 7 Milestone 1 Image tools:
   - Convert
   - Resize
   - Compress
   - Crop & Rotate
   - EXIF (view, strip, remove GPS)
   - Watermark
   - Favicon / ICO generator
5. UI components smoke test (offscreen MainWindow and ToolPage)
"""
from __future__ import annotations

import os
import sys
import shutil
import tempfile
from pathlib import Path

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from swissknife.core.registry import registry
from swissknife.core.naming import make_output_path
from swissknife.core.settings import settings
from swissknife.core.tool import JobContext


def test_registry_discovery():
    print("[1/5] Testing Registry & Discovery...")
    registry.discover("swissknife.tools")
    tools = registry.all_tools()
    print(f"  Discovered {len(tools)} tools.")
    assert len(tools) >= 7, f"Expected at least 7 tools, found {len(tools)}"

    expected_ids = [
        "image.convert",
        "image.resize",
        "image.compress",
        "image.crop_rotate",
        "image.exif",
        "image.watermark",
        "image.favicon",
    ]
    for tid in expected_ids:
        t = registry.get(tid)
        assert t is not None, f"Tool {tid} not registered!"
        print(f"  Found tool: {t.name} (id: {t.id})")
    print("  Registry & Discovery: PASSED")


def test_naming_and_collision():
    print("[2/5] Testing Naming & Collision Avoidance...")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        src = tmp_dir / "photo.png"
        src.write_text("dummy")

        out1 = make_output_path(src, tmp_dir, suffix="_resized", ext=".jpg")
        assert out1.name == "photo_resized.jpg"
        out1.write_text("data")

        # Second creation should avoid collision
        out2 = make_output_path(src, tmp_dir, suffix="_resized", ext=".jpg")
        assert out2.name == "photo_resized (2).jpg"
        out2.write_text("data2")

        # Third creation
        out3 = make_output_path(src, tmp_dir, suffix="_resized", ext=".jpg")
        assert out3.name == "photo_resized (3).jpg"

        # Overwrite=True
        out_ow = make_output_path(src, tmp_dir, suffix="_resized", ext=".jpg", overwrite=True)
        assert out_ow.name == "photo_resized.jpg"

    print("  Naming & Collision: PASSED")


def test_presets():
    print("[3/5] Testing Settings & Presets...")
    tid = "image.resize"
    test_preset_name = "__test_preset_web__"
    test_params = {"mode": "Fit inside box", "width": 1920, "height": 1080}

    settings.save_preset(tid, test_preset_name, test_params)
    all_presets = settings.list_presets(tid)
    assert test_preset_name in all_presets, f"Preset {test_preset_name} not found in {all_presets}"

    loaded = settings.get_preset(tid, test_preset_name)
    assert loaded == test_params, f"Loaded preset mismatch: {loaded}"

    deleted = settings.delete_preset(tid, test_preset_name)
    assert deleted is True
    assert test_preset_name not in settings.list_presets(tid)
    print("  Settings & Presets: PASSED")


def test_image_tools_execution():
    print("[4/5] Testing Image Tools Execution...")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        # 1. Create test images
        img_rgb_path = tmp_dir / "test_rgb.png"
        img_rgba_path = tmp_dir / "test_rgba.png"

        img_rgb = Image.new("RGB", (400, 300), color=(100, 150, 200))
        img_rgb.save(img_rgb_path)

        img_rgba = Image.new("RGBA", (200, 200), color=(255, 0, 0, 128))
        img_rgba.save(img_rgba_path)

        ctx = JobContext(out_dir=tmp_dir / "out")

        # --- Test 1: Convert ---
        convert_tool = registry.get("image.convert")
        res = convert_tool.run([img_rgb_path, img_rgba_path], {"target_format": "JPEG", "quality": 85, "optimize": True}, ctx)
        assert len(res.outputs) == 2
        for p in res.outputs:
            assert p.exists() and p.suffix.lower() == ".jpg"
        print("    image.convert: OK")

        # --- Test 2: Resize ---
        resize_tool = registry.get("image.resize")
        res = resize_tool.run([img_rgb_path], {"mode": "Fit inside box", "width": 100, "height": 100, "keep_aspect": True}, ctx)
        assert len(res.outputs) == 1
        with Image.open(res.outputs[0]) as im:
            assert im.width <= 100 and im.height <= 100
        print("    image.resize: OK")

        # --- Test 3: Compress ---
        compress_tool = registry.get("image.compress")
        res = compress_tool.run([img_rgb_path], {"mode": "Quality reduction", "quality": 50, "strip_metadata": True}, ctx)
        assert len(res.outputs) == 1
        assert res.outputs[0].exists()
        print("    image.compress: OK")

        # --- Test 4: Crop & Rotate ---
        crop_tool = registry.get("image.crop_rotate")
        res = crop_tool.run(
            [img_rgb_path],
            {"rotation": "90° Clockwise", "flip": "Horizontal", "crop_mode": "Square (Center)"},
            ctx
        )
        assert len(res.outputs) == 1
        with Image.open(res.outputs[0]) as im:
            assert im.width == im.height
        print("    image.crop_rotate: OK")

        # --- Test 5: EXIF ---
        exif_tool = registry.get("image.exif")
        res = exif_tool.run([img_rgb_path], {"action": "View metadata"}, ctx)
        assert "=== test_rgb.png ===" in res.text
        res_strip = exif_tool.run([img_rgb_path], {"action": "Strip all metadata"}, ctx)
        assert len(res_strip.outputs) == 1
        print("    image.exif: OK")

        # --- Test 6: Watermark ---
        wm_tool = registry.get("image.watermark")
        res = wm_tool.run(
            [img_rgb_path],
            {"text": "PREVIEW", "position": "Center", "font_size": 24, "opacity": 50, "color": "White"},
            ctx
        )
        assert len(res.outputs) == 1
        assert res.outputs[0].exists()
        print("    image.watermark: OK")

        # --- Test 7: Favicon / ICO ---
        fav_tool = registry.get("image.favicon")
        res = fav_tool.run([img_rgba_path], {"sizes": "Standard (16, 32, 48)", "fit": "Fit inside square (keep aspect)"}, ctx)
        assert len(res.outputs) == 1
        assert res.outputs[0].suffix.lower() == ".ico"
        assert res.outputs[0].stat().st_size > 0
        print("    image.favicon: OK")

    print("  All 7 Image Tools: PASSED")


def test_image_previews():
    print("[5/6] Testing Image Live Previews...")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        test_img_path = tmp_dir / "preview_sample.png"
        sample = Image.new("RGB", (400, 300), color=(50, 100, 150))
        sample.save(test_img_path)

        # 1. Resize Preview
        resize_tool = registry.get("image.resize")
        prev_res = resize_tool.preview(test_img_path, {"mode": "Fit inside box", "width": 200, "height": 200, "keep_aspect": True})
        assert prev_res is not None
        assert prev_res.width == 200 and prev_res.height == 150
        print("    Resize preview: OK (400x300 -> 200x150)")

        # 2. Crop & Rotate Preview
        crop_tool = registry.get("image.crop_rotate")
        prev_rot = crop_tool.preview(test_img_path, {"rotation": "90° Clockwise", "flip": "None", "crop_mode": "None"})
        assert prev_rot is not None
        assert prev_rot.width == 300 and prev_rot.height == 400
        print("    Rotate 90° CW preview: OK (400x300 -> 300x400)")

        prev_sq = crop_tool.preview(test_img_path, {"rotation": "None", "flip": "None", "crop_mode": "Square (Center)"})
        assert prev_sq is not None
        assert prev_sq.width == 300 and prev_sq.height == 300
        print("    Square crop preview: OK (400x300 -> 300x300)")

        # 3. Watermark Preview
        wm_tool = registry.get("image.watermark")
        prev_wm = wm_tool.preview(test_img_path, {"text": "WATERMARK", "position": "Center", "font_size": 20, "opacity": 50, "color": "White"})
        assert prev_wm is not None
        assert prev_wm.size == (400, 300)
        print("    Watermark preview: OK")

    print("  Live Previews: PASSED")


def test_ui_smoke():
    print("[6/6] Testing UI Components & Preview Widget (Offscreen)...")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from PySide6.QtWidgets import QApplication
    from swissknife.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])
    win = MainWindow()
    win.show()

    assert win.tree.topLevelItemCount() == 1, f"Expected 1 active category in sidebar, got {win.tree.topLevelItemCount()}"
    top_item = win.tree.topLevelItem(0)
    assert "Images" in top_item.text(0)
    assert top_item.childCount() == 7
    print(f"  MainWindow instantiated successfully with active category '{top_item.text(0)}' and {top_item.childCount()} tools.")

    # Test that tool page contains the image preview widget
    resize_item = top_item.child(1)  # Resize Images
    win.tree.setCurrentItem(resize_item)
    active_page = win.stack.currentWidget()
    assert hasattr(active_page, "preview_widget"), "ToolPage missing preview_widget"
    assert active_page.preview_widget.orig_display is not None
    assert active_page.preview_widget.prev_display is not None
    print("  ToolPage ImagePreviewWidget verified successfully.")

    win.close()
    print("  UI Smoke Test: PASSED")


if __name__ == "__main__":
    test_registry_discovery()
    test_naming_and_collision()
    test_presets()
    test_image_tools_execution()
    test_image_previews()
    test_ui_smoke()
    print("\n=========================================")
    print(" ALL MILESTONE 1 TESTS PASSED SUCCESSFULLY! ")
    print("=========================================")
