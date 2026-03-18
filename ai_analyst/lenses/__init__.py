"""Lens Engine — deterministic evidence computation from OHLCV data.

Each lens computes structured evidence and returns a LensOutput.
No interpretation, no opinion — compute and emit.
"""

from .base import LensBase, LensOutput
from .momentum import MomentumLens
from .structure import StructureLens
from .trend import TrendLens

__all__ = ["LensBase", "LensOutput", "MomentumLens", "StructureLens", "TrendLens"]
