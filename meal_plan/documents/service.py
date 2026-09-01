from __future__ import annotations

from pathlib import Path
from typing import Any

from .docx_renderer import render_docx
from .helpers import artifact_basename, build_manifest, sha256_file, write_json
from .models import DocumentContext, RenderedArtifact, RenderedArtifactSet
from .pdf_renderer import render_pdf
from .storage import version_output_dir


def _artifact(kind: str, path: Path) -> RenderedArtifact:
    return RenderedArtifact(
        artifact_type=kind,
        path=path,
        filename=path.name,
        sha256=sha256_file(path),
        byte_size=path.stat().st_size,
    )


def render_plan_artifacts(
    plan: dict[str, Any],
    context: DocumentContext,
    *,
    output_root: str | Path | None = None,
) -> RenderedArtifactSet:
    """Render an editable DOCX + client-facing PDF from one immutable plan snapshot.

    Phase 7 is intentionally file-generation only. It does not approve, deliver or
    send artifacts to Telegram. Phase 8 owns review handoff and publication.
    """
    out_dir = version_output_dir(context.plan_public_id, context.version_number, output_root)
    basename = artifact_basename(context.plan_public_id, context.client_name, context.version_number)
    docx_path = render_docx(plan, context, out_dir / f"{basename}.docx")
    pdf_path = render_pdf(plan, context, out_dir / f"{basename}.pdf")

    docx_artifact = _artifact("DOCX", docx_path)
    pdf_artifact = _artifact("PDF", pdf_path)
    manifest_path = out_dir / f"{basename}.manifest.json"
    manifest = build_manifest(plan, context, {
        "DOCX": {
            "filename": docx_artifact.filename,
            "sha256": docx_artifact.sha256,
            "byte_size": docx_artifact.byte_size,
        },
        "PDF": {
            "filename": pdf_artifact.filename,
            "sha256": pdf_artifact.sha256,
            "byte_size": pdf_artifact.byte_size,
        },
    })
    write_json(manifest_path, manifest)
    return RenderedArtifactSet(docx=docx_artifact, pdf=pdf_artifact, manifest_path=manifest_path)


def render_client_pdf(
    plan: dict[str, Any],
    context: DocumentContext,
    output_path: str | Path,
) -> Path:
    """Render an approved, clean client-facing PDF artifact."""
    return render_pdf(plan, context, output_path, is_client_delivery=True)
