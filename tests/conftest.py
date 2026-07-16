"""Pytest configuration for src-layout."""
import sys
from pathlib import Path

# Add project src/ to system path for pytest discovery
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
