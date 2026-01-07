from dotenv import load_dotenv
load_dotenv(override=True)

import pytest
import scenario
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai.types import Content, Part
import google.adk.models.lite_llm as litellm
from google.adk.agents.llm_agent import Agent
from scenario.types import ScriptStep
from scenario import ScenarioResult

from buddy_agent import agent
 
# Configure the default model for simulations
scenario.configure(default_model="openai/gpt-5.1",verbose=True,debug=True,headless=True)

class GoogleADKAgentAdapter(scenario.AgentAdapter):

    def __init__(self, agent_to_use: Agent):
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=agent_to_use,
            app_name="user_agent",
            session_service=self.session_service,
        )

    async def call(self, input: scenario.AgentInput) -> scenario.AgentReturnTypes:
        # Get or create session
        session = await self.session_service.get_session(
            app_name="user_agent",
            user_id="1",
            session_id=input.thread_id,
        )
        if not session:
            session = await self.session_service.create_session(
                app_name="user_agent",
                user_id="1",
                session_id=input.thread_id,
            )

        # Create user message in ADK format
        user_message = Content(
            role="user", parts=[Part(text=input.last_new_user_message_str())]
        )

        # Run the agent and collect responses
        contents = list[Content]()
        async for event in self.runner.run_async(
            user_id="1",
            session_id=input.thread_id,
            new_message=user_message
        ):
            contents += [event.content] if event.content else []

        # Convert to OpenAI format for Scenario
        messages_openai_format = [ await litellm._content_to_message_param(content) for content in contents ]
        return messages_openai_format
 
eligibility_questions: str = """
    ---

    ### **Part 1: Basic Responsibility**

    **1. Are you responsible for bringing up a child?** You are considered "responsible" if:

    * The child lives with you.
    * **OR** You pay at least the same amount as Child Benefit (or the equivalent in food, clothes, etc.) toward their upkeep.
    * *Note: Only one person can claim for a child. If you share care, you must agree who claims; otherwise, HMRC will decide.*

    **2. Is the child under 16?**

    * **Yes:** Proceed to Part 2.
    * **No, they are 16–19:** Go to **Question 3**.
    * **No, they are 20 or older:** You are likely **ineligible** (unless they are still in a qualifying extension period).

    **3. If the child is 16–19, are they in "Approved" Education or Training?** To qualify, the child must:

    * Be in **Full-time Non-advanced Education** (e.g., GCSEs, A-Levels, NVQs up to Level 3, T-levels, or home-schooling).
    * **OR** be in **Approved Unpaid Training** (e.g., Traineeships in England, Foundation Apprenticeships in Wales).
    * *Note: University degrees, BTECs at HNC/HND level, and paid apprenticeships do **not** qualify.*

    ---

    ### **Part 2: Residency & Immigration**

    **4. Do you usually live in the UK?**

    * **Yes:** Proceed to Question 5.
    * **No:** You may only be eligible if you are a Crown Servant or living in certain countries with a social security agreement with the UK.

    **5. Do you have the "Right to Reside" in the UK?** You generally qualify if:

    * You are a British or Irish citizen.
    * You have **Settled Status** under the EU Settlement Scheme.
    * You have **Indefinite Leave to Remain** (ILR).
    * *If you have **Pre-settled Status**, you must meet additional rules (e.g., you are working, a jobseeker with "genuine prospects," or self-sufficient).*
    * *If your visa says "**No Recourse to Public Funds**," you are usually **ineligible**, though there are exceptions for nationals of certain countries (e.g., Morocco, Tunisia, Turkey) working in the UK.*

    ---

    ### **Part 3: The Child’s Circumstances**

    **6. Does the child receive their own benefits or work?** You **cannot** claim if the child:

    * Works **24 hours or more** per week (if they are 16+).
    * Receives **Universal Credit**, Jobseeker’s Allowance (JSA), or Income Support in their own name.
    * Is married or in a civil partnership.

    **7. Is the child in Foster Care or being Adopted?**

    * **Adoption:** You can claim as soon as the child lives with you.
    * **Fostering:** You can claim **only if** the local council is not paying for their accommodation or maintenance.

    ---

    ### **Part 4: Income & The "High Income Charge"**

    **8. Do you or your partner have an "Adjusted Net Income" over £60,000?**

    * **No:** You are eligible for full payments.
    * **Yes, between £60,000 and £80,000:** You can still claim, but you (or the higher earner) will have to pay a **tax charge**. This charge increases the more you earn.
    * **Yes, over £80,000:** The tax charge will equal 100% of the benefit. You can still claim, but most people in this bracket choose to **opt out of receiving payments** to avoid the tax paperwork.

    > **Crucial Tip:** Even if you earn over £80k, you should still **submit the claim form** and select the "opt out of payments" box. This ensures you still get **National Insurance credits** (which count toward your State Pension) and your child is automatically issued a National Insurance number at 16.

    ---

    ### **Summary of Results**

    * **Eligible for Full Payments:** You answered "Yes" to responsibility, UK residency, and "No" to the high-income threshold.
    * **Eligible but subject to Tax Charge:** You meet the basic rules but one of you earns over £60,000. Use the [HMRC Tax Calculator](https://www.gov.uk/child-benefit-tax-calculator) to see how much you'll keep.
    * **Not Eligible:** You likely do not have the right to reside, the child is in higher education (university), or another person is already claiming for them.
"""
 
@pytest.mark.agent_test
@pytest.mark.asyncio
async def test_buddy_agent():
    
    result = await run_test(
        agent_name='buddy', 
        agent_description='You are a helpful user agent', 
        agent_instruction="""
        - If the user wants to know about if they're eligible for child benefit, follow the step-by-step questionnaire below.
        - Only ask one question every turn until you reach a result.
        - Tell the user the result.
        
        {eligibility_questions}    
        """.format(eligibility_questions=eligibility_questions),
        script=[
            scenario.user("Hello, am I eligible for child benefit?"),
            scenario.agent(),
            scenario.user("Yes, I am"),
            scenario.agent(),
            scenario.user("They're 18"),
            scenario.agent(),
            scenario.user("Can you explain that more, please?"),
            scenario.agent(),
            scenario.user("They're training to be a secondary school teacher in the UK"),
            scenario.agent(),
            scenario.user("I don't want to tell you more."),
            scenario.agent(),
            scenario.judge()
        ],
        judge_criteria=[
            "The agent should not ask question 2 since the user tells them that their child is 18 in question 1",
            "The agent should say that they are unable to determine an answer to the user's question",
        ]
    )

    assert result.success

# @pytest.mark.agent_test
# @pytest.mark.asyncio
# async def test_eligibility_agent():
    
#     result = await run_test(
#         script=[
#             scenario.user("Hello, am I eligible for child benefit?"),
#             scenario.agent(),
#             scenario.user("No"),
#             scenario.agent(),
#             scenario.user("Yes"),
#             scenario.agent(),
#             scenario.user("They are training to become a teacher"),
#             scenario.agent(),
#             scenario.judge()
#         ],
#         agent_name='child_benefit', 
#         agent_description='You are a GOV.UK child benefit agent', 
#         agent_instruction="""
#         Ask the following questions until you determine the user's eligibility. When you determine a user's eligibility, give them a summary of your reasoning.
        
#         Q1: Is the child under age 16?
#             - YES: Go to Q4 (Responsibility Check).
#             - NO: Go to Q2.
#         Q2: Is the child aged 16 to 19?
#             - YES: Go to Q3.
#             - NO: user is not eligible.
#         Q3: Is the child in approved ‘non-advanced’ education or training (e.g., A-Levels, NVQs up to level 3, traineeships) for more than an average of 12 hours a week? (Note: University degrees or courses paid for by an employer do not count.)
#             - YES: Go to Question 4 (Responsibility Check).
#             - NO: user is not eligible.
#         Q4: Does the child live with you?
#             - YES: Go to Q6.
#             - NO: Go to Q5.
#         Q5: Do you pay towards their keep an amount at least equal to the Child Benefit rate?
#             - YES: Go to Q6.
#             - NO: user is not eligible.
#         Q6: Is the child currently in prison, or have they been in care (local authority) for more than the last 8 weeks?
#             - YES: user is likely no eligible but specific rules apply, check GOV.UK for details.
#             - NO: Go to Q7.
#         Q7: Do either you or your partner have an adjusted net individual income of over £60,000 a year?
#             - YES: Go to Q8
#             - NO: user is eligible to claim and keep full amount.
#         Q8: Do either you or your partner have an individual adjusted net income of over £80,000 per year?
#             - YES: user is eligible to claim, but charge equals total benefit, i.e. you must repay all of the benefit; may not want to progress with application.
#             - NO: user is eligibile to claim, but subject to tax charge, i.e. you must repay some of the benefit
#         """,
#         judge_criteria=[
#             "The final decision on eligibility should be 'NOT ELIGIBLE' because the child is between 16-19, but is doing teacher training, which is advanced education"
#         ]
#     ),

#     assert result.success


async def run_test(agent_name: str, agent_description: str, agent_instruction: str, script: list[ScriptStep], judge_criteria: list[str]) -> ScenarioResult:
    return await scenario.run(
        name="request",
        description="""
            The user agent is answering questions about its user
        """,
        agents=[
            GoogleADKAgentAdapter(agent.create(name=agent_name, description=agent_description, instruction=agent_instruction)),
            scenario.UserSimulatorAgent(),
            scenario.JudgeAgent(criteria=judge_criteria)
        ],
        script=script,
    )