from pathlib import Path


def get_run_dir(run_id: str) -> Path:
    return Path("ai_analyst/output/runs") / run_id
