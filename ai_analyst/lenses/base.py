"""LensOutput contract and LensBase abstract class.

Spec: ANALYSIS_ENGINE_SPEC_v1.2.md Section 4.2

Every lens must return either a complete valid schema (status='success')
or a clean failure (status='failed', data=None). Partial data is never
acceptable — it is a contract violation.
"""

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel


class LensOutput(BaseModel):
    """Immutable output contract for every lens.

    Rules:
    - status='success' → data is a complete dict, error is None
    - status='failed'  → data is None, error is a non-empty string
    - Partial data is a contract violation
    """

    lens_id: str
    version: str
    timeframe: str
    status: Literal["success", "failed"]
    error: str | None = None
    data: dict | None = None

    def is_success(self) -> bool:
        return self.status == "success"


class LensBase(ABC):
    """Abstract base class for all lenses.

    Subclasses must set lens_id and version as class attributes,
    and implement _compute() and _validate_schema().

    The public run() method wraps _compute() so that a lens NEVER
    raises — it always returns a LensOutput.
    """

    lens_id: str
    version: str

    def run(self, price_data: dict, config: dict) -> LensOutput:
        """Public entry point. Wraps _compute() with failure handling.

        A lens must never raise — it must return a LensOutput.
        """
        timeframe = config.get("timeframe", "unknown")
        try:
            data = self._compute(price_data, config)
            self._validate_schema(data)
            return LensOutput(
                lens_id=self.lens_id,
                version=self.version,
                timeframe=timeframe,
                status="success",
                data=data,
            )
        except Exception as exc:
            return LensOutput(
                lens_id=self.lens_id,
                version=self.version,
                timeframe=timeframe,
                status="failed",
                error=str(exc),
                data=None,
            )

    @abstractmethod
    def _compute(self, price_data: dict, config: dict) -> dict:
        """Compute structured evidence from normalised OHLCV.

        Must return a complete schema — all fields present, null where
        unavailable. Must never return partial data.
        """
        ...

    @abstractmethod
    def _validate_schema(self, data: dict) -> None:
        """Validate that data matches the expected output schema.

        Raises ValueError if any required field is missing or invalid.
        """
        ...
