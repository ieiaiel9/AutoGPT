"""Agent loop skeleton — Think → Act → Observe cycle.

Extracted from AutoGPT agent/agent.py → simplified for RAZ-Core.
This is a reference pattern, not runnable as-is. Adapt for
RAZ-Core's overnight scheduler or autonomous task runner.
"""


def agent_loop(system_prompt, memory, tools, max_steps=25):
    """Run an autonomous think→act→observe loop.

    Args:
        system_prompt: The system prompt defining the agent's persona and goals.
        memory: A memory backend with add() and search() methods.
        tools: A dict mapping tool names to callables: {"name": func(args) -> str}
        max_steps: Safety limit on loop iterations.

    Pattern:
        1. THINK:  Send context to LLM, get structured response
        2. PARSE:  Extract {thoughts, command} from JSON response
        3. AUTHORIZE: Ask user for y/n/feedback (unless continuous mode)
        4. ACT:    Execute the selected command
        5. OBSERVE: Store result in memory + message history
        6. REPEAT
    """
    history = []
    
    for step in range(max_steps):
        # 1. THINK — send everything to the LLM
        # context = build_context(system_prompt, memory.search(recent_context), history, model, token_limit)
        # response = create_chat_completion(client, context, model)

        # 2. PARSE — extract command from JSON response
        # parsed = json.loads(response)
        # command_name = parsed["command"]["name"]
        # command_args = parsed["command"]["args"]
        # thoughts = parsed["thoughts"]["text"]

        # 3. AUTHORIZE — user checkpoint
        # user_input = input(f"Execute '{command_name}'? (y/n/feedback): ")
        # if user_input == "n": break
        # if user_input not in ("y", ""): 
        #     history.append({"role": "user", "content": user_input})
        #     continue

        # 4. ACT — execute the command
        # if command_name in tools:
        #     result = tools[command_name](**command_args)
        # else:
        #     result = f"Unknown command: {command_name}"

        # 5. OBSERVE — record what happened
        # memory.add(f"Command: {command_name} | Result: {result}")
        # history.append({"role": "assistant", "content": response})
        # history.append({"role": "system", "content": f"Command result: {result}"})
        
        pass  # Replace with actual implementation

    return history
