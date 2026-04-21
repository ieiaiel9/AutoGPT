"""
RAZ Core - Meeting Mode
Structured meeting facilitation: agenda, decisions, actions, and output.
Integrates with memory engine to persist meeting records.
"""

import os
import sys
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import core.memory_engine as mem

MEETING_LOG_DIR = os.path.join(BASE_DIR, "logs", "meetings")


class MeetingSession:
    def __init__(self, session_id: str, title: str = "Untitled Meeting"):
        self.session_id = session_id
        self.title = title
        self.started_at = datetime.now().isoformat()
        self.ended_at = None
        self.objectives = []
        self.agenda_items = []
        self.current_item = None
        self.decisions = []
        self.action_items = []
        self.open_questions = []
        self.notes = []
        self.participants = ["Ryan Wallace", "RAZ"]

    def set_objective(self, objective: str):
        self.objectives.append(objective)
        return f"Objective set: {objective}"

    def add_agenda_item(self, item: str):
        self.agenda_items.append({"item": item, "status": "pending", "notes": []})
        return f"Agenda item added: {item}"

    def next_agenda_item(self):
        for item in self.agenda_items:
            if item["status"] == "pending":
                item["status"] = "active"
                self.current_item = item
                return f"Now discussing: {item['item']}"
        return "All agenda items have been covered."

    def log_decision(self, decision: str):
        entry = {
            "decision": decision,
            "timestamp": datetime.now().isoformat(),
            "agenda_item": self.current_item["item"] if self.current_item else "general"
        }
        self.decisions.append(entry)
        return f"Decision logged: {decision}"

    def log_action(self, action: str, owner: str = "Ryan", due: str = None):
        entry = {
            "action": action,
            "owner": owner,
            "due": due,
            "timestamp": datetime.now().isoformat()
        }
        self.action_items.append(entry)
        mem.save_task(
            title=action,
            description=f"From meeting: {self.title} ({self.session_id})",
            priority="normal",
            project=self.title
        )
        return f"Action logged: {action} | Owner: {owner}"

    def log_question(self, question: str):
        self.open_questions.append({
            "question": question,
            "timestamp": datetime.now().isoformat()
        })
        return f"Open question logged: {question}"

    def add_note(self, note: str):
        self.notes.append({
            "note": note,
            "timestamp": datetime.now().isoformat()
        })

    def generate_summary(self) -> str:
        self.ended_at = datetime.now().isoformat()
        duration_note = ""
        if self.started_at and self.ended_at:
            start = datetime.fromisoformat(self.started_at)
            end = datetime.fromisoformat(self.ended_at)
            mins = int((end - start).total_seconds() / 60)
            duration_note = f"{mins} minutes"

        lines = [
            f"MEETING SUMMARY",
            f"{'=' * 50}",
            f"Title: {self.title}",
            f"Session: {self.session_id}",
            f"Started: {self.started_at[:16]}",
            f"Duration: {duration_note}",
            ""
        ]

        if self.objectives:
            lines.append("OBJECTIVES:")
            for o in self.objectives:
                lines.append(f"  - {o}")
            lines.append("")

        if self.agenda_items:
            lines.append("AGENDA COVERED:")
            for item in self.agenda_items:
                status_icon = "OK" if item["status"] == "active" else "NOT REACHED"
                lines.append(f"  [{status_icon}] {item['item']}")
            lines.append("")

        if self.decisions:
            lines.append(f"DECISIONS ({len(self.decisions)}):")
            for d in self.decisions:
                lines.append(f"  - {d['decision']}")
            lines.append("")

        if self.action_items:
            lines.append(f"ACTION ITEMS ({len(self.action_items)}):")
            for a in self.action_items:
                due_str = f" | Due: {a['due']}" if a["due"] else ""
                lines.append(f"  - [{a['owner']}]{due_str} {a['action']}")
            lines.append("")

        if self.open_questions:
            lines.append(f"OPEN QUESTIONS ({len(self.open_questions)}):")
            for q in self.open_questions:
                lines.append(f"  ? {q['question']}")
            lines.append("")

        if self.notes:
            lines.append(f"NOTES ({len(self.notes)}):")
            for n in self.notes:
                lines.append(f"  * {n['note']}")
            lines.append("")

        return "\n".join(lines)

    def save_to_file(self) -> str:
        os.makedirs(MEETING_LOG_DIR, exist_ok=True)
        safe_title = self.title.replace(" ", "_").replace("/", "-")[:40]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"{timestamp}_{safe_title}.json"
        filepath = os.path.join(MEETING_LOG_DIR, filename)

        data = {
            "session_id": self.session_id,
            "title": self.title,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "objectives": self.objectives,
            "agenda_items": self.agenda_items,
            "decisions": self.decisions,
            "action_items": self.action_items,
            "open_questions": self.open_questions,
            "notes": self.notes,
            "participants": self.participants
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        mem.end_session(
            self.session_id,
            summary=self.generate_summary(),
            decisions=[d["decision"] for d in self.decisions],
            action_items=[a["action"] for a in self.action_items]
        )

        return filepath


def load_meeting(filepath: str) -> dict:
    """Load a saved meeting record."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def list_past_meetings(limit: int = 10) -> list:
    """List saved meeting files, most recent first."""
    if not os.path.isdir(MEETING_LOG_DIR):
        return []
    files = sorted(
        [f for f in os.listdir(MEETING_LOG_DIR) if f.endswith(".json")],
        reverse=True
    )
    return files[:limit]


def get_meeting_prompt(meeting: MeetingSession) -> str:
    """Generate a context injection for LLM when in meeting mode."""
    parts = [f"We are currently in Meeting Mode. Meeting: '{meeting.title}'"]
    if meeting.objectives:
        parts.append(f"Objectives: {'; '.join(meeting.objectives)}")
    if meeting.agenda_items:
        items = [i["item"] for i in meeting.agenda_items]
        parts.append(f"Agenda: {', '.join(items)}")
    if meeting.decisions:
        parts.append(f"Decisions so far: {len(meeting.decisions)}")
    if meeting.action_items:
        parts.append(f"Actions logged so far: {len(meeting.action_items)}")
    parts.append("Help organize the conversation, capture decisions and action items, and keep things moving forward.")
    return " ".join(parts)


if __name__ == "__main__":
    mem.init_memory()
    import uuid
    session_id = str(uuid.uuid4())[:8]
    mem.start_session(session_id, mode="meeting")

    meeting = MeetingSession(session_id=session_id, title="RAZ Core v1 Build Planning")
    meeting.set_objective("Define RAZ Core v1 architecture")
    meeting.set_objective("Lock MVP scope")
    meeting.add_agenda_item("Core capabilities review")
    meeting.add_agenda_item("Memory system design")
    meeting.add_agenda_item("Next build steps")

    print(meeting.next_agenda_item())
    meeting.log_decision("Use SQLite for local memory, no cloud dependency in v1")
    meeting.log_action("Complete ingestion pipeline", owner="RAZ")
    meeting.log_action("Set up OpenAI API key in config", owner="Ryan")
    meeting.log_question("Should overnight mode run on a separate thread or process?")

    summary = meeting.generate_summary()
    print(summary)
    saved_path = meeting.save_to_file()
    print(f"[MEETING] Saved to: {saved_path}")
