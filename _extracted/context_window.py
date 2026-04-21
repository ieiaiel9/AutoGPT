"""Context window management — backwards-walk with token budget.

Extracted from AutoGPT chat.py. This is the core algorithm for fitting
as much message history as possible into a fixed token window.

Usage in RAZ-Core:
    context = build_context(system_prompt, memory_text, history, "gpt-4o", 8192)
    response = openai_client.chat.completions.create(messages=context, ...)
"""

import time
from token_counter import count_message_tokens


def _msg(role: str, content: str) -> dict:
    return {"role": role, "content": content}


def build_context(
    system_prompt: str,
    relevant_memory: str,
    full_message_history: list[dict],
    model: str,
    token_limit: int,
    reserve_for_response: int = 1000,
    max_memory_tokens: int = 2500,
) -> list[dict]:
    """Build a context array that fits within token_limit.

    Algorithm:
    1. Start with system prompt + timestamp + relevant memories
    2. Trim memories if they alone exceed max_memory_tokens
    3. Walk message history backwards, inserting until budget is hit
    4. Append the latest user input (already in history[-1])

    Returns the messages list ready for the OpenAI API.
    """
    send_limit = token_limit - reserve_for_response

    # Base context: system prompt + time + memories
    context = [
        _msg("system", system_prompt),
        _msg("system", f"The current time and date is {time.strftime('%c')}"),
    ]
    if relevant_memory:
        context.append(
            _msg("system", f"Relevant memories:\n{relevant_memory}")
        )

    # Trim memories if base context is too large
    trimmed_memory = relevant_memory
    while count_message_tokens(context, model) > max_memory_tokens and trimmed_memory:
        trimmed_memory = trimmed_memory[:-1]
        context = [
            _msg("system", system_prompt),
            _msg("system", f"The current time and date is {time.strftime('%c')}"),
        ]
        if trimmed_memory:
            context.append(
                _msg("system", f"Relevant memories:\n{trimmed_memory}")
            )

    current_tokens = count_message_tokens(context, model)
    insertion_index = len(context)

    # Walk history backwards, inserting most-recent messages first
    for i in range(len(full_message_history) - 1, -1, -1):
        message = full_message_history[i]
        msg_tokens = count_message_tokens([message], model)
        if current_tokens + msg_tokens > send_limit:
            break
        context.insert(insertion_index, message)
        current_tokens += msg_tokens

    return context
