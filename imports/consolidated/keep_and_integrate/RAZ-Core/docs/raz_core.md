# RAZ Core Context

- Project: RAZ-Core local-first assistant runtime
- Primary entrypoint: app.py
- Tablet entrypoint: app_tablet.py
- Config source: system/config.json
- Shared key source: C:/Users/Ry/OneDrive/RAZ/shared/keys.json
- Preferred desktop interpreter: .venv/Scripts/python.exe
- Active desktop lock port: 54321
- Active tablet lock port: 54322
- Tablet sync monitor: scripts/sync_tablet.ps1
- VS Code live diagnostics: scripts/vscode_live_status.ps1
- VS Code perf monitor: scripts/vscode_perf_monitor.ps1
- VS Code resource optimizer: scripts/optimize_vscode_resources.ps1
- Startup context loader: scripts/load_startup_context.ps1
- Rule: keep app running after edits for immediate validation
