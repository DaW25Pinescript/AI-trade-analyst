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

    active_phases = [p for p in dash.phases if p.status == "active"]
    next_phases = [p for p in dash.phases if p.status in ("next", "planned")]
    current_label = active_phases[0].name if active_phases else (next_phases[0].name if next_phases else "—")

    project_name = dash.project or (dash.repo.split("/")[-1] if "/" in dash.repo else dash.repo) or "Project"
    updated = str(dash.last_updated) or datetime.now().strftime("%Y-%m-%d")
    horizon = dash.planning_horizon or "Active planning"

    phases_json = json.dumps([asdict(p) for p in dash.phases])
    specs_json = json.dumps([asdict(s) for s in dash.specs])
    activities_json = json.dumps([asdict(a) for a in dash.activities])
    roadmap_json = json.dumps([asdict(r) for r in dash.roadmap])
    phase8_json = json.dumps([asdict(w) for w in dash.phase8_weeks])
    debt_json = json.dumps([asdict(d) for d in dash.debt])
    risks_json = json.dumps([asdict(r) for r in dash.risks])
    test_history_json = json.dumps([asdict(t) for t in dash.test_history])

    return f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard — {escape(project_name)}</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://unpkg.com/lucide@latest"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
<script>
  tailwind.config = {{
    darkMode: 'class',
    theme: {{
      extend: {{
        fontFamily: {{ sans: ['Inter', 'sans-serif'], display: ['Space Grotesk', 'sans-serif'] }},
        colors: {{
          gray: {{ 850: '#1f2937', 900: '#111827', 950: '#030712' }},
          accent: {{ 400: '#2dd4bf', 500: '#14b8a6' }}
        }}
      }}
    }}
  }}
</script>
<style>
  body {{ background-color: #030712; color: #f3f4f6; }}
  .glass {{ background: rgba(17, 24, 39, 0.7); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.05); }}
  .hide-scroll::-webkit-scrollbar {{ display: none; }}
  .hide-scroll {{ -ms-overflow-style: none; scrollbar-width: none; }}
  .nav-item.active {{ background: rgba(45, 212, 191, 0.1); color: #2dd4bf; border-right: 2px solid #2dd4bf; }}
  .fade-in {{ animation: fadeIn 0.3s ease-in-out; }}
  @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  .accordion-content {{ transition: max-height 0.3s ease-out, padding 0.3s ease; max-height: 0; overflow: hidden; }}
  .accordion-content.open {{ max-height: 500px; padding-top: 1rem; padding-bottom: 1rem; }}
  @media print {{
    aside, header button, #global-search {{ display: none !important; }}
    main {{ overflow: visible !important; }}
    body {{ background: white !important; color: black !important; }}
    .glass {{ background: white !important; border: 1px solid #e5e7eb !important; backdrop-filter: none !important; }}
  }}
</style>
</head>
<body class="flex h-screen overflow-hidden text-sm selection:bg-accent-500 selection:text-white">

  <aside class="w-64 flex-shrink-0 border-r border-gray-800 bg-gray-950 flex flex-col justify-between hidden md:flex z-20">
    <div>
      <div class="h-16 flex items-center px-6 border-b border-gray-800 glass">
        <i data-lucide="hexagon" class="text-accent-400 mr-3"></i>
        <h1 class="font-display font-bold text-lg tracking-tight truncate">{escape(project_name)}</h1>
      </div>
      <nav class="mt-6 px-3 space-y-1" id="sidebar-nav"></nav>
    </div>
    <div class="p-6 border-t border-gray-800 text-xs text-gray-500">
      <p>Updated: {escape(updated)}</p>
      <p class="mt-1 truncate" title="{escape(dash.repo)}">{escape(dash.repo or 'Local')}</p>
    </div>
  </aside>

  <main class="flex-1 flex flex-col h-screen overflow-hidden relative">
    <header class="h-16 glass flex items-center justify-between px-6 border-b border-gray-800 z-10 sticky top-0">
      <div class="flex items-center flex-1 max-w-md bg-gray-900/50 border border-gray-700 rounded-lg px-3 py-1.5 focus-within:border-accent-400 transition-colors">
        <i data-lucide="search" class="w-4 h-4 text-gray-400 mr-2"></i>
        <input type="text" id="global-search" placeholder="Search across dashboard (Press '/')" class="bg-transparent border-none outline-none text-gray-200 w-full placeholder-gray-500 text-sm">
      </div>
      <div class="flex items-center space-x-3 ml-4">
        <button onclick="exportCSV()" class="flex items-center px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-md transition-colors text-xs font-medium">
          <i data-lucide="download" class="w-3.5 h-3.5 mr-2"></i> Export CSV
        </button>
        <button onclick="window.print()" class="flex items-center px-3 py-1.5 bg-accent-500 hover:bg-accent-400 text-gray-950 border border-transparent rounded-md transition-colors text-xs font-medium shadow-[0_0_15px_rgba(45,212,191,0.2)]">
          <i data-lucide="printer" class="w-3.5 h-3.5 mr-2"></i> Report
        </button>
      </div>
    </header>

    <div class="flex-1 overflow-y-auto hide-scroll p-6 md:p-8 relative bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMiIgY3k9IjIiIHI9IjEiIGZpbGw9InJnYmEoMjU1LDI1NSwyNTUsMC4wMykiLz48L3N2Zz4=')]">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div class="glass rounded-xl p-5 border border-gray-800 flex items-center justify-between hover:border-gray-700 transition-colors">
          <div>
            <h3 class="text-gray-400 text-xs font-medium uppercase tracking-wider mb-1">Current Phase</h3>
            <p class="font-display text-2xl font-bold" id="widget-current-phase">{escape(current_label)}</p>
            <p class="text-xs text-gray-500 mt-2"><span id="widget-phase-count">{complete_phases}/{total_phases}</span> phases completed</p>
          </div>
          <div class="relative w-16 h-16 flex items-center justify-center">
            <svg class="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
              <path class="text-gray-800" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" stroke-width="3" stroke-dasharray="100, 100" />
              <path class="text-accent-400" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" stroke-width="3" stroke-dasharray="{completion_pct}, 100" />
            </svg>
            <span class="absolute text-xs font-bold">{completion_pct}%</span>
          </div>
        </div>

        <div class="glass rounded-xl p-5 border border-gray-800 flex flex-col justify-center hover:border-gray-700 transition-colors">
          <h3 class="text-gray-400 text-xs font-medium uppercase tracking-wider mb-1 flex items-center"><i data-lucide="milestone" class="w-3.5 h-3.5 mr-1.5"></i> Next Milestone</h3>
          <p class="font-display text-lg font-bold truncate mt-1" id="widget-next-milestone">Loading...</p>
          <p class="text-xs text-gray-500 mt-2"><span id="widget-horizon">{escape(horizon)}</span> Horizon</p>
        </div>

        <div class="glass rounded-xl p-5 border border-gray-800 flex items-center justify-between hover:border-gray-700 transition-colors">
          <div>
            <h3 class="text-gray-400 text-xs font-medium uppercase tracking-wider mb-1 flex items-center"><i data-lucide="activity" class="w-3.5 h-3.5 mr-1.5"></i> Health Score</h3>
            <p class="font-display text-3xl font-bold mt-1" id="widget-health-score">0</p>
            <p class="text-xs text-gray-500 mt-1"><span id="widget-health-status">Calculating...</span></p>
          </div>
          <div class="w-12 h-12 rounded-full border-4 border-gray-800 flex items-center justify-center bg-gray-900 shadow-inner" id="widget-health-ring">
            <i data-lucide="heart-pulse" class="w-5 h-5 text-gray-500" id="widget-health-icon"></i>
          </div>
        </div>
      </div>

      <div id="panels-container" class="relative min-h-[500px] w-full pb-20"></div>
    </div>
  </main>

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

    let activeTab = 'phases';
    let phaseFilter = 'All';
    const TABS = [
      {{ id: 'phases', name: 'Phases', icon: 'git-merge' }},
      {{ id: 'roadmap', name: 'Roadmap', icon: 'map' }},
      {{ id: 'specs', name: 'Specs & ACs', icon: 'check-square' }},
      {{ id: 'activity', name: 'Activity Log', icon: 'activity' }},
      {{ id: 'debt', name: 'Tech Debt', icon: 'alert-triangle' }},
      {{ id: 'risks', name: 'Risks', icon: 'shield-alert' }},
      {{ id: 'tests', name: 'Test History', icon: 'bar-chart-2' }},
      {{ id: 'phase8', name: 'Phase 8 Plan', icon: 'calendar' }}
    ];

    function renderSidebar() {{
      const nav = document.getElementById('sidebar-nav');
      nav.innerHTML = TABS.map(tab => `
        <a href="#" onclick="switchTab('${{tab.id}}'); return false;" id="nav-${{tab.id}}" class="nav-item group flex items-center px-4 py-2 text-sm font-medium rounded-md text-gray-400 hover:text-white hover:bg-gray-800 transition-colors mb-1 ${{activeTab === tab.id ? 'active' : ''}}">
          <i data-lucide="${{tab.icon}}" class="mr-3 w-4 h-4 text-gray-500 group-hover:text-gray-300 transition-colors ${{activeTab === tab.id ? 'text-accent-400' : ''}}"></i>
          ${{tab.name}}
        </a>
      `).join('');
      lucide.createIcons();
    }}

    function switchTab(tabId) {{
      activeTab = tabId;
      renderSidebar();
      renderPanel();
    }}

    function getStatusColor(status) {{
      const s = String(status || '').toLowerCase();
      if (['complete', 'passed', 'resolved'].includes(s)) return 'text-emerald-400 bg-emerald-400/10 border-emerald-500/20';
      if (['active', 'current'].includes(s)) return 'text-accent-400 bg-accent-400/10 border-accent-500/20';
      if (['next', 'planned', 'pending', 'maintenance', 'open'].includes(s)) return 'text-amber-400 bg-amber-400/10 border-amber-500/20';
      if (['blocked', 'failed', 'critical'].includes(s)) return 'text-red-400 bg-red-400/10 border-red-500/20';
      if (['concept', 'parked', 'low'].includes(s)) return 'text-purple-400 bg-purple-400/10 border-purple-500/20';
      return 'text-gray-400 bg-gray-800 border-gray-700';
    }}

    function lower(val) {{
      return String(val || '').toLowerCase();
    }}

    function titleEscape(val) {{
      return String(val ?? '').replace(/"/g, '&quot;');
    }}

    function matchesSearch(item, keys, searchTerm) {{
      if (!searchTerm) return true;
      return keys.some(k => lower(item[k]).includes(searchTerm));
    }}

    function renderPanel() {{
      const container = document.getElementById('panels-container');
      container.innerHTML = `<div class="fade-in pb-12" id="panel-${{activeTab}}"></div>`;
      const panel = document.getElementById(`panel-${{activeTab}}`);
      const searchTerm = lower(document.getElementById('global-search').value);

      if (activeTab === 'phases') {{
        const statuses = ['All', 'Complete', 'Active', 'Planned', 'Concept', 'Blocked'];
        let html = `<div class="flex items-center space-x-2 mb-6 overflow-x-auto hide-scroll pb-2">`;
        statuses.forEach(s => {{
          html += `<button onclick="setPhaseFilter('${{s}}')" class="px-3 py-1 text-xs font-medium rounded-full border transition-colors ${{phaseFilter === s ? 'border-accent-400 text-accent-400 bg-accent-400/10' : 'border-gray-700 hover:border-gray-500 text-gray-300'}}">${{s}}</button>`;
        }});
        html += `</div><div class="space-y-3">`;

        const filtered = D.phases.filter(p => {{
          const textMatch = lower(p.name).includes(searchTerm) || lower(p.description).includes(searchTerm);
          const statusMatch = phaseFilter === 'All' || lower(p.status) === lower(phaseFilter);
          return textMatch && statusMatch;
        }});
        if (!filtered.length) html += emptyState('No phases found matching your search.');

        filtered.forEach((p, i) => {{
          const colorClass = getStatusColor(p.status);
          const linkedSpecs = D.specs.filter(s => lower(s.phase).includes(lower(p.name)) || lower(s.name).includes(lower(p.name)));
          html += `
            <div class="glass border border-gray-800 rounded-lg overflow-hidden transition-all duration-300 searchable-item">
              <button class="w-full flex items-center justify-between p-4 hover:bg-gray-800/50 transition-colors text-left" onclick="toggleAccordion('phase-${{i}}')">
                <div class="flex items-center space-x-4">
                  <div class="flex-shrink-0 w-2 h-8 rounded-sm ${{colorClass.split(' ')[1].replace('/10', '')}}"></div>
                  <div>
                    <h4 class="font-display font-medium text-gray-100">${{p.name}}</h4>
                    <p class="text-xs text-gray-400 mt-0.5 line-clamp-1">${{p.description || '—'}}</p>
                  </div>
                </div>
                <div class="flex items-center space-x-4 ml-4">
                  ${{p.tests ? `<span class="text-xs text-gray-500 flex items-center"><i data-lucide="beaker" class="w-3 h-3 mr-1"></i> ${{Number(p.tests).toLocaleString()}} tests</span>` : ''}}
                  <span class="px-2.5 py-1 rounded-md text-[10px] font-bold tracking-wider uppercase border ${{colorClass}}">${{p.status}}</span>
                  <i data-lucide="chevron-down" class="w-4 h-4 text-gray-500 transform transition-transform" id="icon-phase-${{i}}"></i>
                </div>
              </button>
              <div id="phase-${{i}}" class="accordion-content bg-gray-900/30 px-4 text-sm text-gray-300 border-t border-transparent">
                 <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pb-4">
                   <div class="p-4 bg-gray-800/50 rounded-lg border border-gray-700/50">
                     <p class="text-xs text-gray-500 uppercase font-semibold tracking-wider mb-2">Specs linked to phase</p>
                     <p class="text-gray-300">${{linkedSpecs.length ? linkedSpecs.map(s => `&bull; ${{s.name}}`).join('<br>') : 'None specifically linked.'}}</p>
                   </div>
                   <div class="p-4 bg-gray-800/50 rounded-lg border border-gray-700/50">
                     <p class="text-xs text-gray-500 uppercase font-semibold tracking-wider mb-2">Summary</p>
                     <p class="text-gray-300">Status: <span class="capitalize">${{p.status}}</span>${{p.tests ? ` · Tests: ${{Number(p.tests).toLocaleString()}}` : ''}}</p>
                   </div>
                 </div>
              </div>
            </div>`;
        }});
        html += `</div>`;
        panel.innerHTML = html;
      }}

      else if (activeTab === 'tests') {{
        panel.innerHTML = `
          <div class="glass border border-gray-800 rounded-xl p-6 mb-6">
            <div class="flex justify-between items-center mb-6">
              <h2 class="font-display font-semibold text-lg flex items-center"><i data-lucide="trending-up" class="w-5 h-5 mr-2 text-accent-400"></i>Test Count Over Time</h2>
            </div>
            <div class="h-64 w-full"><canvas id="testHistoryChart"></canvas></div>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="glass border border-gray-800 rounded-xl p-6">
              <h3 class="text-gray-400 text-xs font-semibold uppercase tracking-wider mb-4">Phase Test Counts</h3>
              <div class="space-y-3">
                ${{D.testHistory.slice().reverse().slice(0, 10).map(t => `<div class="flex justify-between items-center text-sm border-b border-gray-800 pb-2 last:border-0"><span class="text-gray-300 truncate pr-4">${{t.phase}}</span><span class="font-mono text-accent-400">${{Number(t.count || 0).toLocaleString()}}</span></div>`).join('')}}
              </div>
            </div>
          </div>`;

        setTimeout(() => {{
          const chartEl = document.getElementById('testHistoryChart');
          if (!chartEl || !D.testHistory.length) return;
          const ctx = chartEl.getContext('2d');
          new Chart(ctx, {{
            type: 'line',
            data: {{
              labels: D.testHistory.map(t => t.phase.length > 15 ? t.phase.substring(0, 12) + '...' : t.phase),
              datasets: [{{
                label: 'Test Count',
                data: D.testHistory.map(t => t.count),
                borderColor: '#2dd4bf',
                backgroundColor: 'rgba(45, 212, 191, 0.1)',
                borderWidth: 2,
                pointBackgroundColor: '#111827',
                pointBorderColor: '#2dd4bf',
                pointHoverBackgroundColor: '#2dd4bf',
                fill: true,
                tension: 0.3
              }}]
            }},
            options: {{
              responsive: true,
              maintainAspectRatio: false,
              plugins: {{ legend: {{ display: false }} }},
              scales: {{
                y: {{ beginAtZero: true, grid: {{ color: 'rgba(255,255,255,0.05)' }}, ticks: {{ color: '#6b7280' }} }},
                x: {{ grid: {{ display: false }}, ticks: {{ color: '#6b7280', maxRotation: 45, minRotation: 45 }} }}
              }}
            }}
          }});
        }}, 100);
      }}

      else if (activeTab === 'specs') {{
        const filtered = D.specs.filter(s => lower(s.name).includes(searchTerm) || lower(s.title).includes(searchTerm) || lower(s.phase).includes(searchTerm));
        if (!filtered.length) {{
          panel.innerHTML = emptyState('No specifications match this search.');
        }} else {{
          let html = `<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">`;
          filtered.forEach(s => {{
            const pp = s.total_ac ? Math.round((s.passed_ac / s.total_ac) * 100) : 0;
            const pn = s.total_ac ? Math.round((s.pending_ac / s.total_ac) * 100) : 0;
            const statusClass = getStatusColor(s.status);
            html += `
              <div class="glass border border-gray-800 rounded-xl p-5 flex flex-col hover:border-gray-700 transition-colors searchable-item">
                <div class="flex justify-between items-start mb-3 gap-3">
                  <h4 class="font-display font-medium text-gray-100 truncate pr-2"><a href="${{s.source_path || '#'}}" class="hover:text-accent-400 hover:underline transition-colors" title="${{titleEscape(s.name)}}">${{s.name}}</a></h4>
                  <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase border whitespace-nowrap ${{statusClass}}">${{s.status}}</span>
                </div>
                <p class="text-xs text-gray-400 line-clamp-2 mb-2" title="${{titleEscape(s.title)}}">${{s.title || '—'}}</p>
                <p class="text-[11px] text-gray-500 mb-4">Phase: ${{s.phase || '—'}}</p>
                <div class="w-full bg-gray-800 rounded-full h-1.5 mb-2 overflow-hidden flex">
                  <div class="bg-emerald-500 h-1.5 rounded-l-full" style="width: ${{pp}}%"></div>
                  <div class="bg-amber-500 h-1.5" style="width: ${{pn}}%"></div>
                </div>
                <div class="flex justify-between text-[10px] text-gray-500 font-medium">
                  <span class="text-emerald-500">${{s.passed_ac}} passed</span>
                  <span class="text-amber-500">${{s.pending_ac}} pending</span>
                  <span>${{s.total_ac}} total</span>
                </div>
              </div>`;
          }});
          html += `</div>`;
          panel.innerHTML = html;
        }}
      }}

      else if (activeTab === 'roadmap') {{
        const filtered = D.roadmap.filter(r => lower(r.phase).includes(searchTerm) || lower(r.description).includes(searchTerm) || lower(r.depends_on).includes(searchTerm));
        let html = `<div class="space-y-4">`;
        if (!filtered.length) html += emptyState('No roadmap items match this search.');
        filtered.forEach(r => {{
          const colorClass = getStatusColor(r.status);
          html += `
            <div class="glass border border-gray-800 rounded-xl p-5 flex items-start space-x-4 searchable-item">
              <div class="w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs flex-shrink-0 ${{colorClass.replace('/10', '/20')}}">${{r.priority ?? '—'}}</div>
              <div class="flex-1 min-w-0">
                <div class="flex justify-between items-center mb-1 gap-3">
                  <h4 class="font-display font-medium text-gray-100">${{r.phase}}</h4>
                  <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${{colorClass}}">${{r.status}}</span>
                </div>
                <p class="text-sm text-gray-400 mb-2">${{r.description}}</p>
                <p class="text-xs text-gray-500 flex items-center"><i data-lucide="git-commit" class="w-3 h-3 mr-1"></i> Depends on: ${{r.depends_on || '—'}}</p>
              </div>
            </div>`;
        }});
        html += `</div>`;
        panel.innerHTML = html;
      }}

      else {{
        const dataArr = D[activeTab] || D.activities;
        if (!dataArr || !dataArr.length) {{
          panel.innerHTML = emptyState(`No entries found for ${{activeTab}}.`);
        }} else {{
          let renderedRows = 0;
          let html = `<div class="glass border border-gray-800 rounded-xl overflow-hidden overflow-x-auto"><table class="w-full text-left border-collapse">`;
          const keys = Object.keys(dataArr[0]);
          html += `<thead class="bg-gray-800/50 border-b border-gray-700"><tr>${{keys.map(k => `<th class="p-4 text-xs font-semibold text-gray-400 uppercase tracking-wider whitespace-nowrap">${{k.replaceAll('_', ' ')}}</th>`).join('')}}</tr></thead><tbody class="divide-y divide-gray-800/50 text-sm">`;
          dataArr.forEach(item => {{
            if (!matchesSearch(item, keys, searchTerm)) return;
            renderedRows += 1;
            html += `<tr class="hover:bg-gray-800/30 transition-colors">`;
            keys.forEach(k => {{
              let val = item[k];
              if (k === 'status' || k === 'severity') {{
                const c = getStatusColor(val);
                val = `<span class="px-2 py-1 rounded-md text-[10px] font-bold uppercase border ${{c}}">${{val}}</span>`;
              }} else {{
                val = (val === null || val === undefined || val === '') ? '—' : String(val);
              }}
              html += `<td class="p-4 text-gray-300 max-w-xs truncate" title="${{titleEscape(item[k])}}">${{val}}</td>`;
            }});
            html += `</tr>`;
          }});
          html += `</tbody></table></div>`;
          panel.innerHTML = renderedRows ? html : emptyState(`No entries found for ${{activeTab}}.`);
        }}
      }}

      lucide.createIcons();
    }}

    function toggleAccordion(id) {{
      const content = document.getElementById(id);
      const icon = document.getElementById('icon-' + id);
      if (!content || !icon) return;
      if (content.classList.contains('open')) {{
        content.classList.remove('open');
        icon.classList.remove('rotate-180');
        content.style.borderColor = 'transparent';
      }} else {{
        content.classList.add('open');
        icon.classList.add('rotate-180');
        content.style.borderColor = 'rgba(255,255,255,0.05)';
      }}
    }}

    function emptyState(msg) {{
      return `
        <div class="glass border-dashed border-2 border-gray-800 rounded-xl p-12 flex flex-col items-center justify-center text-center">
          <div class="w-12 h-12 rounded-full bg-gray-800/50 flex items-center justify-center mb-4">
            <i data-lucide="search-x" class="w-6 h-6 text-gray-500"></i>
          </div>
          <h3 class="font-medium text-gray-300 mb-1">Nothing found</h3>
          <p class="text-sm text-gray-500">${{msg}}</p>
        </div>`;
    }}

    function calcWidgets() {{
      const nextPlanned = D.roadmap.find(r => r.status === 'planned' || r.status === 'next');
      document.getElementById('widget-next-milestone').innerText = nextPlanned ? nextPlanned.phase : 'No upcoming milestones';

      const passedAC = D.specs.reduce((acc, s) => acc + (Number(s.passed_ac) || 0), 0);
      const totalAC = D.specs.reduce((acc, s) => acc + (Number(s.total_ac) || 0), 0);
      let score = totalAC > 0 ? (passedAC / totalAC) * 100 : 100;

      const openDebt = D.debt.filter(d => lower(d.status) === 'open').length;
      const riskCount = D.risks.length;
      score -= (openDebt * 2) + (riskCount * 5);
      score = Math.max(0, Math.min(100, Math.round(score)));

      const scoreEl = document.getElementById('widget-health-score');
      const statusEl = document.getElementById('widget-health-status');
      const ringEl = document.getElementById('widget-health-ring');
      const iconEl = document.getElementById('widget-health-icon');

      let animateScore = 0;
      const interval = setInterval(() => {{
        animateScore += 3;
        if (animateScore >= score) {{
          animateScore = score;
          clearInterval(interval);
        }}
        scoreEl.innerText = animateScore;
      }}, 20);

      if (score >= 85) {{
        statusEl.innerText = 'System Healthy';
        statusEl.className = 'text-xs text-emerald-500 font-medium mt-1';
        ringEl.className = 'w-12 h-12 rounded-full border-4 border-emerald-500/20 flex items-center justify-center bg-emerald-500/10 shadow-inner';
        iconEl.className = 'w-5 h-5 text-emerald-400';
      }} else if (score >= 60) {{
        statusEl.innerText = 'Needs Attention';
        statusEl.className = 'text-xs text-amber-500 font-medium mt-1';
        ringEl.className = 'w-12 h-12 rounded-full border-4 border-amber-500/20 flex items-center justify-center bg-amber-500/10 shadow-inner';
        iconEl.className = 'w-5 h-5 text-amber-400';
      }} else {{
        statusEl.innerText = 'At Risk';
        statusEl.className = 'text-xs text-red-500 font-medium mt-1';
        ringEl.className = 'w-12 h-12 rounded-full border-4 border-red-500/20 flex items-center justify-center bg-red-500/10 shadow-inner';
        iconEl.className = 'w-5 h-5 text-red-400';
      }}
    }}

    function exportCSV() {{
      const dataArr = D[activeTab] || D.activities;
      if (!dataArr || !dataArr.length) return alert('No data to export.');
      const keys = Object.keys(dataArr[0]);
      let csvContent = 'data:text/csv;charset=utf-8,' + keys.join(',') + '\n';
      dataArr.forEach(item => {{
        const row = keys.map(k => `"${{String(item[k] ?? '').replace(/"/g, '""')}}"`).join(',');
        csvContent += row + '\n';
      }});
      const encodedUri = encodeURI(csvContent);
      const link = document.createElement('a');
      link.setAttribute('href', encodedUri);
      link.setAttribute('download', `ai_trade_analyst_${{activeTab}}_export.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }}

    function setPhaseFilter(value) {{
      phaseFilter = value;
      renderPanel();
    }}

    document.getElementById('global-search').addEventListener('keyup', renderPanel);
    document.addEventListener('keydown', e => {{
      if (e.key === '/' && document.activeElement !== document.getElementById('global-search')) {{
        e.preventDefault();
        document.getElementById('global-search').focus();
      }}
    }});

    renderSidebar();
    calcWidgets();
    switchTab('phases');
  </script>
</body>
</html>"""


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
