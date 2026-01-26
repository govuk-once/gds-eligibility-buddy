from typing import Literal, Dict, Any, List, Optional

from google.adk.agents.llm_agent import Agent
from google.adk.agents import SequentialAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.models.lite_llm import LiteLlm
from google.genai import types
from google.adk.tools.tool_context import ToolContext
from pydantic import BaseModel, Field

from sequential_agent.prompts import user_agent_prompt, elicitation_agent_prompt, personal_independence_payment_agent_prompt, universal_credit_agent_prompt


def update_question_and_answers(question: str, answer: str, tool_context: ToolContext ) -> Dict[str, Any]:
    questions_and_answers = tool_context.state.setdefault("questions_and_answers", {})
    print(questions_and_answers)
    questions_and_answers[question] = answer
    print(questions_and_answers)
    tool_context.state["questions_and_answers"] = questions_and_answers
    
    return {
        "state": tool_context.state.to_dict()
    }


def sign_in(tool_context: ToolContext) -> None:
    questions_and_answers = tool_context.state.setdefault("questions_and_answers", {})
    questions_and_answers["Age?"] = "39"
    questions_and_answers["Salary per annum?"] = "£12,452"
    tool_context.state["questions_and_answers"] = questions_and_answers

universal_credit_agent = Agent(
    model=LiteLlm(model="bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0"),
    # model="bedrock/converse/openai.gpt-oss-120b-1:0"),
    name="universal_credit_agent",
    description="An agent that can determine if a user would be eligible for universal credit",
    instruction=universal_credit_agent_prompt(),
)

personal_independence_payment_agent = Agent(
    model=LiteLlm(model="bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0"),
    # model="bedrock/converse/openai.gpt-oss-120b-1:0"),
    name="personal_independence_payment_agent",
    description="An agent that can determine the likelihood of a user being eligible for universal credit",
    instruction=personal_independence_payment_agent_prompt(),
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
        model="bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
        # response_format causes this bug with claude: https://github.com/BerriAI/litellm/issues/18381
        # response_format={
        #     "type": "json_schema",
        #     "json_schema": {
        #         "name": "response",
        #         "schema": UserAgentToElicitation.model_json_schema(),
        #         "strict": True,
        #     },
        # }
    ),
    name="user_agent",
    description="An agent that helps users",
    instruction=user_agent_prompt(UserAgentToElicitation.model_json_schema()),
    tools=[
        AgentTool(universal_credit_agent), 
        AgentTool(personal_independence_payment_agent),
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