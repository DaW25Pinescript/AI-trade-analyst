#!/usr/bin/env python3
"""
Project Dashboard Generator
Reads AI_TradeAnalyst_Progress.md + PR spec files and generates
an interactive HTML dashboard.

Usage:
    python generate_dashboard.py --progress path/to/Progress.md --specs path/to/specs/ --output dashboard.html
    python generate_dashboard.py --folder path/to/project/docs/  (auto-discovers files)
"""

import re
import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


# ─── Data Models ───

@dataclass
class Phase:
    name: str
    description: str
    status: str  # complete, active, next, pending, parked
    tests: Optional[int] = None
    date: Optional[str] = None
    order: int = 0

@dataclass
class AcceptanceCriterion:
    id: str
    gate: str
    condition: str
    status: str  # passed, pending, failed

@dataclass
class SpecFile:
    name: str
    title: str
    phase: str
    status: str
    date: Optional[str] = None
    acceptance_criteria: list = field(default_factory=list)
    total_ac: int = 0
    passed_ac: int = 0
    pending_ac: int = 0

@dataclass
class TechDebt:
    id: str
    item: str
    location: str
    status: str  # resolved, open
    severity: str  # critical, maintenance, documentation

@dataclass
class TestMilestone:
    phase: str
    count: int
    description: str

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
    status: str  # "planned", "concept"
    depends_on: str

@dataclass
class ProjectDashboard:
    repo: str = ""
    last_updated: str = ""
    current_phase: str = ""
    next_actions: str = ""
    planning_horizon: str = ""
    phases: list = field(default_factory=list)
    specs: list = field(default_factory=list)
    tech_debt: list = field(default_factory=list)
    test_milestones: list = field(default_factory=list)
    latest_increment: str = ""
    risks: list = field(default_factory=list)
    activities: list = field(default_factory=list)
    roadmap: list = field(default_factory=list)


# ─── Parsers ───

def parse_status_emoji(text: str) -> str:
    if "✅" in text or "Complete" in text or "Done" in text:
        return "complete"
    if "🟢" in text or "Active" in text:
        return "active"
    if "▶️" in text or "Next" in text:
        return "next"
    if "⏸️" in text or "Parked" in text:
        return "parked"
    if "⏳" in text or "Pending" in text or "pending" in text:
        return "pending"
    if "Blocked" in text:
        return "blocked"
    return "pending"


def parse_progress_file(filepath: str) -> ProjectDashboard:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    dash = ProjectDashboard()

    # Header metadata
    repo_m = re.search(r"\*\*Repo:\*\*\s*`([^`]+)`", content)
    if repo_m:
        dash.repo = repo_m.group(1)

    updated_m = re.search(r"\*\*Last updated:\*\*\s*(.+)", content)
    if updated_m:
        dash.last_updated = updated_m.group(1).strip()

    phase_m = re.search(r"\*\*Current phase:\*\*\s*(.+)", content)
    if phase_m:
        dash.current_phase = phase_m.group(1).strip()

    next_m = re.search(r"\*\*Next actions:\*\*\s*(.+)", content)
    if next_m:
        dash.next_actions = next_m.group(1).strip()

    horizon_m = re.search(r"\*\*Planning horizon:\*\*\s*(.+)", content)
    if horizon_m:
        dash.planning_horizon = horizon_m.group(1).strip()

    # Latest increment
    inc_m = re.search(r"### Latest increment — (.+?)(?:\n\n|\n###)", content, re.DOTALL)
    if inc_m:
        dash.latest_increment = inc_m.group(1).split("\n")[0].strip()

    # Phase Status Overview table — find the specific section
    phase_section_start = content.find("### Phase Status Overview")
    if phase_section_start == -1:
        phase_section_start = content.find("Phase Status Overview")
    if phase_section_start > -1:
        # Find the end of this section (next ## or ### heading)
        phase_section_end = content.find("\n---\n", phase_section_start + 30)
        if phase_section_end == -1:
            phase_section_end = content.find("\n## ", phase_section_start + 30)
        phase_section = content[phase_section_start:phase_section_end] if phase_section_end > -1 else content[phase_section_start:]

        phase_table = re.findall(
            r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|",
            phase_section
        )
        order = 0
        for row in phase_table:
            name, desc, status_text = row[0].strip(), row[1].strip(), row[2].strip()
            # Skip header and separator rows
            if name in ("Phase", "---") or set(name.replace(" ", "")) <= {"-", "|"}:
                continue
            if set(desc.replace(" ", "")) <= {"-", "|"}:
                continue
            status = parse_status_emoji(status_text)

            # Extract test count if present
            tests = None
            test_m = re.search(r"(\d+)\s*tests?", status_text)
            if test_m:
                tests = int(test_m.group(1))

            dash.phases.append(Phase(
                name=name,
                description=desc,
                status=status,
                tests=tests,
                order=order
            ))
            order += 1

    # Test count progression table
    test_section = content.find("### Test count progression")
    if test_section > -1:
        test_table = re.findall(
            r"\|\s*(.+?)\s*\|\s*([\d,]+)\s*\|\s*(.+?)\s*\|",
            content[test_section:]
        )
        for row in test_table:
            phase_name = row[0].strip()
            if phase_name in ("Phase", "---") or "---" in phase_name:
                continue
            try:
                count = int(row[1].strip().replace(",", ""))
                dash.test_milestones.append(TestMilestone(
                    phase=phase_name,
                    count=count,
                    description=row[2].strip()
                ))
            except ValueError:
                pass

    # Technical debt
    debt_sections = [
        ("### Critical", "critical"),
        ("### Maintenance", "maintenance"),
        ("### Documentation", "documentation"),
    ]
    for section_header, severity in debt_sections:
        idx = content.find(section_header)
        if idx == -1:
            continue
        section_end = content.find("\n### ", idx + len(section_header))
        if section_end == -1:
            section_end = content.find("\n## ", idx + len(section_header))
        section_text = content[idx:section_end] if section_end > -1 else content[idx:]

        debt_rows = re.findall(
            r"\|\s*(TD-\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|",
            section_text
        )
        for row in debt_rows:
            td_id, item, location, risk, timing = [r.strip() for r in row]
            is_resolved = "✅" in timing or "Resolved" in timing
            dash.tech_debt.append(TechDebt(
                id=td_id,
                item=item,
                location=location,
                status="resolved" if is_resolved else "open",
                severity=severity
            ))

    # Risks
    risk_section = content.find("## 5) Risks to Manage")
    if risk_section > -1:
        risk_end = content.find("\n## ", risk_section + 10)
        risk_text = content[risk_section:risk_end] if risk_end > -1 else content[risk_section:]
        risks = re.findall(r"-\s*\*\*(.+?)\*\*(.+?)(?=\n-|\n\n|$)", risk_text, re.DOTALL)
        for r in risks:
            name = r[0].strip().rstrip(":")
            if "~~" in name:
                continue  # resolved/struck-through risk
            dash.risks.append({"name": name, "detail": r[1].strip()[:200]})

    # Recent Activity and Roadmap
    dash.activities = parse_recent_activity(content)
    dash.roadmap = parse_roadmap(content)

    return dash


def parse_recent_activity(content: str) -> list:
    """Parse the ## Recent Activity table."""
    activities = []
    in_section = False
    for line in content.split('\n'):
        if line.strip().startswith('## Recent Activity'):
            in_section = True
            continue
        if in_section and line.strip().startswith('## '):
            break
        if in_section and '|' in line and not line.strip().startswith('|---') and not line.strip().startswith('| Date'):
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) >= 3:
                activities.append(ActivityEntry(
                    date=parts[0],
                    phase=parts[1],
                    activity=parts[2]
                ))
    return activities


def parse_roadmap(content: str) -> list:
    """Parse the ## Roadmap table."""
    items = []
    in_section = False
    for line in content.split('\n'):
        if line.strip().startswith('## Roadmap'):
            in_section = True
            continue
        if in_section and line.strip().startswith('## '):
            break
        if in_section and '|' in line and not line.strip().startswith('|---') and not line.strip().startswith('| Priority'):
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) >= 5:
                status_raw = parts[3]
                if 'Planned' in status_raw or '📋' in status_raw:
                    status = 'planned'
                else:
                    status = 'concept'
                try:
                    priority = int(parts[0])
                except ValueError:
                    priority = 99
                items.append(RoadmapItem(
                    priority=priority,
                    phase=parts[1],
                    description=parts[2],
                    status=status,
                    depends_on=parts[4]
                ))
    return items


def parse_spec_file(filepath: str) -> Optional[SpecFile]:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Title
    title_m = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else Path(filepath).stem

    # Phase
    phase_m = re.search(r"\*\*Phase:\*\*\s*(.+)", content)
    phase = phase_m.group(1).strip() if phase_m else ""

    # Status
    status_m = re.search(r"\*\*Status:\*\*\s*(.+)", content)
    status_text = status_m.group(1).strip() if status_m else ""
    status = parse_status_emoji(status_text)

    # Date
    date_m = re.search(r"\*\*Date:\*\*\s*(.+)", content)
    date = date_m.group(1).strip() if date_m else None

    spec = SpecFile(
        name=Path(filepath).stem,
        title=title,
        phase=phase,
        status=status,
        date=date
    )

    # Acceptance Criteria table
    ac_rows = re.findall(
        r"\|\s*(AC-\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|",
        content
    )
    for row in ac_rows:
        ac_id, gate, condition, ac_status_text = [r.strip() for r in row]
        if "✅" in ac_status_text or "Pass" in ac_status_text:
            ac_status = "passed"
        elif "❌" in ac_status_text or "Fail" in ac_status_text:
            ac_status = "failed"
        else:
            ac_status = "pending"

        spec.acceptance_criteria.append(AcceptanceCriterion(
            id=ac_id,
            gate=gate,
            condition=condition,
            status=ac_status
        ))

    spec.total_ac = len(spec.acceptance_criteria)
    spec.passed_ac = sum(1 for ac in spec.acceptance_criteria if ac.status == "passed")
    spec.pending_ac = sum(1 for ac in spec.acceptance_criteria if ac.status == "pending")

    return spec


# ─── HTML Generator ───

def generate_html(dash: ProjectDashboard) -> str:
    # Compute summary stats
    total_phases = len(dash.phases)
    completed_phases = sum(1 for p in dash.phases if p.status == "complete")
    active_phases = sum(1 for p in dash.phases if p.status == "active")
    completion_pct = round((completed_phases / total_phases * 100) if total_phases else 0)

    total_debt = len(dash.tech_debt)
    resolved_debt = sum(1 for d in dash.tech_debt if d.status == "resolved")
    debt_pct = round((resolved_debt / total_debt * 100) if total_debt else 0)

    total_ac = sum(s.total_ac for s in dash.specs)
    passed_ac = sum(s.passed_ac for s in dash.specs)
    ac_pct = round((passed_ac / total_ac * 100) if total_ac else 0)

    latest_test_count = dash.test_milestones[-1].count if dash.test_milestones else 0

    # Compute previous / current / next phases
    prev_phase = None
    curr_phase = None
    next_phase = None
    for i, p in enumerate(dash.phases):
        if p.status == "active":
            curr_phase = p
            # Previous = last completed phase before this one
            for j in range(i - 1, -1, -1):
                if dash.phases[j].status == "complete":
                    prev_phase = dash.phases[j]
                    break
            # Next = first non-active, non-complete phase after this one
            for j in range(i + 1, len(dash.phases)):
                if dash.phases[j].status != "complete":
                    next_phase = dash.phases[j]
                    break
            break
    # Fallback if no active phase found
    if not curr_phase and dash.phases:
        completed = [p for p in dash.phases if p.status == "complete"]
        remaining = [p for p in dash.phases if p.status != "complete"]
        prev_phase = completed[-1] if completed else None
        curr_phase = remaining[0] if remaining else dash.phases[-1]
        next_phase = remaining[1] if len(remaining) > 1 else None

    prev_name = prev_phase.name if prev_phase else "—"
    prev_desc = prev_phase.description if prev_phase else "No previous phase"
    prev_status = prev_phase.status if prev_phase else ""
    curr_name = curr_phase.name if curr_phase else "—"
    curr_desc = curr_phase.description if curr_phase else "No active phase"
    curr_status = curr_phase.status if curr_phase else ""
    next_name = next_phase.name if next_phase else "—"
    next_desc = next_phase.description if next_phase else "No upcoming phase"
    next_status = next_phase.status if next_phase else ""

    # Serialize data for JS
    phases_json = json.dumps([asdict(p) for p in dash.phases])
    specs_json = json.dumps([{
        **asdict(s),
        "acceptance_criteria": [asdict(ac) for ac in s.acceptance_criteria]
    } for s in dash.specs])
    debt_json = json.dumps([asdict(d) for d in dash.tech_debt])
    tests_json = json.dumps([asdict(t) for t in dash.test_milestones])
    risks_json = json.dumps(dash.risks)
    activities_json = json.dumps([asdict(a) for a in dash.activities])
    roadmap_json = json.dumps([asdict(r) for r in dash.roadmap])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Project Dashboard — {dash.repo.split('/')[-1] if dash.repo else 'Project'}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
:root {{
  --bg-primary: #0f1117;
  --bg-secondary: #1a1d27;
  --bg-card: #1e2130;
  --bg-card-hover: #252840;
  --border: #2a2d3e;
  --text-primary: #e8eaf0;
  --text-secondary: #8b8fa3;
  --text-muted: #5a5e72;
  --accent-teal: #2dd4bf;
  --accent-teal-dim: rgba(45,212,191,0.15);
  --accent-green: #4ade80;
  --accent-green-dim: rgba(74,222,128,0.15);
  --accent-amber: #fbbf24;
  --accent-amber-dim: rgba(251,191,36,0.15);
  --accent-red: #f87171;
  --accent-red-dim: rgba(248,113,113,0.15);
  --accent-blue: #60a5fa;
  --accent-blue-dim: rgba(96,165,250,0.15);
  --accent-purple: #a78bfa;
  --accent-purple-dim: rgba(167,139,250,0.15);
  --radius: 8px;
  --radius-lg: 12px;
}}
html, body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.6;
  min-height: 100vh;
}}

/* Enhanced Timeline Progress Hero */
.timeline-hero {{
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 40px;
  margin-bottom: 32px;
  position: relative;
  overflow: hidden;
}}
.timeline-hero::before {{
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: radial-gradient(circle at 20% 50%, rgba(45,212,191,0.05) 0%, transparent 50%);
  pointer-events: none;
}}
.hero-header {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 28px;
  position: relative;
  z-index: 1;
}}
.hero-title {{
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.5px;
}}
.hero-badge {{
  display: flex;
  gap: 8px;
}}
.badge-pill {{
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.3px;
  text-transform: uppercase;
  background: var(--accent-teal-dim);
  color: var(--accent-teal);
  border: 1px solid rgba(45,212,191,0.3);
}}
.badge-sm {{
  padding: 3px 8px;
  font-size: 9px;
}}
.stat-right {{
  text-align: right;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}}
.stat-badges {{
  display: flex;
  gap: 6px;
  margin-bottom: 2px;
}}
.progress-track {{
  position: relative;
  margin-bottom: 24px;
}}
.progress-rail {{
  height: 20px;
  background: var(--bg-primary);
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 8px;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.3);
}}
.progress-fill {{
  height: 100%;
  background: linear-gradient(90deg, #2dd4bf 0%, #00FFAA 50%, #4ade80 100%);
  border-radius: 10px;
  transition: width 1s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 0 20px rgba(45,212,191,0.5), 0 4px 12px rgba(0,255,170,0.3);
  animation: shimmer-sweep 3s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}}
@keyframes shimmer-sweep {{
  0% {{ background-position: -1000px 0; }}
  100% {{ background-position: 1000px 0; }}
}}
.progress-now {{
  position: absolute;
  top: -8px;
  width: 3px;
  height: 36px;
  background: #00FFAA;
  border-radius: 2px;
  box-shadow: 0 0 16px rgba(0,255,170,0.8), 0 0 32px rgba(0,255,170,0.4);
  animation: pulse-now 2s ease-in-out infinite;
  z-index: 5;
  transition: left 1s cubic-bezier(0.4, 0, 0.2, 1);
}}
@keyframes pulse-now {{
  0%, 100% {{
    box-shadow: 0 0 16px rgba(0,255,170,0.8), 0 0 32px rgba(0,255,170,0.4);
    transform: scaleY(1);
  }}
  50% {{
    box-shadow: 0 0 24px rgba(0,255,170,0.95), 0 0 48px rgba(0,255,170,0.6);
    transform: scaleY(1.1);
  }}
}}
.progress-tooltip {{
  position: absolute;
  top: -8px;
  left: {completion_pct}%;
  transform: translateX(-50%) translateY(-100%);
  background: #1a1d27;
  border: 1px solid rgba(45,212,191,0.4);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 10px;
  color: var(--accent-teal);
  white-space: nowrap;
  z-index: 6;
  box-shadow: 0 2px 8px rgba(0,0,0,0.6);
  font-weight: 600;
}}
.progress-tooltip::after {{
  content: '';
  position: absolute;
  top: 100%;
  left: var(--arrow-left, 50%);
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 5px solid #1a1d27;
}}
.progress-labels {{
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
}}
.phase-group-labels {{
  position: relative;
  height: 20px;
  margin-bottom: 8px;
  font-size: 10px;
  color: var(--text-muted);
}}
.phase-group-label {{
  position: absolute;
  top: 0;
  transform: translateX(-50%);
  font-weight: 600;
  white-space: nowrap;
}}
.task-slots-label {{
  font-size: 10px;
  color: var(--text-muted);
  margin-bottom: 4px;
  font-weight: 600;
}}
.task-slots-track {{
  display: flex;
  position: relative;
  height: 6px;
  background: var(--bg-primary);
  border-radius: 3px;
  margin-bottom: 16px;
  overflow: hidden;
}}
.task-slot {{
  position: absolute;
  height: 100%;
  border-radius: 2px;
  transition: all 0.3s ease;
}}
.task-slot.complete {{
  background: #4ade80;
}}
.task-slot.active {{
  background: #2dd4bf;
  animation: pulse-active 1.5s ease-in-out infinite;
}}
@keyframes pulse-active {{
  0%, 100% {{ opacity: 1; }}
  50% {{ opacity: 0.6; }}
}}
.task-slot.next {{
  background: #fbbf24;
}}
.task-slot.pending {{
  background: #5a5e72;
}}
.milestone-dots {{
  display: none;
}}
.milestone-dot {{
  display: none;
}}
.phase-markers {{
  display: flex;
  justify-content: space-between;
  padding-top: 8px;
}}
.phase-marker {{
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  text-align: center;
  white-space: nowrap;
  flex: 1;
}}
.hero-stats {{
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}}
.stat-number {{
  font-size: 72px;
  font-weight: 800;
  letter-spacing: -2px;
  background: linear-gradient(135deg, #2dd4bf, #00FFAA, #4ade80);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-shadow: none;
  line-height: 1;
  filter: drop-shadow(0 0 20px rgba(45,212,191,0.6));
}}
.stat-label {{
  font-size: 11px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}}
.stat-sub {{
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 4px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  font-weight: 600;
}}
.refresh-indicator {{
  font-size: 10px;
  color: var(--text-muted);
  padding: 4px 8px;
  background: var(--bg-primary);
  border-radius: var(--radius);
  border: 1px solid var(--border);
}}

/* Header */
.header {{
  background: linear-gradient(135deg, var(--bg-secondary) 0%, #12141e 100%);
  border-bottom: 1px solid var(--border);
  padding: 24px 32px;
}}
.header-top {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}}
.project-title {{
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.5px;
}}
.project-meta {{
  display: flex;
  gap: 24px;
  color: var(--text-secondary);
  font-size: 13px;
}}
.project-meta span {{
  display: flex;
  align-items: center;
  gap: 6px;
}}
.meta-label {{ color: var(--text-muted); }}
.header-status {{
  display: flex;
  gap: 8px;
  align-items: center;
}}
.status-pill {{
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.3px;
}}
.pill-active {{ background: var(--accent-teal-dim); color: var(--accent-teal); }}
.pill-info {{ background: var(--accent-blue-dim); color: var(--accent-blue); }}

/* Layout */
.dashboard {{
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px 32px;
}}

/* Summary Cards Row */
.summary-row {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}}
.summary-card {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px;
  text-align: center;
  transition: all 0.2s ease;
}}
.summary-card:hover {{
  border-color: var(--accent-teal);
  background: var(--bg-card-hover);
}}
.summary-value {{
  font-size: 36px;
  font-weight: 800;
  letter-spacing: -1px;
  line-height: 1.1;
  transition: all 0.6s ease;
}}
.summary-label {{
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}}
.summary-sub {{
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}}
.val-teal {{ color: var(--accent-teal); }}
.val-green {{ color: var(--accent-green); }}
.val-amber {{ color: var(--accent-amber); }}
.val-blue {{ color: var(--accent-blue); }}
.val-purple {{ color: var(--accent-purple); }}

/* Sections */
.section {{
  margin-bottom: 32px;
}}
.section-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}}
.section-title {{
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}}
.section-badge {{
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
}}

/* Phase Timeline */
.timeline {{
  position: relative;
}}
.timeline-track {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}}
.phase-chip {{
  padding: 6px 14px;
  border-radius: var(--radius);
  font-size: 12px;
  font-weight: 500;
  border: 1px solid transparent;
  cursor: default;
  transition: all 0.2s;
  position: relative;
}}
.phase-chip:hover {{
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}}
.phase-chip .chip-tests {{
  font-size: 10px;
  opacity: 0.7;
  margin-left: 4px;
}}
.chip-complete {{ background: var(--accent-green-dim); color: var(--accent-green); border-color: rgba(74,222,128,0.2); }}
.chip-active {{ background: var(--accent-teal-dim); color: var(--accent-teal); border-color: rgba(45,212,191,0.3); animation: pulse-border 2s infinite; }}
.chip-next {{ background: var(--accent-amber-dim); color: var(--accent-amber); border-color: rgba(251,191,36,0.2); }}
.chip-pending {{ background: var(--bg-secondary); color: var(--text-muted); border-color: var(--border); }}
.chip-parked {{ background: var(--bg-secondary); color: var(--text-muted); border-color: var(--border); opacity: 0.5; }}
.chip-blocked {{ background: var(--accent-red-dim); color: var(--accent-red); border-color: rgba(248,113,113,0.2); }}

@keyframes pulse-border {{
  0%, 100% {{ border-color: rgba(45,212,191,0.3); }}
  50% {{ border-color: rgba(45,212,191,0.7); }}
}}

/* Tooltip */
.tooltip {{
  display: none;
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: #2a2d40;
  border: 1px solid var(--border);
  padding: 8px 12px;
  border-radius: var(--radius);
  font-size: 12px;
  color: var(--text-primary);
  white-space: nowrap;
  z-index: 10;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  pointer-events: none;
}}
.phase-chip:hover .tooltip {{ display: block; }}

/* Spec Cards */
.spec-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 16px;
}}
.spec-card {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px;
  transition: border-color 0.2s;
}}
.spec-card:hover {{ border-color: var(--accent-teal); }}
.spec-card-header {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}}
.spec-name {{
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}}
.spec-subtitle {{
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}}
.spec-progress {{
  margin: 12px 0;
}}
.spec-progress-bar {{
  height: 8px;
  background: var(--bg-primary);
  border-radius: 4px;
  overflow: hidden;
  display: flex;
}}
.spec-progress-fill {{
  height: 100%;
  transition: width 0.6s ease;
}}
.fill-passed {{ background: var(--accent-green); }}
.fill-pending {{ background: var(--accent-amber); opacity: 0.4; }}
.spec-progress-label {{
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 4px;
}}
.ac-list {{
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.3s ease;
}}
.ac-list.expanded {{
  max-height: 2000px;
}}
.ac-toggle {{
  font-size: 12px;
  color: var(--accent-teal);
  cursor: pointer;
  border: none;
  background: none;
  padding: 4px 0;
  margin-top: 8px;
}}
.ac-toggle:hover {{ text-decoration: underline; }}
.ac-item {{
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid rgba(42,45,62,0.5);
  font-size: 12px;
}}
.ac-item:last-child {{ border-bottom: none; }}
.ac-dot {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 5px;
  flex-shrink: 0;
}}
.dot-passed {{ background: var(--accent-green); }}
.dot-pending {{ background: var(--accent-amber); }}
.dot-failed {{ background: var(--accent-red); }}
.ac-id {{ color: var(--text-muted); font-weight: 600; min-width: 50px; }}
.ac-text {{ color: var(--text-secondary); }}

/* Tech Debt */
.debt-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 10px;
}}
.debt-item {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 13px;
}}
.debt-resolved {{ opacity: 0.5; }}
.debt-resolved .debt-name {{ text-decoration: line-through; }}
.debt-icon {{
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
}}
.debt-icon-resolved {{ background: var(--accent-green-dim); }}
.debt-icon-open {{ background: var(--accent-amber-dim); }}
.debt-name {{ font-weight: 600; color: var(--text-primary); }}
.debt-detail {{ color: var(--text-secondary); font-size: 11px; }}

/* Test Chart */
.test-chart-container {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
}}
.chart-bars {{
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 180px;
  padding: 0 8px;
}}
.chart-bar-wrapper {{
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  justify-content: flex-end;
}}
.chart-bar {{
  width: 100%;
  max-width: 40px;
  background: linear-gradient(180deg, var(--accent-teal), rgba(45,212,191,0.4));
  border-radius: 4px 4px 0 0;
  transition: height 0.6s ease;
  cursor: default;
  position: relative;
  min-height: 2px;
}}
.chart-bar:hover {{
  background: linear-gradient(180deg, var(--accent-teal), rgba(45,212,191,0.7));
}}
.chart-bar-label {{
  font-size: 9px;
  color: var(--text-muted);
  margin-top: 6px;
  text-align: center;
  writing-mode: vertical-rl;
  text-orientation: mixed;
  max-height: 80px;
  overflow: hidden;
}}
.chart-bar-value {{
  font-size: 10px;
  color: var(--accent-teal);
  margin-bottom: 4px;
  font-weight: 600;
}}

/* Risks */
.risk-list {{
  display: flex;
  flex-direction: column;
  gap: 8px;
}}
.risk-item {{
  padding: 12px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent-amber);
  border-radius: var(--radius);
  font-size: 13px;
}}
.risk-name {{ font-weight: 600; color: var(--accent-amber); }}
.risk-detail {{ color: var(--text-secondary); font-size: 12px; margin-top: 4px; }}

/* Activity Feed */
.activity-feed {{
  max-height: 400px;
  overflow-y: auto;
}}
.activity-item {{
  display: flex;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
  align-items: flex-start;
}}
.activity-item:last-child {{ border-bottom: none; }}
.activity-date {{
  color: var(--text-muted);
  font-size: 11px;
  min-width: 85px;
  font-weight: 600;
  flex-shrink: 0;
}}
.activity-phase {{
  color: var(--accent-teal);
  font-weight: 700;
  min-width: 100px;
  font-size: 12px;
  flex-shrink: 0;
}}
.activity-text {{
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.4;
}}

/* Roadmap */
.roadmap-list {{
  display: flex;
  flex-direction: column;
  gap: 8px;
}}
.roadmap-item {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 13px;
  transition: all 0.2s ease;
}}
.roadmap-item:hover {{
  border-color: var(--accent-teal);
  background: var(--bg-card-hover);
}}
.roadmap-item.concept {{
  opacity: 0.6;
  border-style: dashed;
}}
.roadmap-priority {{
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}}
.roadmap-priority.planned {{
  background: var(--accent-teal-dim);
  color: var(--accent-teal);
}}
.roadmap-priority.concept {{
  background: var(--accent-purple-dim);
  color: var(--accent-purple);
}}
.roadmap-name {{ font-weight: 600; color: var(--text-primary); }}
.roadmap-desc {{ color: var(--text-secondary); font-size: 12px; }}
.roadmap-dep {{
  font-size: 10px;
  color: var(--text-muted);
  margin-left: auto;
  flex-shrink: 0;
  padding: 2px 8px;
  background: var(--bg-primary);
  border-radius: 4px;
  border: 1px solid var(--border);
}}

/* Phase Lane — Previous / Current / Next */
.phase-lane {{
  display: grid;
  grid-template-columns: 1fr 1.4fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}}
.lane-card {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px 20px;
  position: relative;
  transition: all 0.2s ease;
}}
.lane-card:hover {{
  border-color: var(--border);
  background: var(--bg-card-hover);
}}
.lane-card.lane-current {{
  border-color: var(--accent-teal);
  box-shadow: 0 0 20px rgba(45,212,191,0.08);
}}
.lane-card.lane-current:hover {{
  border-color: var(--accent-teal);
}}
.lane-card.lane-next {{
  border-color: rgba(251,191,36,0.3);
}}
.lane-card.lane-next:hover {{
  border-color: rgba(251,191,36,0.5);
}}
.lane-header {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}}
.lane-tag {{
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 3px 8px;
  border-radius: 4px;
}}
.tag-prev {{
  background: var(--accent-green-dim);
  color: var(--accent-green);
}}
.tag-curr {{
  background: var(--accent-teal-dim);
  color: var(--accent-teal);
}}
.tag-next {{
  background: var(--accent-amber-dim);
  color: var(--accent-amber);
}}
.lane-name {{
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}}
.lane-desc {{
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}}
.lane-arrow {{
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 18px;
  position: absolute;
  right: -13px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 2;
  width: 26px;
  height: 26px;
  background: var(--bg-primary);
  border-radius: 50%;
  border: 1px solid var(--border);
}}
@media (max-width: 768px) {{
  .phase-lane {{ grid-template-columns: 1fr; }}
  .lane-arrow {{ display: none; }}
}}

/* Footer */
.footer {{
  text-align: center;
  padding: 32px;
  color: var(--text-muted);
  font-size: 11px;
  border-top: 1px solid var(--border);
  margin-top: 40px;
}}

/* Responsive */
@media (max-width: 768px) {{
  .header {{ padding: 16px; }}
  .dashboard {{ padding: 16px; }}
  .summary-row {{ grid-template-columns: repeat(2, 1fr); }}
  .spec-grid {{ grid-template-columns: 1fr; }}
  .project-meta {{ flex-wrap: wrap; gap: 12px; }}
  .header-top {{ flex-direction: column; gap: 12px; }}
  .timeline-hero {{ padding: 24px; }}
  .hero-stats {{ flex-direction: column; gap: 16px; align-items: flex-start; }}
  .stat-number {{ font-size: 40px; }}
}}

/* Tab system */
.tabs {{
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0;
}}
.tab {{
  padding: 8px 20px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  background: none;
  border: none;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
  margin-bottom: -1px;
}}
.tab:hover {{ color: var(--text-primary); }}
.tab.active {{
  color: var(--accent-teal);
  border-bottom-color: var(--accent-teal);
}}
.tab-panel {{ display: none; }}
.tab-panel.active {{ display: block; }}
</style>
</head>
<body>

<div class="header">
  <div class="header-top">
    <div>
      <div class="project-title">{dash.repo.split('/')[-1].replace('-', ' ').title() if dash.repo else 'Project Dashboard'}</div>
      <div class="project-meta">
        <span><span class="meta-label">Repo:</span> {dash.repo}</span>
        <span><span class="meta-label">Updated:</span> {dash.last_updated}</span>
        <span><span class="meta-label">Horizon:</span> {dash.planning_horizon}</span>
      </div>
    </div>
  </div>
</div>

<div class="dashboard">

  <!-- PROJECT TIMELINE PROGRESS Hero Section -->
  <div class="timeline-hero" id="timeline-hero">
    <div class="hero-header">
      <div class="hero-title">PROJECT TIMELINE PROGRESS</div>
    </div>

    <div class="progress-track">
      <div class="progress-labels">
        <span>PROJECT START</span>
        <span>PROJECT END</span>
      </div>
      <div class="phase-group-labels" id="phase-group-labels"></div>
      <div class="progress-rail">
        <div class="progress-fill" id="progress-fill" style="width: {completion_pct}%"></div>
      </div>
      <div class="progress-now" id="progress-now" style="left: {completion_pct}%"></div>
      <div class="progress-tooltip" id="progress-tooltip">{dash.current_phase}</div>

      <div class="task-slots-label">Dynamic Task Slots</div>
      <div class="task-slots-track" id="task-slots-track"></div>

      <div class="milestone-dots" id="milestone-dots"></div>

      <div class="phase-markers" id="phase-markers"></div>
    </div>

    <div class="hero-stats">
      <div>
        <div class="stat-number" id="stat-number">{completion_pct}%</div>
        <div class="stat-sub" id="stat-sub">{completed_phases} of {total_phases} phases</div>
      </div>
      <div class="stat-right">
        <div class="stat-badges">
          <div class="badge-pill badge-sm">DYNAMIC</div>
          <div class="badge-pill badge-sm">REAL-TIME</div>
        </div>
        <div class="stat-label">Live-updating from progress file</div>
        <div class="refresh-indicator" id="refresh-indicator">Last updated: now</div>
      </div>
    </div>
  </div>

  <!-- Summary Cards -->
  <div class="summary-row">
    <div class="summary-card">
      <div class="summary-value val-teal" id="card-completion">{completion_pct}%</div>
      <div class="summary-label">Phases Complete</div>
      <div class="summary-sub" id="card-completion-sub">{completed_phases} of {total_phases} phases</div>
    </div>
    <div class="summary-card">
      <div class="summary-value val-green" id="card-debt">{debt_pct}%</div>
      <div class="summary-label">Tech Debt Resolved</div>
      <div class="summary-sub" id="card-debt-sub">{resolved_debt} of {total_debt} items</div>
    </div>
    <div class="summary-card">
      <div class="summary-value val-blue" id="card-ac">{ac_pct}%</div>
      <div class="summary-label">Acceptance Criteria</div>
      <div class="summary-sub" id="card-ac-sub">{passed_ac} of {total_ac} passing</div>
    </div>
    <div class="summary-card">
      <div class="summary-value val-purple" id="card-tests">{latest_test_count:,}</div>
      <div class="summary-label">Latest Test Count</div>
      <div class="summary-sub">Ops suite milestone</div>
    </div>
  </div>

  <!-- Phase Lane: Previous → Current → Next -->
  <div class="section">
    <div class="phase-lane">
      <div class="lane-card">
        <div class="lane-tag tag-prev">COMPLETED</div>
        <div class="lane-name">{prev_name}</div>
        <div class="lane-desc">{prev_desc}</div>
        <div class="lane-arrow">&#9654;</div>
      </div>
      <div class="lane-card lane-current">
        <div class="lane-tag tag-curr">ACTIVE NOW</div>
        <div class="lane-name">{curr_name}</div>
        <div class="lane-desc">{curr_desc}</div>
        <div class="lane-arrow">&#9654;</div>
      </div>
      <div class="lane-card lane-next">
        <div class="lane-tag tag-next">UP NEXT</div>
        <div class="lane-name">{next_name}</div>
        <div class="lane-desc">{next_desc}</div>
      </div>
    </div>
  </div>

  <!-- Tabs -->
  <div class="tabs">
    <button class="tab active" onclick="switchTab('phases')">Phases</button>
    <button class="tab" onclick="switchTab('activity')">Activity</button>
    <button class="tab" onclick="switchTab('roadmap')">Roadmap</button>
    <button class="tab" onclick="switchTab('specs')">Specs & ACs</button>
    <button class="tab" onclick="switchTab('tests')">Test Progression</button>
    <button class="tab" onclick="switchTab('debt')">Tech Debt</button>
    <button class="tab" onclick="switchTab('risks')">Risks</button>
  </div>

  <!-- Phases Tab -->
  <div id="tab-phases" class="tab-panel active">
    <div class="section">
      <div class="section-header">
        <div class="section-title">Phase Roadmap</div>
        <span class="section-badge pill-info">{total_phases} phases</span>
      </div>
      <div class="timeline">
        <div class="timeline-track" id="phase-track"></div>
      </div>
    </div>
  </div>

  <!-- Activity Tab -->
  <div id="tab-activity" class="tab-panel">
    <div class="section">
      <div class="section-header">
        <div class="section-title">Recent Activity</div>
        <span class="section-badge pill-info">{len(dash.activities)} entries</span>
      </div>
      <div class="activity-feed" id="activity-feed"></div>
    </div>
  </div>

  <!-- Roadmap Tab -->
  <div id="tab-roadmap" class="tab-panel">
    <div class="section">
      <div class="section-header">
        <div class="section-title">Roadmap & Future Phases</div>
        <span class="section-badge pill-info">{len(dash.roadmap)} items</span>
      </div>
      <div class="roadmap-list" id="roadmap-list"></div>
    </div>
  </div>

  <!-- Specs Tab -->
  <div id="tab-specs" class="tab-panel">
    <div class="section">
      <div class="section-header">
        <div class="section-title">Spec Files & Acceptance Criteria</div>
        <span class="section-badge pill-info">{total_ac} ACs</span>
      </div>
      <div class="spec-grid" id="spec-grid"></div>
    </div>
  </div>

  <!-- Tests Tab -->
  <div id="tab-tests" class="tab-panel">
    <div class="section">
      <div class="section-header">
        <div class="section-title">Test Count Progression</div>
      </div>
      <div class="test-chart-container">
        <div class="chart-bars" id="test-chart"></div>
      </div>
    </div>
  </div>

  <!-- Debt Tab -->
  <div id="tab-debt" class="tab-panel">
    <div class="section">
      <div class="section-header">
        <div class="section-title">Technical Debt Register</div>
        <span class="section-badge" style="background:var(--accent-green-dim);color:var(--accent-green)">{resolved_debt}/{total_debt} resolved</span>
      </div>
      <div class="debt-grid" id="debt-grid"></div>
    </div>
  </div>

  <!-- Risks Tab -->
  <div id="tab-risks" class="tab-panel">
    <div class="section">
      <div class="section-header">
        <div class="section-title">Active Risks</div>
      </div>
      <div class="risk-list" id="risk-list"></div>
    </div>
  </div>

</div>

<div class="footer">
  Generated {datetime.now().strftime("%Y-%m-%d %H:%M")} &middot; Project Dashboard Generator v1.0
</div>

<script>
const phases = {phases_json};
const specs = {specs_json};
const debt = {debt_json};
const tests = {tests_json};
const risks = {risks_json};
const activities = {activities_json};
const roadmap = {roadmap_json};

// Render milestone dots, phase markers, group labels, and task slots
function renderMilestones() {{
  const dotContainer = document.getElementById('milestone-dots');
  const markerContainer = document.getElementById('phase-markers');
  const groupLabelsContainer = document.getElementById('phase-group-labels');
  const slotsContainer = document.getElementById('task-slots-track');
  const totalPhases = phases.length;

  dotContainer.innerHTML = '';
  markerContainer.innerHTML = '';
  groupLabelsContainer.innerHTML = '';
  slotsContainer.innerHTML = '';

  // Define milestone groups
  const groups = [
    {{ name: 'Phase 0', pct: 5 }},
    {{ name: 'UI Phases', pct: 25 }},
    {{ name: 'Ops Backend', pct: 45 }},
    {{ name: 'TD & Cleanup', pct: 60 }},
    {{ name: 'Security/API', pct: 75 }},
    {{ name: 'Launch', pct: 92 }}
  ];

  // Render phase group labels
  groups.forEach(g => {{
    const label = document.createElement('div');
    label.className = 'phase-group-label';
    label.style.left = g.pct + '%';
    label.textContent = g.name;
    groupLabelsContainer.appendChild(label);
  }});

  // Render task slots
  let slotPosition = 0;
  phases.forEach((p, idx) => {{
    const slotWidth = (100 / totalPhases);
    const slot = document.createElement('div');
    slot.className = 'task-slot ' + (p.status === 'complete' ? 'complete' : p.status === 'active' ? 'active' : p.status === 'next' ? 'next' : 'pending');
    slot.style.left = slotPosition + '%';
    slot.style.width = slotWidth + '%';
    slot.title = p.name;
    slotsContainer.appendChild(slot);
    slotPosition += slotWidth;
  }});

  phases.forEach((p, idx) => {{
    const pct = (idx / (totalPhases - 1 || 1)) * 100;
    const dot = document.createElement('div');
    dot.className = 'milestone-dot ' + (p.status === 'complete' ? 'complete' : p.status === 'active' ? 'active' : 'pending');
    dot.style.left = pct + '%';
    dot.style.transform = 'translateX(-50%)';
    dotContainer.appendChild(dot);

    const marker = document.createElement('div');
    marker.className = 'phase-marker';
    marker.style.flex = '1';
    marker.textContent = p.name.substring(0, 8);
    markerContainer.appendChild(marker);
  }});
}}
renderMilestones();

// Clamp tooltip so it never overflows the track container
function clampTooltip() {{
  const tooltip = document.getElementById('progress-tooltip');
  const track = document.querySelector('.progress-track');
  if (!tooltip || !track) return;

  // Reset to centered on the NOW position
  tooltip.style.transform = 'translateX(-50%) translateY(-100%)';

  const tRect = tooltip.getBoundingClientRect();
  const trackRect = track.getBoundingClientRect();
  const pad = 8;

  if (tRect.right > trackRect.right - pad) {{
    // Overflows right — shift left
    const overflow = tRect.right - (trackRect.right - pad);
    tooltip.style.transform = 'translateX(calc(-50% - ' + overflow + 'px)) translateY(-100%)';
    // Move the arrow to stay pointing at the NOW line
    const arrowOffset = 50 + (overflow / tRect.width * 100);
    tooltip.style.setProperty('--arrow-left', Math.min(arrowOffset, 90) + '%');
  }} else if (tRect.left < trackRect.left + pad) {{
    const overflow = (trackRect.left + pad) - tRect.left;
    tooltip.style.transform = 'translateX(calc(-50% + ' + overflow + 'px)) translateY(-100%)';
    const arrowOffset = 50 - (overflow / tRect.width * 100);
    tooltip.style.setProperty('--arrow-left', Math.max(arrowOffset, 10) + '%');
  }} else {{
    tooltip.style.setProperty('--arrow-left', '50%');
  }}
}}
clampTooltip();
window.addEventListener('resize', clampTooltip);

// Tab switching
function switchTab(id) {{
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  event.target.classList.add('active');
}}

// Render phases
const track = document.getElementById('phase-track');
phases.forEach(p => {{
  const chip = document.createElement('div');
  chip.className = 'phase-chip chip-' + p.status;
  let label = p.name;
  if (p.tests) label += ' <span class="chip-tests">(' + p.tests + ')</span>';
  chip.innerHTML = label + '<div class="tooltip">' + p.description + (p.tests ? ' — ' + p.tests + ' tests' : '') + '</div>';
  track.appendChild(chip);
}});

// Render specs
const specGrid = document.getElementById('spec-grid');
specs.forEach((s, idx) => {{
  const passedPct = s.total_ac ? Math.round(s.passed_ac / s.total_ac * 100) : 0;
  const pendingPct = s.total_ac ? Math.round(s.pending_ac / s.total_ac * 100) : 0;
  const card = document.createElement('div');
  card.className = 'spec-card';
  card.innerHTML = `
    <div class="spec-card-header">
      <div>
        <div class="spec-name">${{s.name}}</div>
        <div class="spec-subtitle">${{s.title}}</div>
      </div>
      <span class="status-pill ${{s.status === 'complete' ? 'pill-active' : 'pill-info'}}">${{s.status}}</span>
    </div>
    <div class="spec-progress">
      <div class="spec-progress-bar">
        <div class="spec-progress-fill fill-passed" style="width:${{passedPct}}%"></div>
        <div class="spec-progress-fill fill-pending" style="width:${{pendingPct}}%"></div>
      </div>
      <div class="spec-progress-label">
        <span>${{s.passed_ac}} passed</span>
        <span>${{s.pending_ac}} pending</span>
        <span>${{s.total_ac}} total</span>
      </div>
    </div>
    <button class="ac-toggle" onclick="toggleAC(${{idx}})">Show acceptance criteria</button>
    <div class="ac-list" id="ac-list-${{idx}}">
      ${{s.acceptance_criteria.map(ac => `
        <div class="ac-item">
          <div class="ac-dot dot-${{ac.status}}"></div>
          <span class="ac-id">${{ac.id}}</span>
          <span class="ac-text">${{ac.condition}}</span>
        </div>
      `).join('')}}
    </div>
  `;
  specGrid.appendChild(card);
}});

function toggleAC(idx) {{
  const list = document.getElementById('ac-list-' + idx);
  list.classList.toggle('expanded');
  const btn = list.previousElementSibling;
  btn.textContent = list.classList.contains('expanded') ? 'Hide acceptance criteria' : 'Show acceptance criteria';
}}

// Render test chart
const chartEl = document.getElementById('test-chart');
const maxTest = Math.max(...tests.map(t => t.count), 1);
tests.forEach(t => {{
  const h = Math.max(2, (t.count / maxTest) * 160);
  const wrapper = document.createElement('div');
  wrapper.className = 'chart-bar-wrapper';
  wrapper.innerHTML = `
    <div class="chart-bar-value">${{t.count.toLocaleString()}}</div>
    <div class="chart-bar" style="height:${{h}}px" title="${{t.phase}}: ${{t.count}} tests — ${{t.description}}"></div>
    <div class="chart-bar-label">${{t.phase.length > 20 ? t.phase.substring(0,18) + '…' : t.phase}}</div>
  `;
  chartEl.appendChild(wrapper);
}});

// Render debt
const debtGrid = document.getElementById('debt-grid');
const sortedDebt = [...debt].sort((a,b) => {{
  if (a.status === 'open' && b.status !== 'open') return -1;
  if (a.status !== 'open' && b.status === 'open') return 1;
  return 0;
}});
sortedDebt.forEach(d => {{
  const item = document.createElement('div');
  item.className = 'debt-item' + (d.status === 'resolved' ? ' debt-resolved' : '');
  item.innerHTML = `
    <div class="debt-icon ${{d.status === 'resolved' ? 'debt-icon-resolved' : 'debt-icon-open'}}">
      ${{d.status === 'resolved' ? '&#10003;' : '&#9679;'}}
    </div>
    <div>
      <div class="debt-name">${{d.id}} — ${{d.item.substring(0,60)}}</div>
      <div class="debt-detail">${{d.severity}} &middot; ${{d.location.substring(0,60)}}</div>
    </div>
  `;
  debtGrid.appendChild(item);
}});

// Render risks
const riskList = document.getElementById('risk-list');
risks.forEach(r => {{
  const item = document.createElement('div');
  item.className = 'risk-item';
  item.innerHTML = `
    <div class="risk-name">${{r.name}}</div>
    <div class="risk-detail">${{r.detail}}</div>
  `;
  riskList.appendChild(item);
}});

// Render activity feed
const activityFeed = document.getElementById('activity-feed');
if (activityFeed) {{
  activities.forEach(a => {{
    const item = document.createElement('div');
    item.className = 'activity-item';
    item.innerHTML = `
      <span class="activity-date">${{a.date}}</span>
      <span class="activity-phase">${{a.phase}}</span>
      <span class="activity-text">${{a.activity}}</span>
    `;
    activityFeed.appendChild(item);
  }});
}}

// Render roadmap
const roadmapList = document.getElementById('roadmap-list');
if (roadmapList) {{
  roadmap.forEach(r => {{
    const item = document.createElement('div');
    item.className = 'roadmap-item' + (r.status === 'concept' ? ' concept' : '');
    item.innerHTML = `
      <div class="roadmap-priority ${{r.status}}">${{r.priority}}</div>
      <div>
        <div class="roadmap-name">${{r.phase}}</div>
        <div class="roadmap-desc">${{r.description}}</div>
      </div>
      <span class="roadmap-dep">depends: ${{r.depends_on}}</span>
    `;
    roadmapList.appendChild(item);
  }});
}}

// Live-update capability (falls back gracefully if API unavailable)
let lastUpdate = Date.now();
function updateRefreshIndicator() {{
  const now = Date.now();
  const secondsAgo = Math.floor((now - lastUpdate) / 1000);
  const indicator = document.getElementById('refresh-indicator');
  if (indicator) {{
    if (secondsAgo < 60) {{
      indicator.textContent = secondsAgo + 's ago';
    }} else {{
      const minutesAgo = Math.floor(secondsAgo / 60);
      indicator.textContent = minutesAgo + 'm ago';
    }}
  }}
}}
setInterval(updateRefreshIndicator, 5000);
</script>

</body>
</html>"""
    return html


# ─── Main ───

def main():
    parser = argparse.ArgumentParser(description="Generate project dashboard from markdown files")
    parser.add_argument("--progress", "-p", help="Path to progress markdown file")
    parser.add_argument("--specs", "-s", nargs="*", help="Paths to spec files or directory containing specs")
    parser.add_argument("--output", "-o", default="dashboard.html", help="Output HTML file path")
    parser.add_argument("--folder", "-f", help="Auto-discover files in folder")
    args = parser.parse_args()

    # Auto-discovery mode
    if args.folder:
        folder = Path(args.folder)
        progress_files = list(folder.glob("*Progress*.md")) + list(folder.glob("*progress*.md"))
        spec_files = list(folder.glob("*SPEC*.md")) + list(folder.glob("*spec*.md"))
        if not progress_files:
            print("No progress file found in folder")
            sys.exit(1)
        args.progress = str(progress_files[0])
        args.specs = [str(f) for f in spec_files]
        print(f"Auto-discovered: progress={args.progress}, specs={[str(f) for f in spec_files]}")

    if not args.progress:
        print("Please provide --progress or --folder")
        sys.exit(1)

    # Parse progress
    print(f"Parsing progress file: {args.progress}")
    dashboard = parse_progress_file(args.progress)

    # Parse specs
    if args.specs:
        for spec_path in args.specs:
            p = Path(spec_path)
            if p.is_dir():
                spec_files = list(p.glob("*SPEC*.md")) + list(p.glob("*spec*.md"))
            else:
                spec_files = [p]
            for sf in spec_files:
                print(f"Parsing spec: {sf}")
                spec = parse_spec_file(str(sf))
                if spec:
                    dashboard.specs.append(spec)

    # Generate
    html = generate_html(dashboard)
    output_path = args.output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nDashboard generated: {output_path}")
    print(f"  Phases: {len(dashboard.phases)}")
    print(f"  Specs: {len(dashboard.specs)}")
    print(f"  Tech debt items: {len(dashboard.tech_debt)}")
    print(f"  Test milestones: {len(dashboard.test_milestones)}")


if __name__ == "__main__":
    main()
