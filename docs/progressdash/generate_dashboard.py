#!/usr/bin/env python3
"""
AI Trade Analyst — Dashboard Generator (refined)

Scans a docs folder for canonical progress/spec markdown files and emits a
self-contained interactive dashboard.html with drill-down links and a more
useful control-panel layout.
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


@dataclass
class RoadmapItem:
    priority: int
    phase: str
    description: str
    status: str
    depends_on: str


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
    repo: str = "AI Trade Analyst"
    last_updated: str = ""
    current_phase: str = ""
    planning_horizon: str = ""
    progress_source_path: str = ""
    phases: list[Phase] = field(default_factory=list)
    specs: list[SpecFile] = field(default_factory=list)
    activities: list[ActivityEntry] = field(default_factory=list)
    roadmap: list[RoadmapItem] = field(default_factory=list)
    phase8_weeks: list[Phase8Week] = field(default_factory=list)
    latest_test_count: int = 0
    total_ac: int = 0
    passed_ac: int = 0


def clean_text(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_status_emoji(text: str) -> str:
    t = text.lower()
    if "✅" in text or "complete" in t or "done" in t or "closed" in t or "merged" in t:
        return "complete"
    if "🟢" in text or "active" in t or "current" in t or "in progress" in t:
        return "active"
    if "▶️" in text or "up next" in t or "next" in t:
        return "next"
    if "⏸️" in text or "parked" in t:
        return "parked"
    if "blocked" in t or "❌" in text or "risk" in t:
        return "blocked"
    if "⏳" in text or "pending" in t or "planned" in t:
        return "pending"
    return "pending"


def find_section(content: str, heading: str) -> str:
    start = content.find(heading)
    if start == -1:
        return ""
    rest = content[start:]
    m = re.search(r"\n## ", rest[len(heading):])
    if not m:
        return rest
    return rest[: len(heading) + m.start()]


def relative_path(path: Path, docs_root: Path) -> str:
    return path.resolve().relative_to(docs_root.resolve()).as_posix()


def parse_progress_file(filepath: Path, docs_root: Path) -> ProjectDashboard:
    content = filepath.read_text(encoding="utf-8")
    dash = ProjectDashboard(progress_source_path=relative_path(filepath, docs_root))

    repo_m = re.search(r"\*\*Repo:\*\*\s*`([^`]+)`", content)
    if repo_m:
        dash.repo = repo_m.group(1)
    updated_m = re.search(r"\*\*Last updated:\*\*\s*(.+)", content)
    if updated_m:
        dash.last_updated = clean_text(updated_m.group(1))
    phase_m = re.search(r"\*\*Current phase:\*\*\s*(.+)", content)
    if phase_m:
        dash.current_phase = clean_text(phase_m.group(1))
    horizon_m = re.search(r"\*\*Planning horizon:\*\*\s*(.+)", content)
    if horizon_m:
        dash.planning_horizon = clean_text(horizon_m.group(1))

    phase_section = find_section(content, "### Phase Status Overview")
    if phase_section:
        rows = re.findall(r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", phase_section)
        order = 0
        for name, desc, status_text in rows:
            name = clean_text(name)
            desc = clean_text(desc)
            status_text = clean_text(status_text)
            if name in {"Phase", "---"}:
                continue
            if set(name.replace(" ", "")) <= {"-", "|"}:
                continue
            tests_m = re.search(r"(\d{1,5})\s*tests?", status_text, re.I)
            tests = int(tests_m.group(1)) if tests_m else None
            dash.phases.append(Phase(name=name, description=desc, status=parse_status_emoji(status_text), tests=tests, order=order))
            order += 1
            if tests and tests > dash.latest_test_count:
                dash.latest_test_count = tests

    if not dash.latest_test_count:
        counts = [int(x.replace(",", "")) for x in re.findall(r"(\d[\d,]{1,6})\s*tests", content, re.I)]
        dash.latest_test_count = max(counts) if counts else 0

    dash.activities = parse_recent_activity(content)
    dash.roadmap = parse_roadmap(content)
    return dash


def parse_recent_activity(content: str) -> list[ActivityEntry]:
    activities: list[ActivityEntry] = []
    in_section = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Recent Activity"):
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section and "|" in line and not stripped.startswith("|---") and not stripped.startswith("| Date"):
            parts = [clean_text(p) for p in line.split("|")[1:-1]]
            if len(parts) >= 3:
                activities.append(ActivityEntry(date=parts[0], phase=parts[1], activity=parts[2]))
    return activities


def parse_roadmap(content: str) -> list[RoadmapItem]:
    items: list[RoadmapItem] = []
    in_section = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Roadmap"):
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section and "|" in line and not stripped.startswith("|---") and not stripped.startswith("| Priority"):
            parts = [clean_text(p) for p in line.split("|")[1:-1]]
            if len(parts) >= 5:
                status_text = parts[3].lower()
                if "planned" in status_text or "active" in status_text or "next" in status_text:
                    status = "planned"
                elif "risk" in status_text or "blocked" in status_text:
                    status = "risk"
                else:
                    status = "concept"
                try:
                    priority = int(parts[0])
                except ValueError:
                    priority = 99
                items.append(RoadmapItem(priority=priority, phase=parts[1], description=parts[2], status=status, depends_on=parts[4]))
    return items


def parse_spec_file(filepath: Path, docs_root: Path) -> SpecFile:
    content = filepath.read_text(encoding="utf-8")
    title_m = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    title = clean_text(title_m.group(1)) if title_m else filepath.stem
    phase_m = re.search(r"\*\*Phase:\*\*\s*(.+)", content)
    status_m = re.search(r"\*\*Status:\*\*\s*(.+)", content)
    date_m = re.search(r"\*\*Date:\*\*\s*(.+)", content)
    spec = SpecFile(
        name=filepath.stem,
        title=title,
        phase=clean_text(phase_m.group(1)) if phase_m else "",
        status=parse_status_emoji(status_m.group(1) if status_m else ""),
        source_path=relative_path(filepath, docs_root),
        date=clean_text(date_m.group(1)) if date_m else None,
    )
    ac_rows = re.findall(r"\|\s*(AC-\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", content)
    for ac_id, gate, condition, ac_status_text in ac_rows:
        ac_status_text = clean_text(ac_status_text)
        if "✅" in ac_status_text or "pass" in ac_status_text.lower():
            ac_status = "passed"
        elif "❌" in ac_status_text or "fail" in ac_status_text.lower():
            ac_status = "failed"
        else:
            ac_status = "pending"
        spec.acceptance_criteria.append(AcceptanceCriterion(id=ac_id.strip(), gate=clean_text(gate), condition=clean_text(condition), status=ac_status))
    spec.total_ac = len(spec.acceptance_criteria)
    spec.passed_ac = sum(1 for ac in spec.acceptance_criteria if ac.status == "passed")
    spec.pending_ac = sum(1 for ac in spec.acceptance_criteria if ac.status == "pending")
    return spec



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
        weeks.append(Phase8Week(week=f"Week {week_num}", title=clean_text(title), pr=clean_text(pr), goal=goal, source_path=relative_path(filepath, docs_root), scope_summary=scope_summary))
    return weeks


def build_lane(phases: list[Phase], current_phase_text: str) -> tuple[Optional[Phase], Optional[Phase], Optional[Phase]]:
    prev_phase = None
    curr_phase = None
    next_phase = None
    current_phase_text_l = current_phase_text.lower()

    for idx, phase in enumerate(phases):
        if current_phase_text_l and phase.name.lower() in current_phase_text_l:
            curr_phase = phase
            prev_phase = phases[idx - 1] if idx > 0 else None
            next_phase = phases[idx + 1] if idx + 1 < len(phases) else None
            return prev_phase, curr_phase, next_phase

    for idx, phase in enumerate(phases):
        if phase.status == "active":
            curr_phase = phase
            prev_phase = phases[idx - 1] if idx > 0 else None
            next_phase = phases[idx + 1] if idx + 1 < len(phases) else None
            return prev_phase, curr_phase, next_phase

    pending = [p for p in phases if p.status in {"next", "pending"}]
    completed = [p for p in phases if p.status == "complete"]
    prev_phase = completed[-1] if completed else None
    curr_phase = pending[0] if pending else (phases[-1] if phases else None)
    if curr_phase and curr_phase in phases:
        idx = phases.index(curr_phase)
        next_phase = phases[idx + 1] if idx + 1 < len(phases) else None
    return prev_phase, curr_phase, next_phase


def generate_html(dash: ProjectDashboard) -> str:
    total_phases = len(dash.phases)
    complete_phases = sum(1 for p in dash.phases if p.status == "complete")
    completion_pct = round((complete_phases / total_phases) * 100) if total_phases else 0

    dash.total_ac = sum(s.total_ac for s in dash.specs)
    dash.passed_ac = sum(s.passed_ac for s in dash.specs)
    ac_pct = round((dash.passed_ac / dash.total_ac) * 100) if dash.total_ac else 0

    prev_phase, curr_phase, next_phase = build_lane(dash.phases, dash.current_phase)
    roadmap_sorted = sorted(dash.roadmap, key=lambda x: x.priority)
    next_actions = [r for r in roadmap_sorted if r.status == "planned"]
    risks = [r for r in roadmap_sorted if r.status == "risk"]
    recent_items = dash.activities[:5]
    blocked_count = sum(1 for p in dash.phases if p.status == "blocked")
    parked_count = sum(1 for p in dash.phases if p.status == "parked")

    phases_json = json.dumps([asdict(p) for p in dash.phases])
    specs_json = json.dumps([asdict(s) for s in dash.specs])
    activities_json = json.dumps([asdict(a) for a in dash.activities])
    roadmap_json = json.dumps([asdict(r) for r in dash.roadmap])
    phase8_json = json.dumps([asdict(w) for w in dash.phase8_weeks])

    project_name = dash.repo.split("/")[-1] if "/" in dash.repo else dash.repo
    updated = dash.last_updated or datetime.now().strftime("%d %B %Y")
    horizon = dash.planning_horizon or ("Next 5–7 weeks" if dash.phase8_weeks else "Active planning")
    stat_sub = f"{complete_phases} of {total_phases} phases" if total_phases else "No phases found"
    current_label = dash.current_phase or (curr_phase.name if curr_phase else "Current phase not found")
    recommended = next_actions[0] if next_actions else None

    def lane_html(tag_class: str, tag_text: str, phase: Optional[Phase], extra_class: str = "") -> str:
        title = escape(phase.name) if phase else "—"
        desc = escape(phase.description) if phase else "No phase available"
        arrow = '<div class="lane-arrow">&#9654;</div>' if phase else ''
        return f'''<div class="lane-card {extra_class}">
          <div class="lane-tag {tag_class}">{tag_text}</div>
          <div class="lane-name">{title}</div>
          <div class="lane-desc">{desc}</div>
          {arrow}
        </div>'''

    def roadmap_card(item: RoadmapItem | None, empty: str) -> str:
        if not item:
            return f'<div class="directive-card"><div class="directive-title">{escape(empty)}</div><div class="directive-body">No item available.</div></div>'
        pill = "pill-active" if item.status == "planned" else "pill-risk"
        return f'''<div class="directive-card">
          <div class="directive-head"><div class="directive-title">{escape(item.phase)}</div><span class="status-pill {pill}">{escape(item.status.upper())}</span></div>
          <div class="directive-body">{escape(item.description)}</div>
          <div class="directive-meta">Depends on: {escape(item.depends_on or '—')}</div>
        </div>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Project Dashboard — {escape(project_name)}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
:root {{
  --bg-primary: #0f1117; --bg-secondary: #1a1d27; --bg-card: #1e2130; --bg-card-hover: #252840;
  --border: #2a2d3e; --text-primary: #e8eaf0; --text-secondary: #8b8fa3; --text-muted: #5a5e72;
  --accent-teal: #2dd4bf; --accent-green: #4ade80; --accent-amber: #fbbf24; --accent-red: #f87171;
  --accent-blue: #60a5fa; --accent-purple: #a78bfa; --accent-teal-dim: rgba(45,212,191,0.15);
  --accent-green-dim: rgba(74,222,128,0.15); --accent-amber-dim: rgba(251,191,36,0.15);
  --accent-red-dim: rgba(248,113,113,0.15); --accent-blue-dim: rgba(96,165,250,0.15); --accent-purple-dim: rgba(167,139,250,0.15);
  --radius: 8px; --radius-lg: 12px;
}}
html, body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg-primary); color: var(--text-primary); line-height: 1.6; min-height: 100vh; }}
a {{ color: var(--accent-teal); text-decoration: none; }} a:hover {{ text-decoration: underline; }}
.header {{ background: linear-gradient(135deg, var(--bg-secondary) 0%, #12141e 100%); border-bottom: 1px solid var(--border); padding: 24px 32px; }}
.header-top {{ display:flex; justify-content:space-between; align-items:flex-start; gap:16px; }}
.project-title {{ font-size: 24px; font-weight: 700; }}
.project-meta {{ display:flex; gap:24px; color:var(--text-secondary); font-size:13px; flex-wrap: wrap; }}
.meta-label {{ color: var(--text-muted); }}
.dashboard {{ max-width: 1440px; margin: 0 auto; padding: 24px 32px; }}
.timeline-hero {{ background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 32px; margin-bottom: 24px; }}
.hero-title {{ font-size: 20px; font-weight: 700; margin-bottom: 20px; }}
.progress-rail {{ height: 18px; background: var(--bg-primary); border-radius: 10px; overflow: hidden; position: relative; }}
.progress-fill {{ height: 100%; background: linear-gradient(90deg, #2dd4bf 0%, #00ffaa 50%, #4ade80 100%); border-radius: 10px; }}
.progress-meta {{ display:flex; justify-content:space-between; margin-top:12px; color:var(--text-secondary); font-size:12px; gap: 12px; }}
.hero-stats {{ display:flex; justify-content:space-between; align-items:flex-end; margin-top:18px; padding-top:16px; border-top:1px solid var(--border); gap:16px; }}
.stat-number {{ font-size: 64px; font-weight: 800; line-height: 1; color: var(--accent-teal); }}
.stat-sub, .stat-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.4px; color: var(--text-secondary); }}
.summary-row {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:16px; margin-bottom:24px; }}
.summary-card {{ background: var(--bg-card); border:1px solid var(--border); border-radius:var(--radius-lg); padding:20px; text-align:center; }}
.summary-value {{ font-size:36px; font-weight:800; line-height:1.1; }}
.summary-label {{ font-size:12px; color:var(--text-secondary); text-transform:uppercase; letter-spacing:0.5px; margin-top:4px; }}
.summary-sub {{ font-size:11px; color:var(--text-muted); margin-top:4px; }}
.val-teal {{ color: var(--accent-teal); }} .val-blue {{ color: var(--accent-blue); }} .val-green {{ color: var(--accent-green); }} .val-purple {{ color: var(--accent-purple); }} .val-amber {{ color: var(--accent-amber); }}
.section {{ margin-bottom: 28px; }}
.section-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; gap:12px; flex-wrap: wrap; }}
.section-title {{ font-size:16px; font-weight:700; }}
.section-badge, .status-pill {{ font-size:11px; padding:2px 8px; border-radius:10px; font-weight:600; }}
.pill-info {{ background: var(--accent-blue-dim); color: var(--accent-blue); }} .pill-active {{ background: var(--accent-teal-dim); color: var(--accent-teal); }} .pill-risk {{ background: var(--accent-red-dim); color: var(--accent-red); }}
.phase-lane {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }}
.lane-card, .directive-card {{ background: var(--bg-card); border:1px solid var(--border); border-radius:var(--radius-lg); padding:18px; position:relative; min-height:116px; }}
.lane-current {{ border-color: var(--accent-teal); box-shadow: 0 0 0 1px rgba(45,212,191,.15) inset; }}
.lane-next {{ border-color: rgba(251,191,36,.4); }}
.lane-tag {{ display:inline-block; padding:4px 8px; border-radius:6px; font-size:10px; font-weight:800; letter-spacing:.6px; margin-bottom:12px; }}
.tag-prev {{ background: var(--accent-green-dim); color: var(--accent-green); }} .tag-curr {{ background: var(--accent-teal-dim); color: var(--accent-teal); }} .tag-next {{ background: var(--accent-amber-dim); color: var(--accent-amber); }}
.lane-name, .directive-title {{ font-size:20px; font-weight:800; line-height:1.2; margin-bottom:8px; }}
.lane-desc, .directive-body, .directive-meta {{ color:var(--text-secondary); font-size:13px; }}
.lane-arrow {{ position:absolute; right:14px; top:50%; transform:translateY(-50%); color:var(--text-muted); font-size:20px; }}
.control-grid {{ display:grid; grid-template-columns: 1.2fr 1fr 1fr; gap:16px; margin-bottom:24px; }}
.directive-head {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; margin-bottom:10px; }}
.directive-meta {{ margin-top:10px; font-size:11px; }}
.changelog-list, .timeline-track, .roadmap-list {{ display:flex; flex-direction:column; gap:8px; }}
.change-item, .phase-chip, .roadmap-item, .activity-item {{ background:var(--bg-card); border:1px solid var(--border); border-radius:var(--radius); padding:12px 16px; }}
.change-item strong {{ color: var(--accent-teal); }}
.tabs {{ display:flex; flex-wrap:wrap; gap:4px; margin-bottom:20px; border-bottom:1px solid var(--border); }}
.tab {{ padding:8px 20px; font-size:13px; font-weight:600; color:var(--text-secondary); background:none; border:none; cursor:pointer; border-bottom:2px solid transparent; margin-bottom:-1px; }}
.tab.active {{ color: var(--accent-teal); border-bottom-color: var(--accent-teal); }}
.tab-panel {{ display:none; }} .tab-panel.active {{ display:block; }}
.filter-row {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px; }}
.filter-btn {{ background: var(--bg-card); color: var(--text-secondary); border:1px solid var(--border); border-radius:999px; padding:6px 12px; cursor:pointer; font-size:12px; }}
.filter-btn.active {{ color: var(--accent-teal); border-color: var(--accent-teal); }}
.phase-chip.chip-complete {{ border-left:3px solid var(--accent-green); }} .phase-chip.chip-active {{ border-left:3px solid var(--accent-teal); }} .phase-chip.chip-next, .phase-chip.chip-pending {{ border-left:3px solid var(--accent-amber); }} .phase-chip.chip-parked {{ border-left:3px solid var(--text-muted); opacity:.8; }} .phase-chip.chip-blocked {{ border-left:3px solid var(--accent-red); }}
.chip-top {{ display:flex; justify-content:space-between; gap:10px; align-items:flex-start; }}
.chip-title {{ font-weight:700; }} .chip-desc, .activity-text, .roadmap-desc {{ color:var(--text-secondary); font-size:12px; }} .chip-tests {{ color: var(--accent-teal); font-size: 11px; margin-top: 4px; }}
.activity-feed {{ max-height:420px; overflow-y:auto; }} .activity-item {{ display:grid; grid-template-columns:90px 120px 1fr; gap:12px; align-items:start; }} .activity-date {{ color:var(--text-muted); font-size:11px; font-weight:700; }} .activity-phase {{ color:var(--accent-teal); font-weight:700; font-size:12px; }}
.roadmap-item.concept {{ opacity:0.65; border-style:dashed; }} .roadmap-item.risk {{ border-left:3px solid var(--accent-red); }}
.roadmap-top {{ display:flex; gap:12px; align-items:flex-start; }} .roadmap-priority {{ width:28px; height:28px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:700; background:var(--accent-teal-dim); color:var(--accent-teal); flex-shrink:0; }} .roadmap-item.concept .roadmap-priority {{ background:var(--accent-purple-dim); color:var(--accent-purple); }} .roadmap-item.risk .roadmap-priority {{ background:var(--accent-red-dim); color:var(--accent-red); }}
.roadmap-name {{ font-weight:700; }} .roadmap-dep {{ font-size:10px; color:var(--text-muted); margin-top:6px; }}
.spec-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(360px,1fr)); gap:16px; }}
.spec-card {{ background:var(--bg-card); border:1px solid var(--border); border-radius:var(--radius-lg); padding:20px; }} .spec-card-header {{ display:flex; justify-content:space-between; gap:12px; margin-bottom:12px; }} .spec-name {{ font-size:14px; font-weight:700; }} .spec-subtitle, .spec-meta {{ font-size:12px; color:var(--text-secondary); }}
.spec-progress-bar {{ height:8px; background:var(--bg-primary); border-radius:4px; overflow:hidden; display:flex; margin:10px 0 8px; }} .spec-progress-fill.fill-passed {{ background:var(--accent-green); }} .spec-progress-fill.fill-pending {{ background:var(--accent-amber); }} .spec-progress-label {{ display:flex; justify-content:space-between; font-size:11px; color:var(--text-muted); }}
.ac-toggle {{ margin-top:12px; width:100%; background:var(--bg-primary); color:var(--text-secondary); border:1px solid var(--border); padding:8px 10px; border-radius:8px; cursor:pointer; font-size:12px; }}
.ac-list {{ margin-top:12px; display:none; gap:8px; flex-direction:column; }} .ac-list.expanded {{ display:flex; }} .ac-item {{ display:flex; gap:10px; align-items:flex-start; font-size:12px; color:var(--text-secondary); }} .ac-dot {{ width:8px; height:8px; border-radius:50%; margin-top:6px; flex-shrink:0; }} .dot-passed {{ background: var(--accent-green); }} .dot-pending {{ background: var(--accent-amber); }} .dot-failed {{ background: var(--accent-red); }}
.week-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px; }} .week-card {{ background:var(--bg-card); border:1px solid var(--border); border-radius:var(--radius-lg); padding:20px; }} .week-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; gap:10px; }} .week-num {{ color:var(--accent-teal); font-weight:800; font-size:18px; }} .week-pr {{ background:var(--accent-amber-dim); color:var(--accent-amber); padding:4px 8px; border-radius:999px; font-size:10px; font-weight:700; }} .week-title {{ font-size:16px; font-weight:700; margin-bottom:8px; }} .week-goal {{ color:var(--accent-green); font-size:13px; margin-bottom:8px; }} .week-scope {{ color:var(--text-secondary); font-size:12px; }}
.strategic-banner {{ background: linear-gradient(90deg, rgba(45,212,191,.16), rgba(74,222,128,.10)); border:1px solid rgba(45,212,191,.5); border-radius:var(--radius); padding:12px 14px; margin-bottom:16px; color:#d7fff7; font-size:13px; }}
.empty-state {{ color:var(--text-muted); font-size:13px; padding:18px; border:1px dashed var(--border); border-radius:var(--radius); background:rgba(255,255,255,0.01); }}
.footer {{ max-width:1440px; margin:0 auto; padding:0 32px 32px; color:var(--text-muted); font-size:11px; border-top:1px solid var(--border); margin-top:40px; }}
@media (max-width: 1100px) {{ .control-grid, .phase-lane {{ grid-template-columns:1fr; }} .lane-arrow {{ display:none; }} }}
@media (max-width: 900px) {{ .activity-item {{ grid-template-columns:1fr; }} }}
@media (max-width: 768px) {{ .header {{ padding:16px; }} .dashboard {{ padding:16px; }} .summary-row {{ grid-template-columns:repeat(2,1fr); }} .spec-grid {{ grid-template-columns:1fr; }} .hero-stats {{ flex-direction:column; align-items:flex-start; }} .stat-number {{ font-size:40px; }} .footer {{ padding:0 16px 24px; }} }}
</style>
</head>
<body>
<div class="header">
  <div class="header-top">
    <div>
      <div class="project-title">{escape(project_name)}</div>
      <div class="project-meta">
        <span><span class="meta-label">Repo:</span> {escape(dash.repo)}</span>
        <span><span class="meta-label">Updated:</span> {escape(updated)}</span>
        <span><span class="meta-label">Horizon:</span> {escape(horizon)}</span>
        <span><span class="meta-label">Source:</span> <a href="{escape(dash.progress_source_path)}" target="_blank">progress file</a></span>
      </div>
    </div>
  </div>
</div>
<div class="dashboard">
  <div class="timeline-hero">
    <div class="hero-title">PROJECT TIMELINE PROGRESS</div>
    <div class="progress-rail"><div class="progress-fill" style="width:{completion_pct}%"></div></div>
    <div class="progress-meta"><span>PROJECT START</span><span>{escape(current_label)}</span><span>PROJECT END</span></div>
    <div class="hero-stats">
      <div>
        <div class="stat-number">{completion_pct}%</div>
        <div class="stat-sub">{escape(stat_sub)}</div>
      </div>
      <div>
        <div class="stat-label">Live-updating from progress file</div>
      </div>
    </div>
  </div>

  <div class="summary-row">
    <div class="summary-card"><div class="summary-value val-teal">{completion_pct}%</div><div class="summary-label">Phases Complete</div><div class="summary-sub">{escape(stat_sub)}</div></div>
    <div class="summary-card"><div class="summary-value val-blue">{ac_pct}%</div><div class="summary-label">Acceptance Criteria</div><div class="summary-sub">{dash.passed_ac} of {dash.total_ac} passing</div></div>
    <div class="summary-card"><div class="summary-value val-green">{len(dash.specs)}</div><div class="summary-label">Spec Files</div><div class="summary-sub">Parsed outside archive</div></div>
    <div class="summary-card"><div class="summary-value val-purple">{dash.latest_test_count}</div><div class="summary-label">Latest Test Count</div><div class="summary-sub">Detected from progress/spec files</div></div>
    <div class="summary-card"><div class="summary-value val-amber">{blocked_count + parked_count}</div><div class="summary-label">Watch Items</div><div class="summary-sub">{blocked_count} blocked · {parked_count} parked</div></div>
  </div>

  <div class="section"><div class="phase-lane">{lane_html("tag-prev", "COMPLETED", prev_phase)}{lane_html("tag-curr", "ACTIVE NOW", curr_phase, "lane-current")}{lane_html("tag-next", "UP NEXT", next_phase, "lane-next")}</div></div>

  <div class="section"><div class="control-grid">{roadmap_card(recommended, 'Recommended next PR')}{roadmap_card(risks[0] if risks else None, 'Risk / blocker focus')}<div class="directive-card"><div class="directive-title">Recent changes</div><div class="changelog-list">{''.join(f'<div class="change-item"><strong>{escape(a.date)}</strong> · {escape(a.phase)}<br>{escape(a.activity)}</div>' for a in recent_items) or '<div class="empty-state">No recent activity found.</div>'}</div></div></div></div>

  <div class="tabs">
    <button class="tab active" data-tab="phases">Phases</button>
    <button class="tab" data-tab="activity">Activity</button>
    <button class="tab" data-tab="roadmap">Roadmap</button>
    <button class="tab" data-tab="specs">Specs & ACs</button>
    <button class="tab" data-tab="phase8">Phase 8 Plan</button>
  </div>

  <div id="tab-phases" class="tab-panel active"><div class="section"><div class="section-header"><div class="section-title">Phase Roadmap</div><span class="section-badge pill-info">{total_phases} phases</span></div><div class="filter-row" id="phase-filters"></div><div class="timeline-track" id="phase-track"></div></div></div>
  <div id="tab-activity" class="tab-panel"><div class="section"><div class="section-header"><div class="section-title">Recent Activity</div><span class="section-badge pill-info">{len(dash.activities)} entries</span></div><div class="activity-feed" id="activity-feed"></div></div></div>
  <div id="tab-roadmap" class="tab-panel"><div class="section"><div class="section-header"><div class="section-title">Roadmap & Future Phases</div><span class="section-badge pill-info">{len(dash.roadmap)} items</span></div><div class="roadmap-list" id="roadmap-list"></div></div></div>
  <div id="tab-specs" class="tab-panel"><div class="section"><div class="section-header"><div class="section-title">Spec Files & Acceptance Criteria</div><span class="section-badge pill-info">{dash.total_ac} ACs</span></div><div class="filter-row" id="spec-filters"></div><div class="spec-grid" id="spec-grid"></div></div></div>
  <div id="tab-phase8" class="tab-panel"><div class="section"><div class="section-header"><div class="section-title">Phase 8 — Charts + Reflective Intelligence</div><span class="section-badge pill-info">{len(dash.phase8_weeks)} weeks planned</span></div><div class="strategic-banner"><strong>Strategic Direction:</strong> Live candlestick charts embedded in Run mode + rules-based reflective intelligence (aggregation only, human-governed).</div><div class="week-grid" id="week-grid"></div></div></div>
</div>
<div class="footer">Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} · Refined project dashboard generator</div>
<script>
const phases = {phases_json};
const specs = {specs_json};
const activities = {activities_json};
const roadmap = {roadmap_json};
const phase8Weeks = {phase8_json};

function esc(text) {{
  return String(text ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}}

document.querySelectorAll('.tab').forEach(btn => {{
  btn.addEventListener('click', () => {{
    const id = btn.dataset.tab;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const panel = document.getElementById('tab-' + id);
    if (panel) panel.classList.add('active');
  }});
}});

const phaseTrack = document.getElementById('phase-track');
const phaseFilters = document.getElementById('phase-filters');
let phaseFilter = 'all';
function renderPhaseFilters() {{
  const statuses = ['all', ...new Set(phases.map(p => p.status))];
  phaseFilters.innerHTML = statuses.map(s => `<button class="filter-btn ${{phaseFilter === s ? 'active' : ''}}" data-value="${{s}}">${{s}}</button>`).join('');
  phaseFilters.querySelectorAll('.filter-btn').forEach(btn => btn.addEventListener('click', () => {{ phaseFilter = btn.dataset.value; renderPhaseFilters(); renderPhases(); }}));
}}
function renderPhases() {{
  if (!phaseTrack) return;
  const items = phaseFilter === 'all' ? phases : phases.filter(p => p.status === phaseFilter);
  if (!items.length) {{ phaseTrack.innerHTML = '<div class="empty-state">No phases match this filter.</div>'; return; }}
  phaseTrack.innerHTML = items.map(p => `
    <div class="phase-chip chip-${{esc(p.status)}}">
      <div class="chip-top"><div class="chip-title">${{esc(p.name)}}</div><span class="status-pill pill-info">${{esc(p.status)}}</span></div>
      <div class="chip-desc">${{esc(p.description || '')}}</div>
      ${{p.tests ? `<div class="chip-tests">${{esc(p.tests)}} tests</div>` : ''}}
    </div>`).join('');
}}
if (phaseFilters) renderPhaseFilters();
renderPhases();

const activityFeed = document.getElementById('activity-feed');
if (activityFeed) {{
  if (activities.length) {{
    activityFeed.innerHTML = activities.map(a => `<div class="activity-item"><div class="activity-date">${{esc(a.date)}}</div><div class="activity-phase">${{esc(a.phase)}}</div><div class="activity-text">${{esc(a.activity)}}</div></div>`).join('');
  }} else {{
    activityFeed.innerHTML = '<div class="empty-state">No recent activity table found.</div>';
  }}
}}

const roadmapList = document.getElementById('roadmap-list');
if (roadmapList) {{
  if (roadmap.length) {{
    roadmapList.innerHTML = roadmap.map(r => `<div class="roadmap-item ${{esc(r.status)}}"><div class="roadmap-top"><div class="roadmap-priority">${{esc(r.priority)}}</div><div><div class="roadmap-name">${{esc(r.phase)}}</div><div class="roadmap-desc">${{esc(r.description)}}</div><div class="roadmap-dep">Depends on: ${{esc(r.depends_on || '—')}}</div></div></div></div>`).join('');
  }} else {{
    roadmapList.innerHTML = '<div class="empty-state">No roadmap table found.</div>';
  }}
}}

const specGrid = document.getElementById('spec-grid');
const specFilters = document.getElementById('spec-filters');
let specFilter = 'all';
function renderSpecFilters() {{
  const filters = ['all', 'complete', 'active', 'pending'];
  specFilters.innerHTML = filters.map(s => `<button class="filter-btn ${{specFilter === s ? 'active' : ''}}" data-value="${{s}}">${{s}}</button>`).join('');
  specFilters.querySelectorAll('.filter-btn').forEach(btn => btn.addEventListener('click', () => {{ specFilter = btn.dataset.value; renderSpecFilters(); renderSpecs(); }}));
}}
function renderSpecs() {{
  if (!specGrid) return;
  const items = specFilter === 'all' ? specs : specs.filter(s => s.status === specFilter);
  if (!items.length) {{ specGrid.innerHTML = '<div class="empty-state">No spec files match this filter.</div>'; return; }}
  specGrid.innerHTML = '';
  items.forEach(s => {{
    const passedPct = s.total_ac ? Math.round((s.passed_ac / s.total_ac) * 100) : 0;
    const pendingPct = s.total_ac ? Math.round((s.pending_ac / s.total_ac) * 100) : 0;
    const card = document.createElement('div');
    card.className = 'spec-card';
    card.innerHTML = `
      <div class="spec-card-header">
        <div>
          <div class="spec-name"><a href="${{esc(s.source_path)}}" target="_blank">${{esc(s.name)}}</a></div>
          <div class="spec-subtitle">${{esc(s.title)}}</div>
          <div class="spec-meta">${{esc(s.phase || 'No phase tag')}}${{s.date ? ' · ' + esc(s.date) : ''}}</div>
        </div>
        <span class="status-pill ${{s.status === 'complete' ? 'pill-active' : 'pill-info'}}">${{esc(s.status)}}</span>
      </div>
      <div class="spec-progress-bar"><div class="spec-progress-fill fill-passed" style="width:${{passedPct}}%"></div><div class="spec-progress-fill fill-pending" style="width:${{pendingPct}}%"></div></div>
      <div class="spec-progress-label"><span>${{s.passed_ac}} passed</span><span>${{s.pending_ac}} pending</span><span>${{s.total_ac}} total</span></div>
      <button class="ac-toggle" type="button">Show acceptance criteria</button>
      <div class="ac-list">${{(s.acceptance_criteria || []).map(ac => `<div class="ac-item"><div class="ac-dot dot-${{esc(ac.status)}}"></div><span><strong>${{esc(ac.id)}}</strong> ${{esc(ac.condition)}}</span></div>`).join('') || '<div class="empty-state">No acceptance criteria parsed.</div>'}}</div>
    `;
    const toggle = card.querySelector('.ac-toggle');
    const list = card.querySelector('.ac-list');
    toggle.addEventListener('click', () => {{ list.classList.toggle('expanded'); toggle.textContent = list.classList.contains('expanded') ? 'Hide acceptance criteria' : 'Show acceptance criteria'; }});
    specGrid.appendChild(card);
  }});
}}
if (specFilters) renderSpecFilters();
renderSpecs();

const weekGrid = document.getElementById('week-grid');
if (weekGrid) {{
  if (phase8Weeks.length) {{
    weekGrid.innerHTML = phase8Weeks.map(w => `<div class="week-card"><div class="week-header"><span class="week-num">${{esc(w.week)}}</span><span class="week-pr">${{esc(w.pr)}}</span></div><div class="week-title">${{esc(w.title)}}</div><div class="week-goal">${{esc(w.goal)}}</div><div class="week-scope">${{esc(w.scope_summary || '')}}</div><div class="spec-meta" style="margin-top:10px;"><a href="${{esc(w.source_path)}}" target="_blank">Open source roadmap</a></div></div>`).join('');
  }} else {{
    weekGrid.innerHTML = '<div class="empty-state">No Phase 8 roadmap file matching *PHASE_8*Roadmap*.md was found.</div>';
  }}
}}
</script>
</body>
</html>'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", "-f", required=True, help="Root docs folder to scan")
    parser.add_argument("--output", "-o", default="dashboard.html")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists() or not folder.is_dir():
        print(f"[ERROR] Folder not found or not a directory: {folder}")
        return 1

    progress_files = sorted([f for f in folder.rglob("*Progress*.md") if "archive" not in str(f).lower()])
    if not progress_files:
        progress_files = sorted([f for f in folder.rglob("*.md") if "progress" in f.name.lower() and "archive" not in str(f).lower()])
    if not progress_files:
        print("[ERROR] No Progress markdown file found")
        return 1

    dashboard = parse_progress_file(progress_files[0], folder)

    spec_files = sorted([f for f in folder.rglob("*SPEC*.md") if "archive" not in str(f).lower()])
    for sf in spec_files:
        try:
            dashboard.specs.append(parse_spec_file(sf, folder))
        except Exception as exc:
            print(f"[WARN] Skipping spec parse failure for {sf.name}: {exc}")

    phase8_file = next((f for f in sorted(folder.rglob("*PHASE_8*Roadmap*.md")) if "archive" not in str(f).lower()), None)
    if phase8_file:
        dashboard.phase8_weeks = parse_phase8_plan(phase8_file, folder)

    html = generate_html(dashboard)
    output_path = Path(args.output)
    output_path.write_text(html, encoding="utf-8")
    print(f"[OK] Dashboard generated: {output_path}")
    print(f"   Repo: {dashboard.repo}")
    print(f"   Phases: {len(dashboard.phases)} | Specs: {len(dashboard.specs)} | Phase8 weeks: {len(dashboard.phase8_weeks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
