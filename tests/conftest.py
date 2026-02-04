from __future__ import annotations

from pathlib import Path
import sys


# Ensure `quark_strm/` is on sys.path so tests can import `app.*`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

