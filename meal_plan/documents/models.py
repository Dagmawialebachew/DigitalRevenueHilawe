from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DocumentContext:
    client_name: str
    plan_public_id: str
    version_number: int = 1
    language: str = "AM"
    status: str = "DRAFT_FOR_REVIEW"
    client_profile: dict[str, Any] = field(default_factory=dict)
    coach_name: str = "Coach Hilawe Semma"
    coach_username: str = "@CoachHilaweBot"
    hydration_target_l: float | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    coach_image_path: str | None = None

    @property
    def normalized_language(self) -> str:
        return "AM" if str(self.language).upper() == "AM" else "EN"


@dataclass(frozen=True)
class RenderedArtifact:
    artifact_type: str
    path: Path
    filename: str
    sha256: str
    byte_size: int


@dataclass(frozen=True)
class RenderedArtifactSet:
    docx: RenderedArtifact
    pdf: RenderedArtifact
    manifest_path: Path
