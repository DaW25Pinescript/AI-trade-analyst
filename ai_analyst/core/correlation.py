"""
Phase 3 — Correlation ID context propagation.

Provides a contextvars-based correlation ID that threads through all async
operations within a single pipeline run. Every log record, usage entry, and
progress event can access the current run_id without explicit parameter passing.

Usage:
    from ..core.correlation import correlation_ctx, get_correlation_id

    # Set at the start of a run (API endpoint or CLI)
    token = correlation_ctx.set(run_id)
    try:
        ...  # all downstream code can call get_correlation_id()
    finally:
        correlation_ctx.reset(token)

    # Read anywhere in the call stack
    run_id = get_correlation_id()  # returns "" if not set
"""
import logging
from contextvars import ContextVar

# The correlation context variable — set once per run, readable anywhere.
correlation_ctx: ContextVar[str] = ContextVar("correlation_ctx", default="")


def get_correlation_id() -> str:
    """Return the current correlation ID, or empty string if not set."""
    return correlation_ctx.get()


class CorrelationFilter(logging.Filter):
    """
    Logging filter that injects the current correlation ID (run_id) into
    every log record as `record.run_id`.

    Attach to a handler or the root logger:
        handler.addFilter(CorrelationFilter())

    Then use in formatters:
        "%(asctime)s [%(run_id)s] %(name)s %(levelname)s %(message)s"
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = get_correlation_id()  # type: ignore[attr-defined]
        return True


def setup_structured_logging(level: int = logging.INFO) -> None:
    """
    Configure the root logger with structured format including correlation IDs.

    Safe to call multiple times — checks if the handler is already attached.
    """
    root = logging.getLogger()

    # Avoid duplicate handlers on repeated calls
    handler_name = "_phase3_structured"
    for h in root.handlers:
        if getattr(h, "_phase3_tag", None) == handler_name:
            return

    handler = logging.StreamHandler()
    handler._phase3_tag = handler_name  # type: ignore[attr-defined]
    handler.addFilter(CorrelationFilter())
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [run:%(run_id)s] %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))

    root.addHandler(handler)
    root.setLevel(level)
