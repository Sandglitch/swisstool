"""Application settings and saved parameter presets."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from platformdirs import user_config_dir
    CONFIG_DIR = Path(user_config_dir("swissknife", ensure_exists=True))
except Exception:
    CONFIG_DIR = Path.home() / ".swissknife"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

SETTINGS_FILE = CONFIG_DIR / "settings.json"
PRESETS_DIR = CONFIG_DIR / "presets"
PRESETS_DIR.mkdir(parents=True, exist_ok=True)


class Settings:
    """Manages persistent app settings and tool presets."""

    def __init__(self):
        self._data: dict[str, Any] = {
            "default_output_dir": "",
            "overwrite": False,
            "max_workers": 4,
        }
        self.load()

    def load(self) -> None:
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    self._data.update(json.load(f))
            except Exception:
                pass

    def save(self) -> None:
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    # -- Presets management ----------------------------------------------------

    def _preset_file(self, tool_id: str) -> Path:
        safe_id = tool_id.replace(".", "_")
        return PRESETS_DIR / f"{safe_id}.json"

    def _load_tool_presets(self, tool_id: str) -> dict[str, dict[str, Any]]:
        path = self._preset_file(tool_id)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_tool_presets(self, tool_id: str, presets: dict[str, dict[str, Any]]) -> None:
        path = self._preset_file(tool_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(presets, f, indent=2)
        except Exception:
            pass

    def list_presets(self, tool_id: str) -> list[str]:
        presets = self._load_tool_presets(tool_id)
        return sorted(presets.keys())

    def get_preset(self, tool_id: str, name: str) -> dict[str, Any] | None:
        presets = self._load_tool_presets(tool_id)
        return presets.get(name)

    def save_preset(self, tool_id: str, name: str, params: dict[str, Any]) -> None:
        presets = self._load_tool_presets(tool_id)
        presets[name] = params
        self._save_tool_presets(tool_id, presets)

    def delete_preset(self, tool_id: str, name: str) -> bool:
        presets = self._load_tool_presets(tool_id)
        if name in presets:
            del presets[name]
            self._save_tool_presets(tool_id, presets)
            return True
        return False


settings = Settings()

