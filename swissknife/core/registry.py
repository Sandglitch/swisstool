"""Registry for registering and auto-discovering SwissKnife tools."""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Type

from .tool import Tool, Category, CATEGORY_META


class Registry:
    """Central registry of all available SwissKnife tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._by_category: dict[str, list[Tool]] = {cat: [] for cat, _ in CATEGORY_META}

    def register(self, tool_or_cls: Tool | Type[Tool]) -> None:
        """Register a tool instance or Tool class."""
        if inspect.isclass(tool_or_cls):
            if not issubclass(tool_or_cls, Tool) or tool_or_cls is Tool:
                return
            tool = tool_or_cls()
        else:
            tool = tool_or_cls

        if not tool.id:
            raise ValueError(f"Tool {tool} has no 'id' defined.")

        self._tools[tool.id] = tool
        cat = tool.category
        if cat not in self._by_category:
            self._by_category[cat] = []
        if tool not in self._by_category[cat]:
            self._by_category[cat].append(tool)

    def get(self, tool_id: str) -> Tool | None:
        return self._tools.get(tool_id)

    def all_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get_by_category(self, category: str) -> list[Tool]:
        return list(self._by_category.get(category, []))

    def categories(self) -> list[tuple[str, str]]:
        return CATEGORY_META

    def discover(self, package_name: str = "swissknife.tools") -> None:
        """Automatically import and register all tools under package_name."""
        try:
            pkg = importlib.import_module(package_name)
        except ImportError:
            return

        if not hasattr(pkg, "__path__"):
            return

        for _, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
            full_name = f"{package_name}.{modname}"
            try:
                mod = importlib.import_module(full_name)
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (
                        inspect.isclass(attr)
                        and issubclass(attr, Tool)
                        and attr is not Tool
                        and getattr(attr, "id", None)
                    ):
                        self.register(attr)
            except Exception as e:
                print(f"[Warning] Failed to import tool module {full_name}: {e}")


registry = Registry()

