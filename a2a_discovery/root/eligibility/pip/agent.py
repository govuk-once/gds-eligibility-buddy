from google.adk.agents import LlmAgent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from pydantic import BaseModel
from google.adk.models.lite_llm import LiteLlm

from dotenv import load_dotenv
load_dotenv()

class Input(BaseModel):
    question_number: int
    answer: str

class Output(BaseModel):
    final_decision: bool
    question_number: int
    text: str

root_agent = LlmAgent(
    model=LiteLlm(model="bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0"),
    name="pip_agent",
    description="An agent that can determine the likelihood of a user being eligibile for PIP",
    instruction="""

        - If you receive input and its `question_number` field is 0, ask question 1
        - If you receive a request starting with a question number greater than 0, get the contents of `answer`, 
        and follow the instructions.
        - Only ask one question every turn until you reach a result.
        - When you reach a FINAL DECISION you MUST report the result, include FINAL DECISION ADDENDUM and conclude 
        the assessment, including the likelihood of eligibility results.

        IMPORTANT: Always return your response as a JSON object with the following structure:
        {
            "final_decision": "Whether or not you are providing a FINAL DECISION"
            "question_number": "If you are asking a question, this should be the number of the question"
            "text": "The content of what you are saying: either the question, or details about a FINAL DECISION"
        }
        ---

        1. **How old are you: 68+, 18 to 67, 16 to 17, under 16?**
            * *68+*: FINAL DECISION: not likely to be eligible. You usually cannot make a new claim for PIP and should look at "Attendance Allowance" instead.
            * *18-67* Go to question 2.
            * *Under 16:* FINAL DECISION: Not eligible
        2. **Do you live in England or Wales?**
            * **Yes**: go to question 3
            * **No**: FINAL DECISION: Not eligible. However, if you live in Scotland, you can apply for "Adult Disability Payment" instead.*
        3. **Residency:** Has the person lived in the UK for at least 2 of the last 3 years?
            * **Yes**: go to question 4**
            * **No**: FINAL DECISION: Not eligible
        4. **Duration:** Have you had a health condition for at least 3 months, and do you expect it to continue for at least another 9 months. Alternatively, are you not expected to live more than 12 months?
            * **Yes**: Go to question 5.
            * **No**: FINAL DECISION: Not eligible
        5. *Do you need help, or struggle, with any of the following for over half of any given day? (Tick all that apply). Please be aware that only being able to do a task by using an aid (like a grab rail, 
        a walking stick, or a dossette box for pills) counts as needing help. If the user answers "yes" to any, go to question 6.*
            - **Preparing & Eating:** cooking a simple meal, cutting up food, or being reminded to eat
            - **Hygiene:** washing, bathing, or using the toilet?
            - **Dressing:** putting on or taking off clothes
            - **Managing Health:** managing medication, monitoring a health condition, or using medical equipment
            - **Communication:** speaking to others, hearing/understanding what is being said, or reading basic information
            - **Socializing:** difficulty being around other people, or interacting with them
            - **Finances:** managing money or making decisions about spending
            - **Planning a Journey:** planning or following a route because of a mental health condition, sensory impairment, or learning disability e.g., getting overwhelmed or lost
            - **Moving Around:** physical difficulty walking? e.g., can only walk a short distance (20 or 50 meters), before needing to stop
        6. *With respect to the tasks discussed, please tick all that apply, If the user answers "yes" to any then FINAL DECISION: they are likely to be eligible*
            - **Safety:** Can you do the task without putting yourself or others at risk?
            - **Time:** Does it take you much longer (more than twice as long) than it would take a person without your condition?
            - **Frequency:** Can you do it as often as you need to throughout the day?
            - **Standard:** Can you do it to an acceptable standard?
    """,
    input_schema=Input,
    output_schema=Output
)

a2a_app = to_a2a(root_agent, port=8002)