#!/usr/bin/env python3
"""
AI Trade Analyst — Dashboard Generator (v2 — Data-Rich Edition)

Parses YAML frontmatter + strict Markdown tables from a progress file
and generates a self-contained, modern dashboard.html.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# YAML import — graceful fallback if PyYAML is not installed
# ---------------------------------------------------------------------------
try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# ========================== Data classes ==================================

@dataclass
class Phase:
    name: str
    description: str
    status: str
    tests: Optional[int] = None
    order: int = 0


@dataclass
class AcceptanceCriterion:
    id: str
    gate: str
    condition: str
    status: str


@dataclass
class SpecFile:
    name: str
    title: str
    phase: str
    status: str
    source_path: str
    date: Optional[str] = None
    acceptance_criteria: list[AcceptanceCriterion] = field(default_factory=list)
    total_ac: int = 0
    passed_ac: int = 0
    pending_ac: int = 0


@dataclass
class ActivityEntry:
    date: str
    phase: str
    activity: str
    pr_issue: str = ""


@dataclass
class RoadmapItem:
    priority: int
    phase: str
    description: str
    status: str
    depends_on: str


@dataclass
class DebtItem:
    id: str
    item: str
    location: str
    status: str
    severity: str


@dataclass
class RiskItem:
    name: str
    detail: str


@dataclass
class TestHistoryEntry:
    phase: str
    count: int
    description: str


@dataclass
class Phase8Week:
    week: str
    title: str
    pr: str
    goal: str
    source_path: str
    scope_summary: str = ""


@dataclass
class ProjectDashboard:
    project: str = "AI Trade Analyst"
    repo: str = ""
    last_updated: str = ""
    current_phase: str = ""
    planning_horizon: str = ""
    progress_source_path: str = ""
    phases: list[Phase] = field(default_factory=list)
    specs: list[SpecFile] = field(default_factory=list)
    activities: list[ActivityEntry] = field(default_factory=list)
    roadmap: list[RoadmapItem] = field(default_factory=list)
    phase8_weeks: list[Phase8Week] = field(default_factory=list)
    debt: list[DebtItem] = field(default_factory=list)
    risks: list[RiskItem] = field(default_factory=list)
    test_history: list[TestHistoryEntry] = field(default_factory=list)
    latest_test_count: int = 0
    total_ac: int = 0
    passed_ac: int = 0


# ========================== Helpers =======================================

def clean_text(text: str) -> str:
    """Strip inline Markdown formatting."""
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_status(text: str) -> str:
    """Normalise a status string to one of the canonical values."""
    t = text.lower().strip()
    if any(w in t for w in ("complete", "done", "closed", "merged", "resolved")):
        return "complete"
    if any(w in t for w in ("active", "current", "in progress")):
        return "active"
    if any(w in t for w in ("next", "up next")):
        return "next"
    if any(w in t for w in ("blocked", "risk")):
        return "blocked"
    if any(w in t for w in ("parked", "paused")):
        return "parked"
    if any(w in t for w in ("concept",)):
        return "concept"
    return "planned"


def relative_path(path: Path, docs_root: Path) -> str:
    return path.resolve().relative_to(docs_root.resolve()).as_posix()


# ========================== Unified table parser ==========================

def extract_section(content: str, heading: str) -> str:
    """Return the text under a ## heading, up to the next ## or EOF."""
    pattern = rf"^## {re.escape(heading)}\s*$"
    match = re.search(pattern, content, re.MULTILINE)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^## ", content[start:], re.MULTILINE)
    if next_heading:
        return content[start : start + next_heading.start()]
    return content[start:]


def parse_table_rows(section_text: str) -> list[list[str]]:
    """
    Parse Markdown table rows from a section, skipping the header and
    separator rows.  Returns a list of rows, each a list of cell strings.
    """
    rows: list[list[str]] = []
    header_seen = False
    for line in section_text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [clean_text(c) for c in line.split("|")[1:-1]]
        if not cells or all(c == "" for c in cells):
            continue
        # skip separator row (e.g. |:---|:---|)
        if all(set(c.replace(" ", "")) <= {"-", ":"} for c in cells):
            header_seen = True
            continue
        if not header_seen:
            # This is the header row — skip it
            header_seen = True
            continue
        rows.append(cells)
    return rows


# ========================== Frontmatter parsing ===========================

def parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from content.  Falls back to regex if no PyYAML."""
    if not content.lstrip().startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    raw = parts[1]
    if HAS_YAML:
        try:
            return yaml.safe_load(raw) or {}
        except Exception:
            return {}
    # Fallback: simple key: value parsing
    meta: dict = {}
    for line in raw.splitlines():
        m = re.match(r"(\w[\w_]*):\s*(.+)", line)
        if m:
            key, val = m.group(1), m.group(2).strip().strip('"').strip("'")
            meta[key] = val
    return meta


# ========================== Progress file parser ==========================

def parse_progress_file(filepath: Path, docs_root: Path) -> ProjectDashboard:
    content = filepath.read_text(encoding="utf-8")
    dash = ProjectDashboard(progress_source_path=relative_path(filepath, docs_root))

    # --- Frontmatter or inline metadata ---
    meta = parse_frontmatter(content)
    dash.project = meta.get("project", dash.project)
    dash.repo = meta.get("repo", dash.repo)
    raw_updated = meta.get("last_updated", "")
    dash.last_updated = str(raw_updated) if raw_updated else ""
    dash.planning_horizon = meta.get("horizon", dash.planning_horizon)
    if isinstance(meta.get("test_suites"), dict):
        vals = [v for v in meta["test_suites"].values() if isinstance(v, (int, float))]
        if vals:
            dash.latest_test_count = max(int(v) for v in vals)

    def inline_meta(label: str) -> str:
        m = re.search(rf"\*\*{re.escape(label)}:\*\*\s*(.+)", content)
        return clean_text(m.group(1)) if m else ""

    dash.repo = dash.repo or inline_meta("Repo")
    dash.last_updated = dash.last_updated or inline_meta("Last updated")
    dash.current_phase = dash.current_phase or inline_meta("Current phase")
    dash.planning_horizon = dash.planning_horizon or inline_meta("Planning horizon")

    # --- Preferred: explicit phase table ---
    section = extract_section(content, "Phase Status Overview")
    order = 0
    for row in parse_table_rows(section):
        if len(row) < 4:
            continue
        tests = int(row[3]) if row[3].isdigit() else None
        dash.phases.append(Phase(name=row[0], description=row[1], status=parse_status(row[2]), tests=tests, order=order))
        order += 1
        if tests and tests > dash.latest_test_count:
            dash.latest_test_count = tests

    # --- Fallback: current canonical progress file uses Phase Index + Roadmap ---
    if not dash.phases:
        completed_line = inline_meta("Completed named phases")
        seen = set()
        if completed_line:
            for raw in [x.strip(" .") for x in completed_line.split(",") if x.strip()]:
                name = clean_text(raw)
                if name and name not in seen:
                    dash.phases.append(Phase(name=name, description="Completed phase", status="complete", order=order))
                    seen.add(name)
                    order += 1
        current_phase = inline_meta("Current phase")
        if current_phase:
            name = clean_text(current_phase.split(".")[0])
            if name and name not in seen:
                dash.phases.append(Phase(name=name, description=current_phase, status="active", order=order))
                seen.add(name)
                order += 1

    # --- Recent Activity ---
    for row in parse_table_rows(extract_section(content, "Recent Activity")):
        if len(row) >= 3:
            dash.activities.append(ActivityEntry(date=row[0], phase=row[1], activity=row[2], pr_issue=row[3] if len(row) > 3 else ""))

    # --- Roadmap ---
    roadmap_rows = parse_table_rows(extract_section(content, "Roadmap"))
    for row in roadmap_rows:
        if len(row) >= 5:
            try:
                priority = int(row[0])
            except ValueError:
                priority = 99
            dash.roadmap.append(RoadmapItem(priority=priority, phase=row[1], description=row[2], status=parse_status(row[3]), depends_on=row[4]))

    # Fallback phase enrichment from roadmap when no explicit table exists
    if roadmap_rows:
        existing = {p.name for p in dash.phases}
        for row in roadmap_rows:
            if len(row) < 5:
                continue
            name = row[1]
            if name not in existing:
                dash.phases.append(Phase(name=name, description=row[2], status=parse_status(row[3]), order=order))
                existing.add(name)
                order += 1

    # --- Technical Debt Register ---
    for row in parse_table_rows(extract_section(content, "Technical Debt Register")):
        if len(row) >= 5:
            dash.debt.append(DebtItem(id=row[0], item=row[1], location=row[2], status=row[3].lower().strip(), severity=row[4].lower().strip()))

    # --- Risk Register ---
    for row in parse_table_rows(extract_section(content, "Risk Register")):
        if len(row) >= 2:
            dash.risks.append(RiskItem(name=row[0], detail=row[1]))

    # --- Test History ---
    for row in parse_table_rows(extract_section(content, "Test History")):
        if len(row) >= 3:
            num = re.sub(r"[^0-9]", "", row[1])
            if num:
                dash.test_history.append(TestHistoryEntry(phase=row[0], count=int(num), description=row[2]))

    # Fallback latest test count from body text
    if not dash.latest_test_count:
        counts = [int(x.replace(",", "")) for x in re.findall(r"(\d[\d,]{1,6})\s+tests", content, re.I)]
        dash.latest_test_count = max(counts) if counts else 0

    return dash


# ========================== Spec file parser ==============================

def parse_spec_file(filepath: Path, docs_root: Path) -> SpecFile:
    content = filepath.read_text(encoding="utf-8")
    title_m = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    title = clean_text(title_m.group(1)) if title_m else filepath.stem
    phase_m = re.search(r"\*\*Phase:\*\*\s*(.+)", content)
    status_m = re.search(r"\*\*Status:\*\*\s*(.+)", content)
    date_m = re.search(r"\*\*Date:\*\*\s*(.+)", content)
    spec = SpecFile(
        name=filepath.stem, title=title,
        phase=clean_text(phase_m.group(1)) if phase_m else "",
        status=parse_status(status_m.group(1) if status_m else ""),
        source_path=relative_path(filepath, docs_root),
        date=clean_text(date_m.group(1)) if date_m else None,
    )
    ac_rows = re.findall(
        r"\|\s*(AC-\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", content
    )
    for ac_id, gate, condition, ac_status_text in ac_rows:
        ac_status_text = clean_text(ac_status_text)
        if any(w in ac_status_text.lower() for w in ("pass", "✅")):
            ac_status = "passed"
        elif any(w in ac_status_text.lower() for w in ("fail", "❌")):
            ac_status = "failed"
        else:
            ac_status = "pending"
        spec.acceptance_criteria.append(AcceptanceCriterion(
            id=ac_id.strip(), gate=clean_text(gate),
            condition=clean_text(condition), status=ac_status,
        ))
    spec.total_ac = len(spec.acceptance_criteria)
    spec.passed_ac = sum(1 for ac in spec.acceptance_criteria if ac.status == "passed")
    spec.pending_ac = sum(1 for ac in spec.acceptance_criteria if ac.status == "pending")
    return spec


# ========================== Phase 8 plan parser ===========================

def parse_phase8_plan(filepath: Path, docs_root: Path) -> list[Phase8Week]:
    content = filepath.read_text(encoding="utf-8")
    weeks: list[Phase8Week] = []
    for match in re.finditer(r"### Week (\d+):\s*(.+?)\s*\((PR-.+?)\)", content):
        week_num, title, pr = match.groups()
        start = match.end()
        next_week = re.search(r"### Week", content[start:])
        end = start + next_week.start() if next_week else len(content)
        section = content[start:end]
        goal_m = re.search(r"\*\*Goal:\*\*\s*(.+?)(?=\n\n|\n\*\*Scope:)", section, re.DOTALL)
        scope_m = re.search(r"\*\*Scope:\*\*\s*(.+?)(?=\n\n|\n###|\n##)", section, re.DOTALL)
        goal = clean_text(goal_m.group(1)) if goal_m else clean_text(title)
        scope_summary = clean_text(scope_m.group(1)) if scope_m else ""
        if len(scope_summary) > 240:
            scope_summary = scope_summary[:237] + "..."
        weeks.append(Phase8Week(
            week=f"Week {week_num}", title=clean_text(title), pr=clean_text(pr),
            goal=goal, source_path=relative_path(filepath, docs_root),
            scope_summary=scope_summary,
        ))
    return weeks


# ========================== HTML Generation ===============================

def generate_html(dash: ProjectDashboard) -> str:
    total_phases = len(dash.phases)
    complete_phases = sum(1 for p in dash.phases if p.status == "complete")
    completion_pct = round((complete_phases / total_phases) * 100) if total_phases else 0

    dash.total_ac = sum(s.total_ac for s in dash.specs)
    dash.passed_ac = sum(s.passed_ac for s in dash.specs)
    ac_pct = round((dash.passed_ac / dash.total_ac) * 100) if dash.total_ac else 0

    active_phases = [p for p in dash.phases if p.status == "active"]
    next_phases = [p for p in dash.phases if p.status in ("next", "planned")]
    current_label = active_phases[0].name if active_phases else (next_phases[0].name if next_phases else "—")
    blocked_count = sum(1 for p in dash.phases if p.status == "blocked")
    open_debt = sum(1 for d in dash.debt if d.status == "open")
    resolved_debt = sum(1 for d in dash.debt if d.status == "resolved")

    project_name = dash.project or (dash.repo.split("/")[-1] if "/" in dash.repo else dash.repo) or "Project"
    updated = str(dash.last_updated) or datetime.now().strftime("%Y-%m-%d")
    horizon = dash.planning_horizon or "Active planning"

    # JSON data for JS
    phases_json = json.dumps([asdict(p) for p in dash.phases])
    specs_json = json.dumps([asdict(s) for s in dash.specs])
    activities_json = json.dumps([asdict(a) for a in dash.activities])
    roadmap_json = json.dumps([asdict(r) for r in dash.roadmap])
    phase8_json = json.dumps([asdict(w) for w in dash.phase8_weeks])
    debt_json = json.dumps([asdict(d) for d in dash.debt])
    risks_json = json.dumps([asdict(r) for r in dash.risks])
    test_history_json = json.dumps([asdict(t) for t in dash.test_history])

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard — {escape(project_name)}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{
  --bg:#0f1117;--bg2:#1a1d27;--card:#1e2130;--border:#2a2d3e;
  --text:#e8eaf0;--text2:#8b8fa3;--muted:#5a5e72;
  --teal:#2dd4bf;--green:#4ade80;--amber:#fbbf24;--red:#f87171;--blue:#60a5fa;--purple:#a78bfa;
  --teal-d:rgba(45,212,191,.12);--green-d:rgba(74,222,128,.12);--amber-d:rgba(251,191,36,.12);
  --red-d:rgba(248,113,113,.12);--blue-d:rgba(96,165,250,.12);--purple-d:rgba(167,139,250,.12);
  --r:8px;--rl:12px;
}}
html,body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;min-height:100vh}}
a{{color:var(--teal);text-decoration:none}}a:hover{{text-decoration:underline}}

/* Header */
.header{{background:var(--bg2);border-bottom:1px solid var(--border);padding:20px 28px}}
.header h1{{font-size:22px;font-weight:700}}
.meta{{display:flex;gap:20px;color:var(--text2);font-size:13px;margin-top:6px;flex-wrap:wrap}}
.meta b{{color:var(--muted);font-weight:400}}

/* Layout */
.wrap{{max-width:1400px;margin:0 auto;padding:24px 28px}}

/* Progress bar */
.progress-box{{background:var(--bg2);border:1px solid var(--border);border-radius:var(--rl);padding:24px;margin-bottom:20px}}
.progress-box h2{{font-size:14px;text-transform:uppercase;letter-spacing:.5px;color:var(--text2);margin-bottom:12px}}
.rail{{height:14px;background:var(--bg);border-radius:8px;overflow:hidden}}
.fill{{height:100%;background:linear-gradient(90deg,var(--teal),var(--green));border-radius:8px;transition:width .4s ease}}
.progress-info{{display:flex;justify-content:space-between;margin-top:8px;font-size:12px;color:var(--text2)}}

/* Stats row */
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-bottom:20px}}
.stat{{background:var(--card);border:1px solid var(--border);border-radius:var(--rl);padding:16px;text-align:center}}
.stat .n{{font-size:32px;font-weight:800;line-height:1}}
.stat .l{{font-size:11px;color:var(--text2);text-transform:uppercase;letter-spacing:.4px;margin-top:4px}}
.stat .s{{font-size:10px;color:var(--muted);margin-top:2px}}
.c-teal{{color:var(--teal)}}.c-blue{{color:var(--blue)}}.c-green{{color:var(--green)}}.c-purple{{color:var(--purple)}}.c-amber{{color:var(--amber)}}.c-red{{color:var(--red)}}

/* Tabs */
.tabs{{display:flex;gap:2px;border-bottom:1px solid var(--border);margin-bottom:20px;flex-wrap:wrap}}
.tab{{padding:8px 18px;font-size:13px;font-weight:600;color:var(--text2);background:none;border:none;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px}}
.tab.active{{color:var(--teal);border-bottom-color:var(--teal)}}
.panel{{display:none}}.panel.active{{display:block}}

/* Filter row */
.filters{{display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap}}
.fbtn{{background:var(--card);color:var(--text2);border:1px solid var(--border);border-radius:99px;padding:5px 12px;cursor:pointer;font-size:12px}}
.fbtn.active{{color:var(--teal);border-color:var(--teal)}}

/* Cards & chips */
.card{{background:var(--card);border:1px solid var(--border);border-radius:var(--rl);padding:16px;margin-bottom:10px}}
.card:hover{{border-color:rgba(45,212,191,.3)}}
.chip-complete{{border-left:3px solid var(--green)}}.chip-active{{border-left:3px solid var(--teal)}}.chip-next,.chip-planned{{border-left:3px solid var(--amber)}}.chip-blocked{{border-left:3px solid var(--red)}}.chip-parked{{border-left:3px solid var(--muted)}}.chip-concept{{border-left:3px solid var(--purple);opacity:.75;border-style:dashed}}
.card-head{{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}}
.card-title{{font-weight:700;font-size:14px}}.card-desc{{color:var(--text2);font-size:12px;margin-top:4px}}.card-meta{{color:var(--muted);font-size:11px;margin-top:6px}}
.pill{{font-size:10px;padding:2px 8px;border-radius:10px;font-weight:600;white-space:nowrap}}
.pill-teal{{background:var(--teal-d);color:var(--teal)}}.pill-amber{{background:var(--amber-d);color:var(--amber)}}.pill-red{{background:var(--red-d);color:var(--red)}}.pill-green{{background:var(--green-d);color:var(--green)}}.pill-blue{{background:var(--blue-d);color:var(--blue)}}.pill-purple{{background:var(--purple-d);color:var(--purple)}}

/* Activity feed */
.act{{display:grid;grid-template-columns:90px 110px 1fr;gap:10px;align-items:start;padding:10px 14px}}
.act-date{{color:var(--muted);font-size:11px;font-weight:700}}.act-phase{{color:var(--teal);font-weight:700;font-size:12px}}.act-text{{color:var(--text2);font-size:12px}}

/* Roadmap */
.rm-priority{{width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;background:var(--teal-d);color:var(--teal);flex-shrink:0}}
.rm-concept .rm-priority{{background:var(--purple-d);color:var(--purple)}}

/* Spec cards */
.spec-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px}}
.spec-bar{{height:6px;background:var(--bg);border-radius:4px;overflow:hidden;display:flex;margin:8px 0 6px}}
.spec-fill-pass{{background:var(--green)}}.spec-fill-pend{{background:var(--amber)}}
.ac-toggle{{margin-top:10px;width:100%;background:var(--bg);color:var(--text2);border:1px solid var(--border);padding:6px 8px;border-radius:6px;cursor:pointer;font-size:11px}}
.ac-list{{margin-top:8px;display:none;flex-direction:column;gap:6px}}.ac-list.open{{display:flex}}
.ac-item{{display:flex;gap:8px;align-items:flex-start;font-size:11px;color:var(--text2)}}
.ac-dot{{width:7px;height:7px;border-radius:50%;margin-top:5px;flex-shrink:0}}.dot-passed{{background:var(--green)}}.dot-pending{{background:var(--amber)}}.dot-failed{{background:var(--red)}}

/* Debt grid */
.debt-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}}
.sev-critical{{border-left:3px solid var(--red)}}.sev-maintenance{{border-left:3px solid var(--amber)}}.sev-low{{border-left:3px solid var(--blue)}}

/* Test history chart */
.th-bar-wrap{{display:flex;align-items:flex-end;gap:6px;height:120px;padding:8px 0}}
.th-bar{{flex:1;background:var(--teal-d);border-radius:4px 4px 0 0;position:relative;min-width:20px;transition:height .3s ease}}
.th-bar:hover{{background:var(--teal)}}
.th-bar .tip{{position:absolute;bottom:100%;left:50%;transform:translateX(-50%);background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:4px 8px;font-size:10px;white-space:nowrap;display:none;z-index:10}}
.th-bar:hover .tip{{display:block}}
.th-labels{{display:flex;gap:6px}}.th-labels span{{flex:1;text-align:center;font-size:9px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:20px}}

/* Week cards */
.week-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}
.wk-num{{color:var(--teal);font-weight:800;font-size:16px}}.wk-pr{{background:var(--amber-d);color:var(--amber);padding:2px 8px;border-radius:99px;font-size:10px;font-weight:700}}.wk-title{{font-weight:700;margin:6px 0 4px}}.wk-goal{{color:var(--green);font-size:13px}}.wk-scope{{color:var(--text2);font-size:12px;margin-top:6px}}

/* Risk cards */
.risk-name{{font-weight:700;color:var(--amber);margin-bottom:4px}}

/* Empty state */
.empty{{color:var(--muted);font-size:13px;padding:16px;border:1px dashed var(--border);border-radius:var(--r)}}

/* Footer */
.footer{{max-width:1400px;margin:40px auto 0;padding:0 28px 28px;color:var(--muted);font-size:11px;border-top:1px solid var(--border);padding-top:16px}}

@media(max-width:768px){{
  .header{{padding:14px}}.wrap{{padding:14px}}.stats{{grid-template-columns:repeat(2,1fr)}}
  .spec-grid,.debt-grid,.week-grid{{grid-template-columns:1fr}}.act{{grid-template-columns:1fr}}
}}
</style>
</head>
<body>

<div class="header">
  <h1>{escape(project_name)}</h1>
  <div class="meta">
    <span><b>Repo:</b> {escape(dash.repo or '—')}</span>
    <span><b>Updated:</b> {escape(updated)}</span>
    <span><b>Horizon:</b> {escape(horizon)}</span>
    <span><b>Source:</b> <a href="{escape(dash.progress_source_path)}">{escape(dash.progress_source_path)}</a></span>
  </div>
</div>

<div class="wrap">
  <!-- Progress bar -->
  <div class="progress-box">
    <h2>Project Timeline</h2>
    <div class="rail"><div class="fill" style="width:{completion_pct}%"></div></div>
    <div class="progress-info">
      <span>{completion_pct}% complete — {complete_phases} of {total_phases} phases</span>
      <span>Active: {escape(current_label)}</span>
    </div>
  </div>

  <!-- Stats -->
  <div class="stats">
    <div class="stat"><div class="n c-teal">{completion_pct}%</div><div class="l">Phases done</div><div class="s">{complete_phases}/{total_phases}</div></div>
    <div class="stat"><div class="n c-blue">{ac_pct}%</div><div class="l">Acceptance criteria</div><div class="s">{dash.passed_ac}/{dash.total_ac} passing</div></div>
    <div class="stat"><div class="n c-purple">{dash.latest_test_count:,}</div><div class="l">Latest tests</div><div class="s">Peak count detected</div></div>
    <div class="stat"><div class="n c-green">{len(dash.specs)}</div><div class="l">Spec files</div><div class="s">Parsed from docs</div></div>
    <div class="stat"><div class="n c-amber">{open_debt}</div><div class="l">Open debt</div><div class="s">{resolved_debt} resolved</div></div>
    <div class="stat"><div class="n c-red">{len(dash.risks)}</div><div class="l">Risks</div><div class="s">{blocked_count} blocked phases</div></div>
  </div>

  <!-- Tabs -->
  <div class="tabs">
    <button class="tab active" data-tab="phases">Phases</button>
    <button class="tab" data-tab="activity">Activity</button>
    <button class="tab" data-tab="roadmap">Roadmap</button>
    <button class="tab" data-tab="specs">Specs</button>
    <button class="tab" data-tab="debt">Tech Debt</button>
    <button class="tab" data-tab="risks">Risks</button>
    <button class="tab" data-tab="tests">Test History</button>
    <button class="tab" data-tab="phase8">Phase 8</button>
  </div>

  <div id="p-phases" class="panel active"><div class="filters" id="phase-filters"></div><div id="phase-list"></div></div>
  <div id="p-activity" class="panel"><div id="activity-list"></div></div>
  <div id="p-roadmap" class="panel"><div id="roadmap-list"></div></div>
  <div id="p-specs" class="panel"><div class="filters" id="spec-filters"></div><div class="spec-grid" id="spec-grid"></div></div>
  <div id="p-debt" class="panel"><div class="debt-grid" id="debt-grid"></div></div>
  <div id="p-risks" class="panel"><div id="risk-list"></div></div>
  <div id="p-tests" class="panel"><div id="test-chart"></div></div>
  <div id="p-phase8" class="panel"><div class="week-grid" id="week-grid"></div></div>
</div>

<div class="footer">Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} &middot; AI Trade Analyst Dashboard v2</div>

<script>
const D = {{
  phases: {phases_json},
  specs: {specs_json},
  activities: {activities_json},
  roadmap: {roadmap_json},
  phase8: {phase8_json},
  debt: {debt_json},
  risks: {risks_json},
  testHistory: {test_history_json}
}};

const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const esc = t => String(t??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

// --- Tabs ---
$$('.tab').forEach(btn => btn.addEventListener('click', () => {{
  $$('.tab').forEach(t => t.classList.remove('active'));
  $$('.panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  const p = $('#p-' + btn.dataset.tab);
  if (p) p.classList.add('active');
}}));

// --- Phases ---
let pf = 'all';
function renderPhases() {{
  const items = pf === 'all' ? D.phases : D.phases.filter(p => p.status === pf);
  const el = $('#phase-list');
  if (!items.length) {{ el.innerHTML = '<div class="empty">No phases match this filter.</div>'; return; }}
  el.innerHTML = items.map(p => `
    <div class="card chip-${{esc(p.status)}}">
      <div class="card-head"><div class="card-title">${{esc(p.name)}}</div><span class="pill pill-teal">${{esc(p.status)}}</span></div>
      <div class="card-desc">${{esc(p.description)}}</div>
      ${{p.tests ? `<div class="card-meta">${{p.tests.toLocaleString()}} tests</div>` : ''}}
    </div>`).join('');
}}
function renderPhaseFilters() {{
  const statuses = ['all', ...new Set(D.phases.map(p => p.status))];
  const el = $('#phase-filters');
  el.innerHTML = statuses.map(s => `<button class="fbtn ${{pf===s?'active':''}}" data-v="${{s}}">${{s}}</button>`).join('');
  el.querySelectorAll('.fbtn').forEach(b => b.addEventListener('click', () => {{ pf = b.dataset.v; renderPhaseFilters(); renderPhases(); }}));
}}
renderPhaseFilters(); renderPhases();

// --- Activity ---
(function() {{
  const el = $('#activity-list');
  if (!D.activities.length) {{ el.innerHTML = '<div class="empty">No activity entries found.</div>'; return; }}
  el.innerHTML = D.activities.map(a => `
    <div class="card act">
      <div class="act-date">${{esc(a.date)}}</div>
      <div class="act-phase">${{esc(a.phase)}}</div>
      <div class="act-text">${{esc(a.activity)}}</div>
    </div>`).join('');
}})();

// --- Roadmap ---
(function() {{
  const el = $('#roadmap-list');
  if (!D.roadmap.length) {{ el.innerHTML = '<div class="empty">No roadmap items found.</div>'; return; }}
  el.innerHTML = D.roadmap.map(r => `
    <div class="card chip-${{esc(r.status)}} rm-${{esc(r.status)}}">
      <div style="display:flex;gap:12px;align-items:flex-start">
        <div class="rm-priority">${{esc(r.priority)}}</div>
        <div>
          <div class="card-title">${{esc(r.phase)}}</div>
          <div class="card-desc">${{esc(r.description)}}</div>
          <div class="card-meta">Depends on: ${{esc(r.depends_on || '—')}}</div>
        </div>
      </div>
    </div>`).join('');
}})();

// --- Specs ---
let sf = 'all';
function renderSpecs() {{
  const items = sf === 'all' ? D.specs : D.specs.filter(s => s.status === sf);
  const el = $('#spec-grid');
  if (!items.length) {{ el.innerHTML = '<div class="empty">No specs match this filter.</div>'; return; }}
  el.innerHTML = '';
  items.forEach(s => {{
    const pp = s.total_ac ? Math.round((s.passed_ac/s.total_ac)*100) : 0;
    const pn = s.total_ac ? Math.round((s.pending_ac/s.total_ac)*100) : 0;
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <div class="card-head">
        <div><div class="card-title"><a href="${{esc(s.source_path)}}">${{esc(s.name)}}</a></div><div class="card-desc">${{esc(s.title)}}</div></div>
        <span class="pill pill-teal">${{esc(s.status)}}</span>
      </div>
      <div class="spec-bar"><div class="spec-fill-pass" style="width:${{pp}}%"></div><div class="spec-fill-pend" style="width:${{pn}}%"></div></div>
      <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--muted)"><span>${{s.passed_ac}} passed</span><span>${{s.pending_ac}} pending</span><span>${{s.total_ac}} total</span></div>
      <button class="ac-toggle">Show acceptance criteria</button>
      <div class="ac-list">${{(s.acceptance_criteria||[]).map(ac => `<div class="ac-item"><div class="ac-dot dot-${{esc(ac.status)}}"></div><span><b>${{esc(ac.id)}}</b> ${{esc(ac.condition)}}</span></div>`).join('') || '<div class="empty">No ACs parsed.</div>'}}</div>`;
    card.querySelector('.ac-toggle').addEventListener('click', function() {{
      const list = card.querySelector('.ac-list');
      list.classList.toggle('open');
      this.textContent = list.classList.contains('open') ? 'Hide acceptance criteria' : 'Show acceptance criteria';
    }});
    el.appendChild(card);
  }});
}}
function renderSpecFilters() {{
  const filters = ['all','complete','active','planned','pending'];
  const el = $('#spec-filters');
  el.innerHTML = filters.map(s => `<button class="fbtn ${{sf===s?'active':''}}" data-v="${{s}}">${{s}}</button>`).join('');
  el.querySelectorAll('.fbtn').forEach(b => b.addEventListener('click', () => {{ sf = b.dataset.v; renderSpecFilters(); renderSpecs(); }}));
}}
renderSpecFilters(); renderSpecs();

// --- Tech Debt ---
(function() {{
  const el = $('#debt-grid');
  if (!D.debt.length) {{ el.innerHTML = '<div class="empty">No technical debt items found.</div>'; return; }}
  el.innerHTML = D.debt.map(d => `
    <div class="card sev-${{esc(d.severity)}}">
      <div class="card-head">
        <div class="card-title">${{esc(d.id)}}: ${{esc(d.item)}}</div>
        <span class="pill ${{d.status==='resolved'?'pill-green':'pill-amber'}}">${{esc(d.status)}}</span>
      </div>
      <div class="card-desc">${{esc(d.location)}}</div>
      <div class="card-meta">Severity: ${{esc(d.severity)}}</div>
    </div>`).join('');
}})();

// --- Risks ---
(function() {{
  const el = $('#risk-list');
  if (!D.risks.length) {{ el.innerHTML = '<div class="empty">No risks registered.</div>'; return; }}
  el.innerHTML = D.risks.map(r => `
    <div class="card" style="border-left:3px solid var(--amber)">
      <div class="risk-name">${{esc(r.name)}}</div>
      <div class="card-desc">${{esc(r.detail)}}</div>
    </div>`).join('');
}})();

// --- Test History Chart ---
(function() {{
  const el = $('#test-chart');
  if (!D.testHistory.length) {{ el.innerHTML = '<div class="empty">No test history entries found.</div>'; return; }}
  const maxCount = Math.max(...D.testHistory.map(t => t.count));
  el.innerHTML = `
    <div class="th-bar-wrap">${{D.testHistory.map(t => {{
      const h = maxCount ? Math.max(8, Math.round((t.count/maxCount)*100)) : 8;
      return `<div class="th-bar" style="height:${{h}}%"><div class="tip">${{esc(t.phase)}}: ${{t.count.toLocaleString()}} tests</div></div>`;
    }}).join('')}}</div>
    <div class="th-labels">${{D.testHistory.map(t => `<span title="${{esc(t.phase)}}">${{esc(t.phase.length > 12 ? t.phase.slice(0,10)+'…' : t.phase)}}</span>`).join('')}}</div>`;
}})();

// --- Phase 8 ---
(function() {{
  const el = $('#week-grid');
  if (!D.phase8.length) {{ el.innerHTML = '<div class="empty">No Phase 8 roadmap file found.</div>'; return; }}
  el.innerHTML = D.phase8.map(w => `
    <div class="card">
      <div style="display:flex;justify-content:space-between;margin-bottom:8px"><span class="wk-num">${{esc(w.week)}}</span><span class="wk-pr">${{esc(w.pr)}}</span></div>
      <div class="wk-title">${{esc(w.title)}}</div>
      <div class="wk-goal">${{esc(w.goal)}}</div>
      ${{w.scope_summary ? `<div class="wk-scope">${{esc(w.scope_summary)}}</div>` : ''}}
    </div>`).join('');
}})();
</script>
</body>
</html>'''


# ========================== Main ==========================================

def main() -> int:
    parser = argparse.ArgumentParser(description="AI Trade Analyst — Dashboard Generator v2")
    parser.add_argument("--folder", "-f", required=True, help="Docs folder or repo root to scan")
    parser.add_argument("--output", "-o", default="dashboard.html")
    args = parser.parse_args()

    folder = Path(args.folder).resolve()
    if not folder.exists() or not folder.is_dir():
        print(f"[ERROR] Folder not found or not a directory: {folder}")
        return 1
    if folder.name.lower() != "docs" and (folder / "docs").is_dir():
        folder = (folder / "docs").resolve()

    # Find progress file
    progress_files = sorted(
        [f for f in folder.rglob("*Progress*.md") if "archive" not in str(f).lower()]
    )
    if not progress_files:
        progress_files = sorted(
            [f for f in folder.rglob("*.md") if "progress" in f.name.lower() and "archive" not in str(f).lower()]
        )
    if not progress_files:
        print("[ERROR] No Progress markdown file found in", folder)
        return 1

    print(f"[INFO] Parsing progress file: {progress_files[0].name}")
    dashboard = parse_progress_file(progress_files[0], folder)

    # Parse spec files
    spec_files = sorted(
        [f for f in folder.rglob("*SPEC*.md") if "archive" not in str(f).lower()]
    )
    for sf in spec_files:
        try:
            dashboard.specs.append(parse_spec_file(sf, folder))
        except Exception as exc:
            print(f"[WARN] Skipping spec parse failure for {sf.name}: {exc}")

    # Parse Phase 8 roadmap
    phase8_file = next(
        (f for f in sorted(folder.rglob("*PHASE_8*Roadmap*.md")) if "archive" not in str(f).lower()),
        None,
    )
    if phase8_file:
        dashboard.phase8_weeks = parse_phase8_plan(phase8_file, folder)

    # Generate
    html = generate_html(dashboard)
    output_path = Path(args.output)
    output_path.write_text(html, encoding="utf-8")

    print(f"[OK] Dashboard generated: {output_path}")
    print(f"     Project:  {dashboard.project}")
    print(f"     Phases:   {len(dashboard.phases)}")
    print(f"     Specs:    {len(dashboard.specs)}")
    print(f"     Debt:     {len(dashboard.debt)} ({sum(1 for d in dashboard.debt if d.status == 'open')} open)")
    print(f"     Risks:    {len(dashboard.risks)}")
    print(f"     Tests:    {dashboard.latest_test_count:,} (peak)")
    if not HAS_YAML:
        print("[NOTE] PyYAML not installed — used fallback frontmatter parser.")
        print("       Install with: pip install pyyaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
