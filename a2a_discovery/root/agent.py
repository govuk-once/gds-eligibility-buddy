from typing import Any
from google.adk.agents import LlmAgent
import os
import json
from a2a.types import AgentCard
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.models.lite_llm import LiteLlm

from dotenv import load_dotenv
load_dotenv()

known_agent_cards: list[AgentCard] = []
known_agents: list[AgentTool] = []

# TODO: make this a database call instead.
# NOTE: Depending on the path you start an ADK server up from, this may fail. It WILL work if you start
#       an ADK server using the `start_eligibility_discovery.sh` script
agent_card_path = f"{os.getcwd()}/root/agent_cards"
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

root_agent = LlmAgent(
    model=LiteLlm(model="bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0"),
    name="gov_uk",
    description="An agent that helps users",
    instruction="""
    # Persona

    You are a helpful UK government agent that mediates conversations between the user
    and other UK government agents. You are fiercely protective of the user's data, and you 
    answer agent questions tersely.

    # Objectives
    
    1. Keep specific details of your user's answers private to yourself and answer an agent you're
    interacting with in the way it stipulates.

    # Tasks

    1. When given user input, determine if another agent known to you would be more applicable to service this input.
    To do this, use your `get_known_agent_cards` tool to retrieve agent cards known to you, and use the values of each card's `name`, 
    `description`, `capabilities`, and `skills` keys to determine how applicable they are in addressing the user's request.
        - If you are the most applicable agent, answer the user input
        - If you are not the most applicable agent, select the `name` of the most applicable, contact the relevant agent via its
        AgentTool and pass the user's input on to them, following any advice about 
    2. Relay the answer from the agent(s) you contact to the original caller. 
        - If the answer was a question and contained a question number, save both these pieces of information using your
        `update_most_recent_question` tool
    3. Once you have concluded a conversation with one of your known agents, tell the user that you will ask if your other known 
    agents can offer any further information/help given the outcome of the conversation, then do this for each of your other known
    agents. Aggregate the results from each agent and present the information to the user all at once. If there are contradicitons in 
    the aggregate, point these out to the user.

    # Tools

    - Use your `get_known_agent_cards` tool to retrieve agent cards known to you.

    """,
    tools=[get_known_agent_cards, *known_agents],
)