from typing import Literal, Dict, Any, Optional, List

from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.agents.llm_agent import Agent
from google.adk.agents import SequentialAgent
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH
from google.adk.tools.agent_tool import AgentTool
from google.adk.models.lite_llm import LiteLlm
from google.genai import types
from google.adk.tools.tool_context import ToolContext
from pydantic import BaseModel, Field

from sequential_agent.prompts import user_agent_prompt, elicitation_agent_prompt


def update_question_and_answers(question: str, provided_answer: str, tool_context: ToolContext ) -> Dict[str, Any]:
    """Update questionnaire.
    
    Args:
       question_and_number: the question asked without a numeric identifier, e.g. "Do you live in the UK?"
       provided_answer: the answer to the question, e.g. "Yes, I live in the UK"
       tool_context: Automatically injected by ADK
        
    Returns:
        dict: state
    """
    questions_and_responses = tool_context.state.setdefault("questions_and_responses", {})
    print(questions_and_responses)
    questions_and_responses[question] = provided_answer
    print(questions_and_responses)
    tool_context.state["questions_and_responses"] = questions_and_responses
    
    return {
        "state": tool_context.state.to_dict()
    }


def sign_in(tool_context: ToolContext) -> None:
    questions_and_responses = tool_context.state.setdefault("questions_and_responses", {})
    questions_and_responses["What is your age?"] = "39"
    questions_and_responses["How much do you earn per annum net tax?"] = "£12,452"
    tool_context.state["questions_and_responses"] = questions_and_responses

    return {
        "state": tool_context.state.to_dict()
    }


universal_credit_agent = RemoteA2aAgent(
    name="universal_credit_agent",
    description="Agent that can work out if someone is eligible for universal credit benefit",
    agent_card=(f"http://localhost:8001/a2a/universal_credit_agent{AGENT_CARD_WELL_KNOWN_PATH}"),
)

personal_independence_payments_agent = RemoteA2aAgent(
    name="personal_independence_payments_agent",
    description="Agent that can determine how likely it is that someone is eligible for personal independence payments",
    agent_card=(f"http://localhost:8001/a2a/personal_independence_payments_agent{AGENT_CARD_WELL_KNOWN_PATH}"),
)

reply_types = Literal["yes_no", "choice_multiple", "choice_single", "free_text", "none"]
sources = Literal["benefit_agent", "user_agent"]

class UserAgentToElicitation(BaseModel):
    content:str
    source: sources
    expects_reply: bool
    reply_type: reply_types
    choices: list[str] | None = None

class ElicitationAction(BaseModel):
    label: str = Field(description='The text to display on a user modality (i.e. a button)')
    payload: str = Field(description='The message to send to the agent if the user chooses this option - this can be more detailed than the label')

class ElicitationResponse(BaseModel):
    content: str = Field(description='The free text to display to the user - this is always required')
    source: sources
    reply_type: reply_types
    actions: list[ElicitationAction]| None = None

def emit_elicitation_response(
    content: str,
    source: str,
    reply_type: str,
    actions: Optional[List[dict]] = None,
) -> dict:
    """
    Emits a final ElicitationResponse.
    This tool is terminal: no conversational output should follow.
    
    `actions` must either be `null` or a list of objects:
    [{"label": "string", "payload": "string"}]
    """
    if actions is not None:
        validated_actions = []
        for action in actions:
            if "label" in action and "payload" in action:
                validated_actions.append({
                    "label": str(action["label"]),
                    "payload": str(action["payload"])
                })
        actions = validated_actions if validated_actions else None

    return {
        "content": content,
        "source": source,
        "reply_type": reply_type,
        "actions": actions,
    }

elicitation_agent = Agent(
    name="elicitation_agent", 
    
    model=LiteLlm(
        model="bedrock/openai.gpt-oss-120b-1:0",
        # model="bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0",
    ),
    description="An agent to process responses for possible elicitation",
    tools=[emit_elicitation_response],
    generate_content_config=types.GenerateContentConfig(
        temperature=0.1,
    ),
    instruction=elicitation_agent_prompt(
        user_agent_to_elicitation_agent_schema=UserAgentToElicitation.model_json_schema(), 
        elicitation_agent_response_schema=ElicitationResponse.model_json_schema()
    ),
)
 
user_agent = Agent(
    model=LiteLlm(
        model="bedrock/openai.gpt-oss-120b-1:0", 
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "response",
                "schema": UserAgentToElicitation.model_json_schema(),
                "strict": True,
            },
        }
    ),
    name="user_agent",
    description="An agent that helps users",
    instruction=user_agent_prompt(UserAgentToElicitation.model_json_schema()),
    tools=[
        (AgentTool(universal_credit_agent)), 
        (AgentTool(personal_independence_payments_agent)),
        update_question_and_answers,
        sign_in
    ],
    output_schema=UserAgentToElicitation
)

sequential_agent = SequentialAgent(
    name="eligibility_sequential_agent",
    sub_agents=[user_agent, elicitation_agent],
    description="Executes a sequence of eligibility mediation and elicitation of responses into JSON.",
)

root_agent = sequential_agent