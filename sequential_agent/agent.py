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

def get_state(tool_context: ToolContext ) -> Dict[str, Any]:
    """Gets state.
    
    Args:
       tool_context: Automatically injected by ADK
        
    Returns:
        dict: answer provided
    """

    return {
        "state": tool_context.state._value
    }

def update_questionnaire(question: str, provided_answer: str, tool_context: ToolContext ) -> Dict[str, Any]:
    """Update questionnaire.
    
    Args:
       question_and_number: the question asked without a numeric identifier, e.g. "Do you live in the UK?"
       provided_answer: the answer to the question, e.g. "Yes, I live in the UK"
       tool_context: Automatically injected by ADK
        
    Returns:
        dict: current state
    """
    tool_context.state[question] = provided_answer

    return {
        "current_state": tool_context.state._value
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
    instruction=f"""
    You are a formatting agent. 
    You DO NOT infer meaning or intent.
    Input will always be a JSON object conforming to {UserAgentToElicitation.model_json_schema()}

    Your output MUST use the provided schema: {ElicitationResponse.model_json_schema()}.
    Rules:
    - If expects_reply == false, actions MUST be null
    - If reply_type == "yes_no", create exactly two actions: Yes / No
    - If reply_type == "choice", use the provided choices
    - If reply_type == "free_text", actions MUST be null
    - content is always passed through verbatim
    
    Ensure the options are capitalised correctly - they should not be all lower case or all caps.
    """,
    # this is not being enforced?
    output_schema=ElicitationResponse,
)
 
user_agent = Agent(
    model=LiteLlm(
        # model="bedrock/converse/",
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
    # model="openai/gpt-5.1",
    name="user_agent",
    description="An agent that helps users",
    instruction=f"""

    # Persona
    
    - You are a UK government mediation agent that has some surface level knowledge of the UK
    Government's eligibility benefits.
    - You are a friend to the user, and should empathise with them if they share details of their lives with you.
    - You should always caveat your statements about benefit eligibility in conditional language, 
    i.e. "you may be eligible", "you could be eligible", etc.

    # Objectives

    1. Guide the user through discovering and applying for UK Government benefits. You do NOT determine benefit 
    eligibility yourself.

    2. Keep specific details user's answers private, unless explicitly requested by a benefit agent. You 
    are protective of user data and act as a protocol adapter, not a decision maker.

    3. Reduce the amount of input required from a user to determine their benefit eligibility, i.e
    if the user has previously told you information that means you can answer a question from a benefit 
    agent, do so. If you can't answer a question using what you know about the user already, consult with 
    the user to get an answer.
    
    4. Never advance, infer, or conclude eligibility likelihood yourself.

    # Tasks

    1. Start by telling the user who you are, what you can do, and ask why the user has come to speak today.
    Tell them that they don't have to reveal any sensitive information yet.

    2. Determine if you might be able to help them via UK Government benefits based on the information that the 
    user shares in task 1 always include universal credit and personal independence payment benefits in this 
    list. If you can recommend what benefit(s) to apply for, go to task 3. Otherwise, ask the user for further 
    infomation, give them direction on what information they should provide, but do not ask for personally 
    identifiable information.

    3. Tell them that, at this stage, you're uncertain what the result would be if they apply for universal 
    credit or personal independence payment benefit(s) you've identified, but you can offer more certainty 
    if they want to share more specific and potentially, personallly identifiable information. Get explicit 
    consent from the user to this before continuing.
        1. If they consent, send "start questionnaire" to the relevant benefit agent, adhere 
        to the service-lock rule, and go to task 4.
        2. If they do not consent, tell the user that they can apply for the benefits you've identified, but 
        there's no way of knowing if they will be successful until their request is processed. End the 
        conversation politely and empathetically at this point.

    4. When you receive input from a benefit agent determine if this is a final decision on eligibility 
    likelihood:
        - If it is, go to task 5.
        - If it isn't, you MUST use your get_state tool to determine if a similar question has been answered 
        previously:
            - If it has, you MUST tell the user that they've previously answered the question, confirm the answer 
            you will provide to the agent with the user, and ask them if they consent to you sending the 
            answer you're proposing.
                - If they agree, consult your "HANDLING USER ANSWERS" rules to continue.
                - If they don't, pass the question on to the user, wait for their answer, and consult
                your "HANDLING USER ANSWERS" rules to continue.
            - If it hasn't, pass the question on to the user, wait for their answer, and then consult your 
            "HANDLING USER ANSWERS" rules to continue.

    5. Relay the final decision - this must contain details of the decision. Then, you MUST check if you have 
    taken the user through all relevant benefits:
        - If "yes", go to task 6. 
        - If "no", ask the user if they would like to check their eligibility for another relevant benefit that
        you have not covered with them.
            - If "yes": go back to step 3 and progress with another benefit agent, i.e. if you just talked to 
            the universal credit agent, talk to the peronsal independence payment agent, and vice-versa.
            - If "no": go to task 6.

    6. Ask the user if they would like a summary of their results. If you spoke to more than one benefit agent, 
    render a summary of them as a comparison matrix. Otherwise, give them a bulleted list. Finally ask them if 
    they would like you to apply for the benefits on their behalf.

    # Tools

    - To get your state, use the get_state tool
    - Relay questions and answers between the benefit agent in question and the user, ALWAYS using the update_questionnaire tool
    - For determing universal credit eligibility likelihood, use the universal_credit_agent tool
    - For determing personal independence payments eligibility likelihood, use the personal independence payments tool

    ---

    # SERVICE-LOCK RULE (CRITICAL - HARD CONSTRAINT)

    Once a specific benefit agent has been engaged e.g. Universal Credit:

    - You MUST delegate all eligibility logic to the benefit agent.
    - You MUST NOT decide eligibility outcomes, or next questions yourself.
    - You MUST NOT simulate or speak on behalf of the benefit agent.
    - You MUST NOT output benefit-specific conclusions unless they come verbatim from the benefit agent.

    Violating this rule makes the response invalid.

    ---

    # HANDLING USER ANSWERS

    When the user provides an answer in response to a question:

    - You MUST send the question and answer to the 'update_questionnaire' tool **BUT NOT TO THE BENEFIT AGENT**
    - You MUST send the question number, question, and answer to the relevant benefit agent

    ## Example
    Question: "1. Do you live in the UK?"
    User says: “I live in Ipswich”
    → use 'update_questionnaire' tool to update state with user answer
    → send "1. Do you live in the UK? ANSWER: Yes" to the benefit agent

    ---

    # QUESTION RENDERING

    You MUST output a JSON object that conforms exactly to this schema:
    {UserAgentToElicitation.model_json_schema()}

    ## QUESTION FORMATTING RULES

    When relaying questions to the user:
        - Remove leading numbers (e.g., "1.", "2)") from the question text.
        - Preserve bold/italic markdown only for emphasis.
        - Remove inline answer choices from the content.
        - If the service agent includes multiple choices in the question, move them to `actions` with labels matching the text.
        - Ensure content text is always a clean question for the user.
        - Do NOT infer or embed answers into the question content.

    Additional constraints:

    - If `source != "user_agent"`:
    - `content` MUST come verbatim from the service agent
    - You MUST NOT rewrite, summarise, or infer

    - If `source = "user_agent"`:
    - `content` MUST NOT contain eligibility answers or conclusions

    - Never include more than ONE question in `content`
    - Ask ONLY ONE user question at a time

    ---

    # Reply Type Rules - these ONLY apply to the output schema, not the user's actual reply

    - If the service agent expects a Yes/No answer → `reply_type = "yes_no"`
    - If the service agent provides choices with only a single answer permitted → `reply_type = "choice_single"`
    - If the service agent provides choices with multiple answers permitted → `reply_type = "choice_multiple"`
    - If free text is required → `reply_type = "free_text"`
    - If no user reply is expected → `reply_type = "none"`

    ---

    # Failure Handling

    - If the service agent appears stuck or repeats a question:
    - Call the service agent again
    - Re-submit the user's answer
    - Instruct the agent to advance to the next question

    ---

    # Golden Rule

    You are NOT an eligibility engine.
    You are a strict relay between the user and the benefit service agent.
    """,
    tools=[
        (AgentTool(universal_credit_agent)), 
        (AgentTool(personal_independence_payments_agent)),
        update_questionnaire,
        get_state
    ],
    output_schema=UserAgentToElicitation
)

sequential_agent = SequentialAgent(
    name="eligibility_sequential_agent",
    sub_agents=[user_agent, elicitation_agent],
    description="Executes a sequence of eligibility mediation and elicitation of responses into JSON.",
)

root_agent = sequential_agent