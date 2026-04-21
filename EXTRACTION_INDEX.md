# AutoGPT → RAZ-Core Extraction Index

Patterns extracted from AutoGPT (Significant-Gravitas, stable branch) for
cannibalization into RAZ-Core. Each file below is a standalone, modernized
snippet ready to integrate.

## Extracted Patterns

| File | Source | Purpose |
|------|--------|---------|
| `_extracted/token_counter.py` | `autogpt/token_counter.py` | tiktoken-based token counting for messages and strings |
| `_extracted/context_window.py` | `autogpt/chat.py` | Backwards-walk context window management with token budget |
| `_extracted/sqlite_fts5_memory.py` | `autogpt/permanent_memory/sqlite3_store.py` | SQLite FTS5 full-text search memory with sessions |
| `_extracted/retry_llm.py` | `autogpt/llm_utils.py` | Exponential backoff retry for OpenAI API calls (modernized) |
| `_extracted/prompt_builder.py` | `autogpt/promptgenerator.py` | Structured prompt builder: constraints, commands, resources |
| `_extracted/workspace_sandbox.py` | `autogpt/workspace.py` | Path sandboxing to prevent directory traversal |
| `_extracted/agent_loop.py` | `autogpt/agent/agent.py` | Think→Act→Observe loop skeleton with user authorization |

## Workspace Artifacts (Previous RAZ Runs)

The `auto_gpt_workspace/` directory contains outputs from previous AutoGPT
sessions configured as "RAZ". Key content:

- `goals.txt` — Ryan's personal goals (AI, business, scheduling)
- `tasks.txt` — Task breakdown per goal
- `marketing_plan.txt` — Music festival marketing plan (Oct 13-14)
- `content_calendar.txt` — Social media calendar
- `ticket_sales.py` — QR code ticket generator
- `*_strategies.txt` — Festival/social media strategy research

## Not Extracted (AutoGPT-specific)

- Docker code execution (`execute_code.py`)
- Pinecone/Redis memory backends
- Google/web search commands
- Browser automation
- Image generation commands
- Plugin system stubs
- Typing effect console handler
