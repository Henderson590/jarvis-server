"""
Agent core (Phase 1): tool-calling planner that replaced the old regex-cascade
brain.py. See planner.py for the loop, registry.py for the tool contract, and
tools_*.py for the actual capabilities.
"""
from .planner import process  # noqa: F401
from . import registry  # noqa: F401
