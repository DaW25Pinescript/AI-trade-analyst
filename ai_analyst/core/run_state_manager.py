"""
Persists and loads RunState for each run.
State is stored in output/runs/{run_id}/state.json so runs are resumable
if the user closes the app mid-way (design principle #6 of spec v1.2).
"""
import json
from pathlib import Path
from datetime import datetime

from ..models.execution_config import RunState, RunStatus

OUTPUT_BASE = Path(__file__).parent.parent / "output" / "runs"


def _state_path(run_id: str) -> Path:
    return OUTPUT_BASE / run_id / "state.json"


def save_run_state(state: RunState) -> Path:
    run_dir = OUTPUT_BASE / state.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    path = _state_path(state.run_id)
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_run_state(run_id: str) -> RunState:
    path = _state_path(run_id)
    if not path.exists():
        raise FileNotFoundError(f"No state file found for run '{run_id}' at {path}")
    return RunState.model_validate_json(path.read_text(encoding="utf-8"))


def transition(state: RunState, new_status: RunStatus, **updates) -> RunState:
    """Return a new RunState with updated status and timestamp."""
    data = state.model_dump()
    data["status"] = new_status
    data["updated_at"] = datetime.utcnow().isoformat()
    data.update(updates)
    new_state = RunState(**data)
    save_run_state(new_state)
    return new_state


def list_all_runs() -> list[RunState]:
    """
    Return all persisted RunState objects, sorted by created_at descending.
    """
    if not OUTPUT_BASE.exists():
        return []

    states: list[RunState] = []
    for state_file in OUTPUT_BASE.glob("*/state.json"):
        try:
            states.append(RunState.model_validate_json(
                state_file.read_text(encoding="utf-8")
            ))
        except Exception:
            pass  # skip corrupt state files

    return sorted(states, key=lambda s: s.created_at, reverse=True)
