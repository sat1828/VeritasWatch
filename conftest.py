"""
conftest.py — pytest configuration for VeritasWatch.

Adds the src/ directory to sys.path so all test files can import
project modules without relative path hacks.

RUNNING ALL TESTS:
  pytest tests/ -v

RUNNING WITH COVERAGE (requires pytest-cov):
  pytest tests/ -v --cov=src --cov-report=term-missing

EXPECTED RESULTS:
  test_scorer.py:   ~35 tests — all should pass
  test_utils.py:    ~15 tests — all should pass
  test_database.py: ~15 tests — all should pass (uses temp DB)

If tests fail after pulling from GitHub, the most likely cause is
a missing dependency. Run: pip install -r requirements.txt
"""

import sys
import os

# Make src/ importable from all test files
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
