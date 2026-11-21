"""python -m tests: test klasörü ayarlandıktan sonra testleri bulup çalıştırır."""

import sys
import unittest
from pathlib import Path

import tests  # noqa: F401  (önce test klasörü ayarlansın)

ROOT = Path(__file__).resolve().parent.parent
argv = [sys.argv[0], "discover", "-s", str(ROOT / "tests"), "-t", str(ROOT)] + sys.argv[1:]
unittest.main(module=None, argv=argv)
