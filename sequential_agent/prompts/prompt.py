from typing import Any
from pathlib import Path

def user_agent_prompt(agent_output_schema: dict[str, Any]) -> str:
    return _retrieve("user_agent").format(output_schema=agent_output_schema)

def universal_credit_agent_prompt() -> str:
    return _retrieve("universal_credit_agent")

def personal_independence_payment_agent_prompt() -> str:
    return _retrieve("personal_independence_payment_agent")

def elicitation_agent_prompt(user_agent_to_elicitation_agent_schema: dict[str, Any], elicitation_agent_response_schema: dict[str, Any]) -> str:
    return _retrieve("elicitation_agent").format(
        user_agent_to_elicitation_agent_schema=user_agent_to_elicitation_agent_schema, 
        elicitation_agent_response_schema=elicitation_agent_response_schema
    )

def _retrieve(agent_prompt: str) -> str:
    file_path = Path.cwd() / f"sequential_agent/prompts/{agent_prompt}.md" 
    print(file_path)
    return file_path.read_text(encoding='utf-8')