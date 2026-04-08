"""SDK fingerprint metadata shared by project and packaging flows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SdkFingerprint:
    source_kind: str = ""
    source_root: str = ""
    remote: str = ""
    commit: str = ""
    commit_short: str = ""
    revision: str = ""
    dirty: bool = False
    metadata_path: str = ""

    def to_dict(self) -> dict[str, object]:
        payload = {
            "source_kind": self.source_kind,
            "source_root": self.source_root,
            "remote": self.remote,
            "commit": self.commit,
            "commit_short": self.commit_short,
            "revision": self.revision,
            "dirty": bool(self.dirty),
        }
        if self.metadata_path:
            payload["metadata_path"] = self.metadata_path
        return payload
