"""Preview engine preference helpers with safe fallback semantics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PreviewSettings:
    """Encapsulate preview engine preference resolution."""

    preferred_engine: str = "v1"

    @staticmethod
    def normalize(engine: str | None, *, default: str = "v1") -> str:
        value = str(engine or "").strip().lower()
        return value if value else default

    @classmethod
    def from_config(cls, engine: str | None) -> "PreviewSettings":
        return cls(preferred_engine=cls.normalize(engine))

    def resolve_initial_engine(self, *, env_v2_enabled: bool) -> str:
        # Environment flag can force-enable v2 in gray rollout.
        if env_v2_enabled:
            return "v2"
        return self.normalize(self.preferred_engine)
