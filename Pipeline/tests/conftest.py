"""
conftest.py -- keeps every test away from any real data.

The pipeline finds your data through $OMAR_DATA_DIR (see omar_paths.py).
Setting it to a throwaway folder here, at import time (before any test
module imports chat_config, which reads it), means no test can ever read
or write your real data directory, whatever's in ../data on this machine.
"""
import os
import sys
import tempfile
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))

os.environ["OMAR_DATA_DIR"] = tempfile.mkdtemp(prefix="omar-test-data-")
