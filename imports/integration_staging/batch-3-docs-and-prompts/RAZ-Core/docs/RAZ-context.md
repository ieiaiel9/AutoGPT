# RAZ Context

## Purpose
RAZ is a local-first personal AI desktop app for Ryan that blends chat, memory, automation, and workflow execution.

## Primary Entry Points
- app.py: Desktop UI runtime
- app_tablet.py: Tablet mode runtime
- main.py: Core chat launcher

## Core Modules
- core/chat.py: Model routing, streaming, fallback handling, tool loop
- core/memory_engine.py: Persistent memory, sessions, tasks, followups
- core/secret_brain.py: Secret Brain ingestion and profile synthesis
- system/prompt_loader.py: Base identity, mode overlays, and execution rules

## Operational Rules
- Keep one canonical interpreter: .venv\\Scripts\\python.exe
- Prefer scripted tasks in .vscode/tasks.json over ad hoc terminal commands
- Keep launch/debug presets in .vscode/launch.json in sync with tasks
- Preserve single-instance behavior and update flow in scripts/update_everything_now.ps1

## Daily Command Deck
- Build: scripts/build_apps.ps1
- Full update: scripts/update_everything_now.ps1
- Tablet sync once: scripts/sync_tablet.ps1 -Once
- Desktop run: .venv\\Scripts\\python.exe app.py

## Quality Gates
- Lint: .venv\\Scripts\\python.exe -m ruff check .
- Tests: .venv\\Scripts\\python.exe -m pytest -q

## Safety and Reliability
- Keep workspace trust on prompt for untrusted files
- Avoid broad auto-approve behavior for agentic actions
- Use structured JSON for system/config.json edits
