from google.adk.agents.llm_agent import Agent
import os
import json
from typing import Any
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from typing import Any
from google.adk.agents import Agent
from a2a.types import AgentCard
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.tool_context import ToolContext

from dotenv import load_dotenv
load_dotenv()

known_agent_cards: list[AgentCard] = []
known_agents: list[AgentTool] = []

# TODO: make this a database call instead.
# NOTE: Depending on the path you start an ADK server up from, this may fail. It WILL work if you start
#       an ADK server using the `start_eligibility_discovery.sh` script
agent_card_path = f"{os.getcwd()}/root/taxation/agent_cards"
for agent_card_file in [file for file in os.listdir(agent_card_path) if file.endswith('.json')]:
    with open(f"{agent_card_path}/{agent_card_file}") as json_file:
        agent_card_json: dict[str, Any] = json.load(json_file)
        agent_card: AgentCard = AgentCard(**agent_card_json)

        known_agent_cards.append(agent_card)
        known_agents.append(AgentTool(RemoteA2aAgent(
            name=agent_card_json['name'],
            agent_card=agent_card
        )))

def get_known_agent_cards() -> list[AgentCard]:
    return known_agent_cards

def currently_talking_to(agent_name: str, tool_context: ToolContext):
    tool_context.state.setdefault("currently_talking_to", "")
    tool_context.state["currently_talking_to"] = agent_name

def update_most_recent_question(question_number: int, question_text: str, tool_context: ToolContext):
    most_recent_question = tool_context.state.setdefault("most_recent_question", {})
    most_recent_question: dict[str, str | int] = { "number": question_number, "text": question_text }
    tool_context.state["most_recent_question"] = most_recent_question
        
root_agent = Agent(
    model=LiteLlm(model="bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0"),
    name="taxation_agent",
    description="A gateway agent to the taxation domain for UK government",
    instruction="""
    # Persona
    
    You are a helpful UK government gateway agent that is an expert in identifying and relaying conversations
    between specialist taxation agents.

    # Objectives

    1. Identify what agents may be most applicable to service any input received
    2. Engage with the agents identified in the way they stipulate via their agent cards (you act as an
    adapter between input received and output to agents identified)
    3. Pass any responses from identified agents back to the caller, unfiltered.

    # Tasks
    
    **CRITICAL: ONLY CONSIDER AGENT CARDS RETRIEVED BY YOUR `get_agent_cards` tool!**

    1. Check if state['currently_talking_to'] == ""
        - If so, go to step 2.
        - If not, check if state['most_recent_question'] is {}
            - If so, send the user message on via the AgentTool that maps to the name returned by state['currently_talking_to'].
            - If not, take the input received along with the result of state['most_recent_question'], and use the
            AgentTool that maps to the name returned by state['currently_talking_to'], to determine how to construct 
            a message to that agent. Finally, send the message to the state['currently_talking_to'] agent using its AgentTool.
            If the agent's response indicates a final decision, set state['most_recent_question'] = {}, and 
            state['currently_talking_to'] = "".

    3. Determine what agent known to you would be applicable to service the input received by using your `get_known_agent_cards` 
    tool to retrieve agent cards known to you. 
        - Use the values of each card's `name`, `description`, `capabilities`, and `skills` 
        keys to determine how applicable they are in addressing the user's request. 
        - Select the `name` of the most applicable
        - Pass the `name` to your `currently_talking_to` tool
        - Contact the relevant agent via its AgentTool and use the `skills.examples` value to help format your request
    
    # Tools

    - Use your `get_known_agent_cards` tool to retrieve agent cards known to you.
    - Use your `update_most_recent_question` tool to save the last question that came from an agent identified via an agent card.

    """,
    tools=[get_known_agent_cards, *known_agents, currently_talking_to, update_most_recent_question]
    
)

a2a_app = to_a2a(root_agent, port=8003)