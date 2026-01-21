from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.agents.llm_agent import Agent
from google.adk.agents import SequentialAgent
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH
from google.adk.tools.agent_tool import AgentTool
from google.adk.models.lite_llm import LiteLlm
from pydantic import BaseModel, Field
from google.genai import types
from typing import Literal, Dict, Any
from google.adk.tools.tool_context import ToolContext
from sequential_agent.prompts import user_agent_prompt, elicitation_agent_prompt

def get_state(tool_context: ToolContext ) -> Dict[str, Any]:
    """Gets state.
    
    Args:
       tool_context: Automatically injected by ADK
        
    Returns:
        dict: answer provided
    """
    print("TOOL CALLED")
    print(tool_context.state._value)
    return tool_context.state._value

def update_questionnaire(question: str, provided_answer: str, tool_context: ToolContext ) -> Dict[str, Any]:
    """Update questionnaire.
    
    Args:
       question_and_number: the question asked without a numeric identifier, e.g. "Do you live in the UK?"
       provided_answer: the answer to the question, e.g. "Yes, I live in the UK"
       tool_context: Automatically injected by ADK
        
    Returns:
        dict: state
    """
    tool_context.state[question] = provided_answer

    return {
        "state": tool_context.state._value
    }

def sign_in(tool_context: ToolContext) -> Dict[str, Any]:
    tool_context.state["What is your age?"] = "39"
    tool_context.state["How much do you earn per annum net tax?"] = "£12,452"

    return {
        "state": tool_context.state._value
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

elicitation_agent = Agent(
    name="elicitation_agent", 
    model=LiteLlm(
        model="bedrock/openai.gpt-oss-120b-1:0",
        # model="bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0",
        # it is not clear if LiteLLM/Google ADK is picking up the following response format
        response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "response",
            "schema": ElicitationResponse.model_json_schema(),
            "strict": True,
        },
    },
    ),
    description="An agent to process responses for possible elicitation",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.1,
    ),
    instruction=elicitation_agent_prompt(
        user_agent_to_elicitation_agent_schema=UserAgentToElicitation.model_json_schema(), 
        elicitation_agent_response_schema=ElicitationResponse.model_json_schema()
    ),
    output_schema=ElicitationResponse,# this is not being enforced?
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
        update_questionnaire,
        get_state,
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