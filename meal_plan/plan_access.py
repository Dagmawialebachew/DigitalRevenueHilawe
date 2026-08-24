from __future__ import annotations

from pathlib import Path
from typing import Any

from meal_plan.documents.storage import artifact_root
from meal_plan.runtime import coach_username


def safe_local_pdf_path(storage_key: str) -> Path | None:
    try:
        root = artifact_root().resolve()
        candidate = Path(storage_key).expanduser().resolve()
        candidate.relative_to(root)
    except (ValueError, OSError):
        return None
    return candidate if candidate.is_file() and candidate.suffix.lower() == ".pdf" else None


def plan_payload(plan_row) -> dict[str, Any] | None:
    if not plan_row:
        return None
    pdf_path = safe_local_pdf_path(str(plan_row.get("pdf_storage_key") or "")) if plan_row.get("pdf_storage_key") else None
    return {
        "version_number": plan_row["version_number"],
        "status": plan_row["status"],
        "detail_source": plan_row.get("detail_source"),
        "approved_at": plan_row.get("approved_at").isoformat() if plan_row.get("approved_at") else None,
        "delivered_at": plan_row.get("delivered_at").isoformat() if plan_row.get("delivered_at") else None,
        "pdf_available": bool(pdf_path or plan_row.get("pdf_telegram_file_id")),
        "docx_available": bool(plan_row.get("docx_artifact_id")),
        "coach_username": coach_username() if plan_row.get("status") in {"APPROVED", "DELIVERED"} else "",
    }
