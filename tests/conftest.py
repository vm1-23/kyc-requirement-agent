import os
from pathlib import Path

import pytest

os.environ.setdefault("KYC_RE_LLM", "offline")

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


@pytest.fixture
def neobank():
    from kyc_re.cli import load_case

    co = load_case(SAMPLES / "kyc_onboarding", llm="offline")
    co.run()
    return co
