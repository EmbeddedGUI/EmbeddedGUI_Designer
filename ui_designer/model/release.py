"""Release configuration and result models for UI Designer."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from .workspace import normalize_path


RELEASE_CONFIG_FILENAME = "release.json"
RELEASE_SCHEMA_VERSION = 1
DEFAULT_RELEASE_PROFILE_ID = "windows-pc"
DEFAULT_RELEASE_PACKAGE_FORMAT = "dir+zip"


def default_release_profile() -> "ReleaseProfile":
    return ReleaseProfile(
        id=DEFAULT_RELEASE_PROFILE_ID,
        name="Windows PC",
        port="pc",
        make_target="all",
        package_format=DEFAULT_RELEASE_PACKAGE_FORMAT,
        extra_make_args=[],
        copy_resource_dir=True,
    )


def _coerce_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if value is None:
        return default
    return bool(value)


def _normalize_extra_make_args(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        value = [value]

    result = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def _release_config_dir(project_or_config_dir: str) -> str:
    resolved = normalize_path(project_or_config_dir)
    if not resolved:
        return ""
    if os.path.basename(resolved) == ".eguiproject":
        return resolved
    return os.path.join(resolved, ".eguiproject")


def release_config_path(project_or_config_dir: str) -> str:
    config_dir = _release_config_dir(project_or_config_dir)
    if not config_dir:
        return ""
    return os.path.join(config_dir, RELEASE_CONFIG_FILENAME)


@dataclass
class ReleaseProfile:
    id: str
    name: str
    port: str = "pc"
    make_target: str = "all"
    package_format: str = DEFAULT_RELEASE_PACKAGE_FORMAT
    extra_make_args: list[str] = field(default_factory=list)
    copy_resource_dir: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, object] | None):
        data = data or {}
        profile_id = str(data.get("id") or "").strip()
        name = str(data.get("name") or "").strip()
        if not profile_id:
            profile_id = DEFAULT_RELEASE_PROFILE_ID
        if not name:
            name = profile_id
        package_format = str(data.get("package_format") or DEFAULT_RELEASE_PACKAGE_FORMAT).strip() or DEFAULT_RELEASE_PACKAGE_FORMAT
        if package_format not in {"dir", "dir+zip"}:
            package_format = DEFAULT_RELEASE_PACKAGE_FORMAT
        return cls(
            id=profile_id,
            name=name,
            port=str(data.get("port") or "pc").strip() or "pc",
            make_target=str(data.get("make_target") or "all").strip() or "all",
            package_format=package_format,
            extra_make_args=_normalize_extra_make_args(data.get("extra_make_args")),
            copy_resource_dir=_coerce_bool(data.get("copy_resource_dir"), default=True),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "port": self.port,
            "make_target": self.make_target,
            "package_format": self.package_format,
            "extra_make_args": list(self.extra_make_args),
            "copy_resource_dir": bool(self.copy_resource_dir),
        }


@dataclass
class ReleaseConfig:
    schema_version: int = RELEASE_SCHEMA_VERSION
    default_profile: str = DEFAULT_RELEASE_PROFILE_ID
    profiles: list[ReleaseProfile] = field(default_factory=lambda: [default_release_profile()])

    @classmethod
    def default(cls) -> "ReleaseConfig":
        return cls()

    @classmethod
    def from_dict(cls, data: dict[str, object] | None):
        data = data or {}
        schema_version = int(data.get("schema_version", RELEASE_SCHEMA_VERSION) or RELEASE_SCHEMA_VERSION)
        profiles_data = data.get("profiles") or []
        profiles = []
        seen = set()
        for raw_profile in profiles_data:
            if not isinstance(raw_profile, dict):
                continue
            profile = ReleaseProfile.from_dict(raw_profile)
            if profile.id in seen:
                continue
            seen.add(profile.id)
            profiles.append(profile)
        if not profiles:
            profiles = [default_release_profile()]

        default_profile = str(data.get("default_profile") or "").strip()
        if not default_profile or default_profile not in {profile.id for profile in profiles}:
            default_profile = profiles[0].id

        return cls(
            schema_version=schema_version,
            default_profile=default_profile,
            profiles=profiles,
        )

    @classmethod
    def load(cls, project_or_config_dir: str) -> "ReleaseConfig":
        path = release_config_path(project_or_config_dir)
        if not path or not os.path.isfile(path):
            return cls.default()

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError, TypeError):
            return cls.default()

        if not isinstance(data, dict):
            return cls.default()
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": int(self.schema_version or RELEASE_SCHEMA_VERSION),
            "default_profile": self.default_profile,
            "profiles": [profile.to_dict() for profile in self.profiles],
        }

    def save(self, project_or_config_dir: str) -> str:
        config_dir = _release_config_dir(project_or_config_dir)
        if not config_dir:
            raise ValueError("project_or_config_dir is required")
        os.makedirs(config_dir, exist_ok=True)
        path = os.path.join(config_dir, RELEASE_CONFIG_FILENAME)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            f.write("\n")
        return path

    def get_profile(self, profile_id: str | None = None) -> ReleaseProfile:
        wanted = (profile_id or self.default_profile or "").strip()
        for profile in self.profiles:
            if profile.id == wanted:
                return profile
        return self.profiles[0]

    def replace_profiles(self, profiles: list[ReleaseProfile], default_profile: str | None = None) -> None:
        unique_profiles = []
        seen = set()
        for profile in profiles:
            if not profile.id or profile.id in seen:
                continue
            seen.add(profile.id)
            unique_profiles.append(profile)
        if not unique_profiles:
            unique_profiles = [default_release_profile()]

        self.profiles = unique_profiles
        selected_default = (default_profile or self.default_profile or "").strip()
        if selected_default not in {profile.id for profile in self.profiles}:
            selected_default = self.profiles[0].id
        self.default_profile = selected_default
        self.schema_version = RELEASE_SCHEMA_VERSION


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


@dataclass
class ReleaseArtifact:
    path: str
    sha256: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "sha256": self.sha256,
        }


@dataclass
class ReleaseRequest:
    project: object
    project_dir: str
    sdk_root: str
    profile: ReleaseProfile
    designer_root: str = ""
    output_dir: str = ""
    warnings_as_errors: bool = False
    package_release: bool = True


@dataclass
class ReleaseResult:
    success: bool
    message: str
    build_id: str
    profile_id: str
    release_root: str
    dist_dir: str
    manifest_path: str
    log_path: str
    history_path: str
    zip_path: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    artifacts: list[ReleaseArtifact] = field(default_factory=list)
