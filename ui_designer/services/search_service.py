"""Search service for component catalog."""

from __future__ import annotations

from dataclasses import dataclass

from .component_catalog import ComponentMeta


@dataclass(frozen=True)
class SearchQuery:
    text: str = ""
    category: str = "all"
    scenario: str = "all"
    complexity: str = "all"
    tags: tuple[str, ...] = ()
    sort_mode: str = "relevance"


class SearchService:
    """Filter and rank components with stable ordering."""

    def filter_and_sort(
        self,
        items: list[ComponentMeta],
        query: SearchQuery,
        *,
        favorite_types: set[str] | None = None,
        recent_types: list[str] | None = None,
    ) -> list[ComponentMeta]:
        favorite_types = favorite_types or set()
        recent_types = recent_types or []
        filtered = self._filter(items, query)
        return self._sort(filtered, query, favorite_types=favorite_types, recent_types=recent_types)

    def rank(
        self,
        item: ComponentMeta,
        query: SearchQuery,
        *,
        favorite_types: set[str] | None = None,
        recent_types: list[str] | None = None,
    ) -> tuple:
        """Return the same tuple used for relevance ordering (for diagnostics/tests)."""
        favorite_types = favorite_types or set()
        recent_types = recent_types or []
        mode = str(query.sort_mode or "relevance").strip().lower()
        if mode == "name":
            return (item.display_name.lower(), item.browse_priority, item.type_name.lower())
        if mode == "complexity":
            rank = {"basic": 0, "intermediate": 1, "advanced": 2}
            return (
                rank.get(item.complexity.lower(), 9),
                item.display_name.lower(),
                item.browse_priority,
                item.type_name.lower(),
            )

        search = str(query.text or "").strip().lower()
        terms = self._tokenize(search)
        recent_order = {name: idx for idx, name in enumerate(recent_types)}
        weighted_rank = -self._text_score(item, terms)
        favorite_rank = 0 if item.type_name in favorite_types else 1
        recent_rank = recent_order.get(item.type_name, 999)
        return (weighted_rank, favorite_rank, recent_rank, item.browse_priority, item.display_name.lower(), item.type_name.lower())

    def _filter(self, items: list[ComponentMeta], query: SearchQuery) -> list[ComponentMeta]:
        search = str(query.text or "").strip().lower()
        category = str(query.category or "all").strip().lower()
        scenario = str(query.scenario or "all").strip().lower()
        complexity = str(query.complexity or "all").strip().lower()
        required_tags = {str(tag or "").strip().lower() for tag in (query.tags or ()) if str(tag or "").strip()}

        result = items
        if category not in {"", "all"}:
            if category == "containers":
                result = [item for item in result if item.is_container]
            else:
                result = [item for item in result if item.category.lower() == category]
        if scenario not in {"", "all"}:
            if scenario.startswith("scenario:"):
                scenario = scenario.split(":", 1)[1].strip()
            result = [item for item in result if item.scenario.lower() == scenario]
        if complexity not in {"", "all"}:
            result = [item for item in result if item.complexity.lower() == complexity]

        if required_tags:
            result = [
                item
                for item in result
                if required_tags.issubset({tag.strip().lower() for tag in item.tags if tag.strip()})
            ]

        if search:
            terms = self._tokenize(search)
            result = [item for item in result if self._matches(item, terms)]

        return result

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [part for part in (text or "").lower().split() if part]

    @staticmethod
    def _matches(item: ComponentMeta, terms: list[str]) -> bool:
        if not terms:
            return True
        haystack = " ".join(
            [item.display_name, item.type_name, item.category, item.scenario, item.complexity]
            + list(item.tags)
            + list(item.keywords)
        ).lower()
        return all(term in haystack for term in terms)

    def _sort(
        self,
        items: list[ComponentMeta],
        query: SearchQuery,
        *,
        favorite_types: set[str],
        recent_types: list[str],
    ) -> list[ComponentMeta]:
        return sorted(
            items,
            key=lambda item: self.rank(
                item,
                query,
                favorite_types=favorite_types,
                recent_types=recent_types,
            ),
        )

    def _text_score(self, item: ComponentMeta, terms: list[str]) -> int:
        if not terms:
            return 0
        display = item.display_name.lower()
        type_name = item.type_name.lower()
        category = item.category.lower()
        scenario = item.scenario.lower()
        complexity = item.complexity.lower()
        tags = [tag.lower() for tag in item.tags]
        keywords = [keyword.lower() for keyword in item.keywords]
        score_value = 0
        for term in terms:
            if term == display or term == type_name:
                score_value += 300
            elif display.startswith(term) or type_name.startswith(term):
                score_value += 180
            elif term in display or term in type_name:
                score_value += 120
            elif any(term == tag for tag in tags):
                score_value += 90
            elif any(term in tag for tag in tags):
                score_value += 70
            elif any(term == keyword for keyword in keywords):
                score_value += 80
            elif any(term in keyword for keyword in keywords):
                score_value += 60
            elif term == category or term == scenario or term == complexity:
                score_value += 50
            elif term in category or term in scenario or term in complexity:
                score_value += 30
        return score_value
