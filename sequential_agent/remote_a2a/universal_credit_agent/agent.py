from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from sequential_agent.prompts import universal_credit_agent_prompt

root_agent = Agent(
    model=LiteLlm(model="bedrock/converse/openai.gpt-oss-120b-1:0"),
    name="universal_credit_agent",
    description="An agent that can determine if a user would be eligible for universal credit",
    instruction=universal_credit_agent_prompt(),
)