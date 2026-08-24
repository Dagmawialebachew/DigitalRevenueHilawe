from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


IVORY = "#F7F5F0"
PAPER = "#FFFEFB"
INK = "#171512"
GRAPHITE = "#5D5953"
MUTED = "#8D887F"
ORANGE = "#F27018"
ORANGE_SOFT = "#F6E8DE"
BORDER = "#DED9D1"
SUCCESS = "#2F6D4F"
WARNING = "#9A5C11"
DANGER = "#9D3E38"


@dataclass(frozen=True)
class FontPaths:
    latin_regular: Path
    latin_bold: Path
    ethiopic_regular: Path
    ethiopic_bold: Path


def _existing(candidates: list[str | Path | None]) -> Path | None:
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists() and path.is_file():
            return path
    return None


def resolve_pdf_fonts() -> FontPaths:
    latin_regular = _existing([
        os.getenv("MEAL_PLAN_PDF_LATIN_FONT_REGULAR"),
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ])
    latin_bold = _existing([
        os.getenv("MEAL_PLAN_PDF_LATIN_FONT_BOLD"),
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ])
    ethiopic_regular = _existing([
        os.getenv("MEAL_PLAN_PDF_FONT_REGULAR"),
        r"C:\Windows\Fonts\ebrima.ttf",
        r"C:\Windows\Fonts\nyala.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansEthiopic-Regular.ttf",
    ])
    ethiopic_bold = _existing([
        os.getenv("MEAL_PLAN_PDF_FONT_BOLD"),
        r"C:\Windows\Fonts\ebrimabd.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansEthiopic-Bold.ttf",
    ])
    if not all((latin_regular, latin_bold, ethiopic_regular, ethiopic_bold)):
        raise RuntimeError(
            "Meal Plan PDF fonts are unavailable. Install Noto Sans + Noto Sans Ethiopic, "
            "or set the MEAL_PLAN_PDF_* font path environment variables."
        )
    return FontPaths(
        latin_regular=latin_regular,
        latin_bold=latin_bold,
        ethiopic_regular=ethiopic_regular,
        ethiopic_bold=ethiopic_bold,
    )
