"""Component catalog service for widget browsing."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

from ..model.widget_registry import WidgetRegistry


@dataclass(frozen=True)
class ComponentMeta:
    type_name: str
    display_name: str
    category: str
    scenario: str
    tags: tuple[str, ...] = field(default_factory=tuple)
    keywords: tuple[str, ...] = field(default_factory=tuple)
    complexity: str = "basic"
    icon_key: str = ""
    preview_kind: str = "widget"
    browse_priority: int = 999
    is_container: bool = False


class ComponentCatalog:
    """Provides normalized component metadata for browser/search."""

    def __init__(self, registry: WidgetRegistry | None = None):
        self._registry = registry or WidgetRegistry.instance()

    def list_components(self, *, addable_only: bool = True) -> list[ComponentMeta]:
        items = self._registry.browser_items(addable_only=addable_only)
        return [self._to_meta(item) for item in items]

    def browser_categories(self) -> list[str]:
        return self._registry.browser_categories()

    def browser_scenarios(self) -> list[str]:
        return self._registry.browser_scenarios()

    def by_type(self, type_name: str, *, addable_only: bool = True) -> ComponentMeta | None:
        type_name = str(type_name or "").strip()
        if not type_name:
            return None
        item = self._registry.browser_item(type_name)
        if not item:
            return None
        if addable_only and not bool(item.get("addable", True)):
            return None
        return self._to_meta(item)

    def filter_components(self, *, addable_only: bool = True, scenarios: Iterable[str] | None = None) -> list[ComponentMeta]:
        items = self.list_components(addable_only=addable_only)
        if scenarios:
            normalized = {str(s or "").strip().lower() for s in scenarios if str(s or "").strip()}
            if normalized:
                items = [item for item in items if item.scenario.lower() in normalized]
        return items

    def lane_counts(
        self,
        *,
        addable_only: bool = True,
        favorite_types: set[str] | None = None,
        recent_types: list[str] | None = None,
    ) -> dict[str, int]:
        """Return counts for special lanes and scenario lanes."""
        items = self.list_components(addable_only=addable_only)
        favorites = set(favorite_types or set())
        recents = set(recent_types or [])
        counts: dict[str, int] = {
            "all": len(items),
            "favorites": 0,
            "recent": 0,
            "containers": 0,
        }
        for item in items:
            if item.type_name in favorites:
                counts["favorites"] += 1
            if item.type_name in recents:
                counts["recent"] += 1
            if item.is_container:
                counts["containers"] += 1
            scenario = str(item.scenario or "").strip()
            if scenario:
                key = f"scenario:{scenario}".lower()
                counts[key] = counts.get(key, 0) + 1
        return counts

    def top_tags(self, *, addable_only: bool = True, limit: int = 18) -> list[str]:
        """Return most frequent tags across the catalog."""
        counter: Counter[str] = Counter()
        for item in self.list_components(addable_only=addable_only):
            for tag in item.tags:
                text = str(tag or "").strip()
                if text:
                    counter[text] += 1
        ranked = sorted(counter.items(), key=lambda entry: (-entry[1], entry[0].lower()))
        max_items = max(int(limit or 0), 0)
        if max_items == 0:
            return []
        return [text for text, _count in ranked[:max_items]]

    @staticmethod
    def group_by_scenario(items: list[ComponentMeta | dict]) -> list[tuple[str, list[ComponentMeta | dict]]]:
        grouped: dict[str, tuple[str, list[ComponentMeta | dict]]] = {}
        order: list[str] = []
        for item in items:
            if isinstance(item, dict):
                scenario_value = item.get("scenario", "")
            else:
                scenario_value = item.scenario
            scenario = str(scenario_value or "").strip() or "Other"
            key = scenario.lower()
            if key not in grouped:
                grouped[key] = (scenario, [])
                order.append(key)
            grouped[key][1].append(item)
        return [grouped[key] for key in order]

    @staticmethod
    def _to_meta(item: dict) -> ComponentMeta:
        return ComponentMeta(
            type_name=str(item.get("type_name", "")),
            display_name=str(item.get("display_name", "")),
            category=str(item.get("category", "")),
            scenario=str(item.get("scenario", "")),
            tags=tuple(item.get("tags", []) or []),
            keywords=tuple(item.get("keywords", []) or []),
            complexity=str(item.get("complexity", "basic")),
            icon_key=str(item.get("icon_key", "")),
            preview_kind=str(item.get("preview_kind", "widget")),
            browse_priority=int(item.get("browse_priority", 999) or 999),
            is_container=bool(item.get("is_container")),
        )
