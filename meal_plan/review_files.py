from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MIME = "application/pdf"


class ReviewFileError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedReviewFile:
    artifact_type: str
    path: Path
    filename: str
    sha256: str
    byte_size: int


def classify_review_filename(filename: str, mime_type: str | None = None) -> str:
    name = (filename or "").strip().lower()
    mime = (mime_type or "").strip().lower()
    if name.endswith(".pdf") or mime == PDF_MIME:
        return "PDF"
    if name.endswith(".docx") or mime == DOCX_MIME:
        return "DOCX"
    raise ReviewFileError("Only PDF and DOCX replacement files are accepted")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_review_file(path: str | Path, *, filename: str, mime_type: str | None = None, max_bytes: int = 25 * 1024 * 1024) -> ValidatedReviewFile:
    file_path = Path(path)
    if not file_path.is_file():
        raise ReviewFileError("Replacement file was not found")
    size = file_path.stat().st_size
    if size <= 0:
        raise ReviewFileError("Replacement file is empty")
    if size > max_bytes:
        raise ReviewFileError(f"Replacement file is larger than {max_bytes // (1024 * 1024)} MB")

    artifact_type = classify_review_filename(filename, mime_type)
    if artifact_type == "PDF":
        with file_path.open("rb") as handle:
            signature = handle.read(5)
        if not signature.startswith(b"%PDF-"):
            raise ReviewFileError("The uploaded PDF does not have a valid PDF signature")
    else:
        if not zipfile.is_zipfile(file_path):
            raise ReviewFileError("The uploaded DOCX is not a valid Office document")
        with zipfile.ZipFile(file_path) as zf:
            names = set(zf.namelist())
        if "[Content_Types].xml" not in names or "word/document.xml" not in names:
            raise ReviewFileError("The uploaded DOCX is missing required Word document parts")

    return ValidatedReviewFile(
        artifact_type=artifact_type,
        path=file_path,
        filename=Path(filename).name,
        sha256=_sha256(file_path),
        byte_size=size,
    )
