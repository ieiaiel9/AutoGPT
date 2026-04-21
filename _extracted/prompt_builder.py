"""Structured prompt builder — constraints, commands, resources, evaluations.

Extracted from AutoGPT promptgenerator.py.
Use this to programmatically build system prompts for RAZ-Core modes
(meeting, overnight, etc.) without string concatenation.
"""

import json
from typing import Any


class PromptBuilder:
    """Build structured system prompts from composable parts."""

    def __init__(self):
        self.constraints: list[str] = []
        self.commands: list[dict[str, Any]] = []
        self.resources: list[str] = []
        self.evaluations: list[str] = []
        self.response_format: dict | None = None

    def add_constraint(self, text: str) -> "PromptBuilder":
        self.constraints.append(text)
        return self

    def add_command(self, label: str, name: str, args: dict[str, str] | None = None) -> "PromptBuilder":
        self.commands.append({"label": label, "name": name, "args": args or {}})
        return self

    def add_resource(self, text: str) -> "PromptBuilder":
        self.resources.append(text)
        return self

    def add_evaluation(self, text: str) -> "PromptBuilder":
        self.evaluations.append(text)
        return self

    def set_response_format(self, schema: dict) -> "PromptBuilder":
        self.response_format = schema
        return self

    def _numbered(self, items: list, formatter=None) -> str:
        fmt = formatter or (lambda x: str(x))
        return "\n".join(f"{i+1}. {fmt(item)}" for i, item in enumerate(items))

    @staticmethod
    def _format_command(cmd: dict) -> str:
        args_str = ", ".join(f'"{k}": "{v}"' for k, v in cmd["args"].items())
        return f'{cmd["label"]}: "{cmd["name"]}", args: {args_str}'

    def build(self) -> str:
        """Generate the full prompt string."""
        sections = []
        if self.constraints:
            sections.append(f"Constraints:\n{self._numbered(self.constraints)}")
        if self.commands:
            sections.append(
                f"Commands:\n{self._numbered(self.commands, self._format_command)}"
            )
        if self.resources:
            sections.append(f"Resources:\n{self._numbered(self.resources)}")
        if self.evaluations:
            sections.append(f"Performance Evaluation:\n{self._numbered(self.evaluations)}")
        if self.response_format:
            sections.append(
                f"Response Format:\n{json.dumps(self.response_format, indent=2)}\n"
                "Respond only in valid JSON matching this schema."
            )
        return "\n\n".join(sections)
