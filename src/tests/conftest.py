"""Puts src/ on sys.path so tests import p3focus without installing it (the old repo's habit)."""
import os
import sys

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SRC not in sys.path:
    sys.path.insert(0, SRC)
