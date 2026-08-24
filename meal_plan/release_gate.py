"""Final release-candidate gates for the Coach Hilawe Meal Plan system.

The checks in this module are intentionally read-only. They never print secret
values, write to PostgreSQL, contact Telegram, or deploy anything.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlparse

from meal_plan.generation.dataset import load_dataset
from meal_plan.runtime import (
    auto_approve_payments,
    demo_bot_id,
    demo_mode,
    frontend_origin,
    frontend_url,
    frontend_url_is_valid,
    generation_worker_enabled,
    guarded_local_dev_mode,
    lifecycle_worker_enabled,
    loopback_frontend_url_is_valid,
    review_group_id,
    reviewer_ids,
)
from scripts.meal_plan_readiness import collect_checks

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DATASET_VERSION = "HILAWE_MEAL_OS_V1.3_2026-08-17"
EXPECTED_ENGINE_MIGRATIONS = {"0001", "0002", "0003"}


@dataclass(frozen=True)
class ReleaseFinding:
    code: str
    status: str
    message: str


@dataclass(frozen=True)
class ReleaseReport:
    mode: str
    full_demo: bool
    ready: bool
    blockers: int
    warnings: int
    findings: tuple[ReleaseFinding, ...]

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "full_demo": self.full_demo,
            "ready": self.ready,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "findings": [asdict(item) for item in self.findings],
        }


def _present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _status(condition: bool, *, block: bool = True) -> str:
    if condition:
        return "PASS"
    return "BLOCK" if block else "WARN"


def _frontend_host_is_public_https() -> bool:
    candidate = frontend_url()
    if not frontend_url_is_valid(candidate):
        return False
    host = (urlparse(candidate).hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1", "example.invalid"} or host.endswith(".invalid"):
        return False

    # Preserve the existing optional FRONTEND_ORIGIN contract, but never let a
    # configured HTTP/loopback CORS origin pass a hosted/public frontend gate.
    origin = frontend_origin()
    if origin:
        if not frontend_url_is_valid(origin):
            return False
        origin_host = (urlparse(origin).hostname or "").lower()
        if origin_host in {"localhost", "127.0.0.1", "::1", "example.invalid"} or origin_host.endswith(".invalid"):
            return False
    return True


def _local_dev_frontend_is_valid() -> bool:
    return (
        loopback_frontend_url_is_valid(frontend_url())
        and loopback_frontend_url_is_valid(frontend_origin())
    )


def _migration_versions() -> set[str]:
    folder = ROOT / "database" / "migrations"
    return {
        path.name.split("_", 1)[0]
        for path in folder.glob("[0-9][0-9][0-9][0-9]_*.sql")
        if path.is_file()
    }


def _document_dependency_ok() -> tuple[bool, str]:
    try:
        import docx  # noqa: F401
        import reportlab  # noqa: F401
        from PIL import Image, _imaging  # noqa: F401
    except Exception as exc:
        return False, f"Document dependency import failed ({type(exc).__name__})."
    return True, "DOCX/PDF/Pillow native dependencies import correctly."


def _database_contract_ok() -> bool:
    value = os.getenv("DATABASE_URL", "").strip().lower()
    return value.startswith("postgresql://") or value.startswith("postgres://")


def collect_release_findings(mode: str = "demo", *, full_demo: bool = False) -> list[ReleaseFinding]:
    if mode not in {"demo", "production"}:
        raise ValueError("mode must be demo or production")
    production = mode == "production"
    findings: list[ReleaseFinding] = []

    # Preserve the Phase 9 readiness surface and strengthen it rather than
    # creating a second contradictory configuration contract.
    for check in collect_checks(mode):
        status = check.status
        if full_demo and check.code in {"FEATURE_FLAG", "FRONTEND_HTTPS", "LOCAL_DEV_FRONTEND", "GENERATION_WORKER", "LIFECYCLE_WORKER"} and status == "WARN":
            status = "BLOCK"
        findings.append(ReleaseFinding(f"P9_{check.code}", status, check.message))

    findings.append(ReleaseFinding(
        "DATABASE_ENGINE",
        _status(_database_contract_ok()),
        "DATABASE_URL uses PostgreSQL." if _database_contract_ok() else "Meal Plan release requires a PostgreSQL DATABASE_URL.",
    ))

    if production:
        findings.append(ReleaseFinding(
            "DEMO_MODE_OFF",
            _status(not demo_mode()),
            "Demo safety mode is off for production." if not demo_mode() else "MEAL_PLAN_DEMO_MODE must be false in production.",
        ))
    else:
        findings.append(ReleaseFinding(
            "DEMO_MODE_ON",
            _status(demo_mode(), block=full_demo),
            "Demo safety mode is enabled." if demo_mode() else "Set MEAL_PLAN_DEMO_MODE=true before running the local Telegram demo stack.",
        ))
        findings.append(ReleaseFinding(
            "DEMO_BOT_ID_GUARD",
            "PASS" if demo_bot_id() else "WARN",
            "Demo bot id guard is configured." if demo_bot_id() else "MEAL_PLAN_DEMO_BOT_ID is optional but strongly recommended before deleting a webhook or polling.",
        ))

    group_ok = review_group_id() < 0
    findings.append(ReleaseFinding(
        "PRIVATE_GROUP_SHAPE",
        _status(group_ok),
        "Review destination uses a Telegram group/supergroup id." if group_ok else "MEAL_PLAN_REVIEW_GROUP_ID should be a negative Telegram group/supergroup id.",
    ))
    findings.append(ReleaseFinding(
        "REVIEWER_SET",
        _status(bool(reviewer_ids())),
        "Authorized reviewer ids are configured." if reviewer_ids() else "No authorized Meal Plan reviewer ids are configured.",
    ))

    if production or full_demo:
        if not production and guarded_local_dev_mode():
            findings.append(ReleaseFinding(
                "LOCAL_DEV_FRONTEND",
                _status(_local_dev_frontend_is_valid()),
                "Guarded localhost Mini App frontend enabled."
                if _local_dev_frontend_is_valid()
                else "Local dev requires HTTP loopback origins on port 5173 for MEAL_PLAN_FRONTEND_URL and FRONTEND_ORIGIN.",
            ))
        else:
            findings.append(ReleaseFinding(
                "PUBLIC_FRONTEND",
                _status(_frontend_host_is_public_https()),
                "Mini App frontend is a public HTTPS URL." if _frontend_host_is_public_https() else "A real public HTTPS MEAL_PLAN_FRONTEND_URL is required for the Telegram Mini App journey.",
            ))
        findings.append(ReleaseFinding(
            "WORKERS_ON",
            _status(generation_worker_enabled() and lifecycle_worker_enabled()),
            "Generation and lifecycle workers are enabled." if generation_worker_enabled() and lifecycle_worker_enabled() else "Both Meal Plan workers must be enabled for the full lifecycle test.",
        ))

    findings.append(ReleaseFinding(
        "PAYMENT_MANUAL_FIRST",
        _status(not auto_approve_payments()),
        "Payment auto-approval is off." if not auto_approve_payments() else "Automatic Meal Plan payment approval is not allowed for the initial release candidate.",
    ))

    migrations = _migration_versions()
    findings.append(ReleaseFinding(
        "MIGRATION_SET",
        _status(EXPECTED_ENGINE_MIGRATIONS.issubset(migrations)),
        "Required Meal Plan migrations 0001 through 0003 are present." if EXPECTED_ENGINE_MIGRATIONS.issubset(migrations) else "Required Meal Plan migrations 0001/0002/0003 are missing.",
    ))

    try:
        dataset = load_dataset()
        dataset_ok = dataset.version == EXPECTED_DATASET_VERSION and len(dataset.foods) == 111 and len(dataset.templates) == 64
        recipe_rows = list(dataset.recipes)
        uncalibrated = sum("required" in str(row.get("Calibration Status") or "").lower() for row in recipe_rows)
    except Exception:
        dataset_ok = False
        uncalibrated = -1
    findings.append(ReleaseFinding(
        "DATASET_SNAPSHOT",
        _status(dataset_ok),
        "Bundled Hilawe v1.3 dataset snapshot matches the locked engine contract." if dataset_ok else "Bundled Hilawe dataset is missing or does not match the locked v1.3 contract.",
    ))
    if uncalibrated > 0:
        findings.append(ReleaseFinding(
            "RECIPE_CALIBRATION",
            "WARN" if not production else "BLOCK",
            f"{uncalibrated} source recipe rows still require Coach calibration before broad production release.",
        ))

    deps_ok, deps_message = _document_dependency_ok()
    findings.append(ReleaseFinding("DOCUMENT_DEPS", _status(deps_ok), deps_message))

    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    req_ok = all(name in requirements for name in ("python-docx", "reportlab", "pillow"))
    findings.append(ReleaseFinding(
        "DOCUMENT_REQUIREMENTS",
        _status(req_ok),
        "Document runtime dependencies are pinned in requirements.txt." if req_ok else "requirements.txt is missing a required document dependency.",
    ))

    package_path = ROOT / "meal_plan_miniapp" / "package.json"
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
        frontend_ok = package.get("version") == "1.0.0"
    except Exception:
        frontend_ok = False
    findings.append(ReleaseFinding(
        "FRONTEND_RC_VERSION",
        _status(frontend_ok),
        "Mini App package is marked 1.0.0 release candidate." if frontend_ok else "Mini App package version is not 1.0.0.",
    ))

    return findings


def release_report(mode: str = "demo", *, full_demo: bool = False) -> ReleaseReport:
    findings = collect_release_findings(mode, full_demo=full_demo)
    blockers = sum(item.status == "BLOCK" for item in findings)
    warnings = sum(item.status == "WARN" for item in findings)
    return ReleaseReport(
        mode=mode,
        full_demo=full_demo,
        ready=blockers == 0,
        blockers=blockers,
        warnings=warnings,
        findings=tuple(findings),
    )
