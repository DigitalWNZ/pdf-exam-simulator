from pathlib import Path

import pytest

REAL_PDF = Path(__file__).resolve().parents[2] / "source" / "pde_349.pdf"


@pytest.fixture(scope="session")
def real_pdf() -> Path:
    if not REAL_PDF.is_file():
        pytest.skip(f"real PDF not present at {REAL_PDF}")
    return REAL_PDF
