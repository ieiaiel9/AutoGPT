"""Token counting utilities using tiktoken.

Extracted from AutoGPT → modernized for current OpenAI models.
Use with RAZ-Core's chat.py for context window management.
"""

import tiktoken


def count_message_tokens(messages: list[dict[str, str]], model: str = "gpt-4o") -> int:
    """Count tokens used by a list of chat messages.

    Accounts for per-message framing overhead used by OpenAI's chat format.
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    # All current chat models use 3 tokens per message + 1 per name
    tokens_per_message = 3
    tokens_per_name = 1

    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


def count_string_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens in a plain text string."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))
