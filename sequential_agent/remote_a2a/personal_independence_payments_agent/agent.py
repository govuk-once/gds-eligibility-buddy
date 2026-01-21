from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from sequential_agent.prompts import personal_independence_payment_agent_prompt

root_agent = Agent(
    model=LiteLlm(model="bedrock/converse/openai.gpt-oss-120b-1:0"),
    name="universal_credit_agent",
    description="An agent that can determine the likelihood of a user being eligibile for universal credit",
    instruction=personal_independence_payment_agent_prompt(),
)