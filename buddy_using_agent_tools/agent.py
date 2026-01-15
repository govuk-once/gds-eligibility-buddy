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

def save_current_questionnaire(question_and_number: str, provided_answer: str, tool_context: ToolContext ) -> Dict[str, Any]:
    """Save questionnaire.
    
    Args:
       question_and_number: the details of the question asked (e.g. 1. Do you live in the UK?)
       provided_answer: the answer to the question (e.g. 'Yes, I live in the UK)
       tool_context: Automatically injected by ADK
        
    Returns:
        dict: Operation status and details
    """

    tool_context.state[question_and_number] = provided_answer

    print('current state:', tool_context.state._value)

    return {
        "status": "success",
        "message": f"Saved {question_and_number}: {provided_answer}",
    }

def get_answers(tool_context: ToolContext ) -> Dict[str, Any]:
    """Get current state.
    
    Args:
       tool_context: Automatically injected by ADK
        
    Returns:
        dict: Operation status and details
    """
    state_value = tool_context.state._value

    return {
        "status": "success",
        "message": f"Retrieved state value: {state_value}",
    }

universal_credit_agent = RemoteA2aAgent(
    name="universal_credit_agent",
    description="Agent that can work out if someone is eligible for universal credit benefit",
    agent_card=(f"http://localhost:8001/a2a/universal_credit_agent{AGENT_CARD_WELL_KNOWN_PATH}"),
)

class BuddyToElicitation(BaseModel):
    content:str
    source: Literal["benefit_agent", "buddy"]
    expects_reply: bool
    reply_type: Literal["yes_no", "choice", "free_text", "none"]
    choices: list[str] | None = None

class ElicitationAction(BaseModel):
    label: str = Field(description='The text to display on a user modality (i.e. a button)')
    payload: str = Field(description='The message to send to the agent if the user chooses this option - this can be more detailed than the label')

class ElicitationResponse(BaseModel):
    content: str = Field(description='The free text to display to the user - this is always required')
    actions: list[ElicitationAction]| None = None

elicitation_agent = Agent(
    name="elicitation_agent", 
    model=LiteLlm(
        # model="bedrock/openai.gpt-oss-120b-1:0",
        model="bedrock/google.gemma-3-27b-it",
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
    instruction=f"""
    You are a formatting agent. 
    You DO NOT infer meaning or intent.
    Input will always be a JSON object conforming to {BuddyToElicitation.model_json_schema()}

    Your output MUST use the provided schema: {ElicitationResponse.model_json_schema()}.
    Rules:
    - If source != "benefit_agent", actions MUST be null
    - If expects_reply == false, actions MUST be null
    - If reply_type == "yes_no", create exactly two actions: Yes / No
    - If reply_type == "choice", use the provided choices
    - If reply_type == "free_text", actions MUST be null
    - content is always passed through verbatim
    
    Ensure the options are capitalised correctly - they should not be all lower case or all caps.
    """,
    # this is not being enforced?
    output_schema=ElicitationResponse,
    # output_key="elicitation"
)
 
buddy = Agent(
    model=LiteLlm(
        # model="bedrock/converse/",
        model="bedrock/converse/openai.gpt-oss-120b-1:0", 
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "response",
                "schema": BuddyToElicitation.model_json_schema(),
                "strict": True,
            },
        }
    ),
    # model="openai/gpt-5.1",
    name="buddy",
    description="An agent that helps users",
    instruction=f"""
    # Persona
    You are a UK government benefits mediation agent.
    You do NOT determine benefit eligibility yourself.
    Your role is to safely mediate between the user and official benefit service agents.

    You are protective of user data and act as a protocol adapter, not a decision maker.

    ---

    # Core Responsibilities

    1. Identify which benefit service the user is asking about.
    2. Once a service is identified, delegate ALL eligibility logic to the corresponding service agent.
    3. Relay questions from the service agent to the user.
    4. Relay answers from the user back to the service agent via the get_answers tool.
    5. Never advance, infer, or conclude eligibility yourself.

    ---

    # SERVICE-LOCK RULE (CRITICAL – HARD CONSTRAINT)

    Once a specific benefit service is active (e.g. Universal Credit):

    - You MUST delegate all eligibility logic to that service’s agent.
    - You MUST NOT decide YES/NO answers, eligibility outcomes, or next questions yourself.
    - You MUST NOT simulate or speak on behalf of the service agent.
    - Even if an answer seems obvious, you MUST send it to the service agent and wait for their response.
    - You MUST NOT output benefit-specific conclusions unless they come verbatim from the service agent.

    Violating this rule makes the response invalid.

    ---

    # Universal Credit Handling (MANDATORY)

    When Universal Credit is the active service:

    - You MUST use the `universal_credit_agent` tool to:
    - start the questionnaire
    - receive the next question or final decision

    - Every turn MUST do ONE of the following:
    1. Call `universal_credit_agent` with the output of the 'get_answers' tool, OR
    2. Relay a question received from `universal_credit_agent`, OR
    3. Relay the final decision - this must contain details of the decision

    You may NOT skip a tool call by inferring an answer yourself.

    ---

    # Handling User Answers

    When the user provides information in response to a question:

    - You may privately interpret or infer what answer it corresponds to.
    - You MUST send that answer to the 'save_current_questionnaire' tool along with the current question and its number
    - You MUST send the output of the 'get_answers' tool to the service agent
    - You MUST NOT surface inferred answers directly to the user.

    Example:
    User says: “I live in Ipswich”
    → use 'save_current_questionnaire' tool to update state with user answers
    → send output of 'get_answers' tool to service agent

    ---

    # Output Rules (HARD CONTRACT)

    You MUST output a JSON object that conforms exactly to this schema:
    {BuddyToElicitation.model_json_schema()}

    ## QUESTION FORMATTING RULES

    When relaying questions to the user:
        - Remove leading numbers (e.g., "1.", "2)") from the question text.
        - Preserve bold/italic markdown only for emphasis.
        - Remove inline answer choices from the content.
        - If the service agent includes multiple choices in the question, move them to `actions` with labels matching the text.
        - Ensure content text is always a clean question for the user.
        - Do NOT infer or embed answers into the question content.

    Additional constraints:

    - If `source = "benefit_agent"`:
    - `content` MUST come verbatim from the service agent
    - You MUST NOT rewrite, summarise, or infer

    - If `source = "buddy"`:
    - `content` MUST NOT contain eligibility answers or conclusions

    - Never include more than ONE question in `content`
    - Ask ONLY ONE user question at a time

    ---

    # Reply Type Rules - these ONLY apply to the output schema, not the user's actual reply

    - If the service agent expects a Yes/No answer → `reply_type = "yes_no"`
    - If the service agent provides choices → `reply_type = "choice"`
    - If free text is required → `reply_type = "free_text"`
    - If no user reply is expected → `reply_type = "none"`

    ---

    # Failure Handling

    - If the service agent appears stuck or repeats a question:
    - Call the service agent again
    - Re-submit the user’s answer
    - Instruct the agent to advance to the next question

    ---

    # Golden Rule

    You are NOT an eligibility engine.
    You are a strict relay between the user and the benefit service agent.
    """,
    tools=[(AgentTool(universal_credit_agent)), save_current_questionnaire, get_answers],
    output_schema=BuddyToElicitation
)

buddy_sequential_agent = SequentialAgent(
    name="CodePipelineAgent",
    sub_agents=[buddy, elicitation_agent],
    description="Executes a sequence of eligibility mediation and elicitation of responses into JSON.",
)

root_agent = buddy_sequential_agent