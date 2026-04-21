"""Exponential backoff retry for OpenAI API calls.

Extracted from AutoGPT llm_utils.py → updated for openai SDK v1+.
Handles RateLimitError and transient 502s.
"""

import time
import openai


def create_chat_completion(
    client: openai.OpenAI,
    messages: list[dict],
    model: str = "gpt-4o",
    temperature: float = 0.7,
    max_tokens: int | None = None,
    max_retries: int = 10,
) -> str:
    """Call OpenAI chat completions with exponential backoff retry.

    Args:
        client: An initialized openai.OpenAI instance.
        messages: The messages to send.
        model: Model name.
        temperature: Sampling temperature.
        max_tokens: Max tokens for the response.
        max_retries: Number of retry attempts.

    Returns:
        The assistant's response text.
    """
    for attempt in range(max_retries):
        backoff = 2 ** (attempt + 2)  # 4, 8, 16, 32, ...
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except openai.RateLimitError:
            print(f"[retry] Rate limited. Waiting {backoff}s (attempt {attempt + 1}/{max_retries})")
        except openai.APIStatusError as e:
            if e.status_code == 502:
                print(f"[retry] Bad gateway. Waiting {backoff}s (attempt {attempt + 1}/{max_retries})")
            else:
                raise
        time.sleep(backoff)

    raise RuntimeError(f"Failed to get response after {max_retries} retries")
