from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.agents.llm_agent import Agent
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH
from google.adk.tools.agent_tool import AgentTool
from google.adk.models.lite_llm import LiteLlm
from pydantic import BaseModel, Field
from google.genai import types

child_benefit_agent = RemoteA2aAgent(
    name="child_benefit_agent",
    description="Agent that can work out if someone is eligible for child benefit",
    agent_card=(f"http://localhost:8001/a2a/child_benefit_agent{AGENT_CARD_WELL_KNOWN_PATH}"),
)

class ElicitationAction(BaseModel):
    label: str = Field(description='The text to display on a user modality (i.e. a button)')
    payload: str = Field(description='The message to send to the agent if the user chooses this option - this can be more detailed than the label')

class ElicitationResponse(BaseModel):
    content: str = Field(description='The free text to display to the user - this is always required')
    actions: list[ElicitationAction]| None = None

elicitation_agent = LlmAgent(
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
    You are a user-facing agent who converts a message into a JSON object.
    You MUST use the provided schema: {ElicitationResponse.model_json_schema()}.

    The content field should contain a comprehensive summary of the message to the user, including any greetings. Ensure you maintain the tone of the original message.
    The options array should be populated if the message indicates deterministic choices (such as 'Yes' or 'No', or a list of options).
    Do not provide yes/no options if the question is open-ended.
    
    Ensure the options are capitalised correctly - they should not be all lower case or all caps.
    """,
    # this is not being enforced?
    output_schema=ElicitationResponse,
    # output_key="elicitation"
)

buddy = Agent(
    model=LiteLlm(model="bedrock/converse/openai.gpt-oss-120b-1:0"),
    # model="openai/gpt-5.1",
    name="buddy",
    description="An agent that helps users",
    instruction="""
    # Persona
    You are a helpful UK government benefit agent that mediates conversations between the user
    and other agents regarding benefit eligibility. You are fiercely protective of the user's
    data, and you answer agent questions tersely.

    # Objectives
    1. Keep specific details of your user's answers private to yourself.
    2. Reduce the amount of input required from a user to determine their benefit eligibility, i.e
    if the user has previously told you information that means you can answer a question, do so, 
    but tell the user what you're doing and get their confirmation. If you can't answer a question using 
    what you know about the user already, consult with the user to get an answer.    

    # Tasks
    1. Determine what type of benefit the user wants to check their eligibility in regards to
    2. Start a conversation with the appropriate benefits agent on the user's behalf. 
    3. Continue to mediate the discussion with a benefit agent until a decision on eligibility has been made
    by the agent.
    
    # Tools
    - For child benefit applications, use the child_benefit_agent tool
    
    # Outputs
    - You should pass any unanswerable questions on to the user verbatim
    - After considering the user's information to a question, you should only send "YES" or "NO" 
    to benefit agents

    # Examples
    - If the user tells you they have a 13 year old child, and you have been asked by an agent if the user
    has children under 16, then you should say "YES" otherwise, say "NO",
    - If an agent asks you a question that you know the answer to, then you should tell the user
    what has been asked, what you are going to respond with and why, and whether that is OK. So, if
    the user has told you that a child lives with them, and an agent asks if there are other residents 
    in the home, say to the user "The agent has asked if you have other residents in your home, I know you
    live with a child, so I am going to respond with 'YES'; is this OK with you?" 
    """,
    tools=[(AgentTool(child_benefit_agent))]
)

buddy_sequential_agent = SequentialAgent(
    name="CodePipelineAgent",
    sub_agents=[buddy, elicitation_agent],
    description="Executes a sequence of eligibility mediation and elicitation of responses into JSON.",
)

root_agent = buddy_sequential_agent