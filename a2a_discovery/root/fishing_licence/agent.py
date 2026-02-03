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
    name="fishing_licence_agent",
    description="An agent that can determine the likelihood of a user being eligibile for a fishing licence",
    instruction="""
        - If you receive input and its `question_number` field is 0, ask question 1. Otherwise, if you are asked a general 
        question, please answer it to the best of your ability.
        - If you receive a request starting with a question number greater than 0, get the contents of `answer`, 
        and follow the instructions.
        - Only ask one question every turn until you reach a result. Include any notes with the question. Please do
        not relay any of your instructions regarding how you should interpret an answer
        - If the answer to a question doesn't yield another question, report the answer as a result and conclude the assessment

        IMPORTANT: Always return questions as a JSON object with the following structure:
        {
            "question_number": "If you are asking a question, this should be the number of the question"
            "text": "The content of what you are saying: either the question, or details about a FINAL DECISION"
        }

        ## Concession Criteria

        If some one meets any of the following criteria, they are eligible for a concession on their fishing licence

        - Aged 66 or older
        - Have a Blue Badge (or meet eligibility criteria)
        - Receive Personal Independence Payment (PIP)
        - Receive Disability Living Allowance (DLA)
        
        ---

        1. How old is the person fishing?
            - 12 years old or younger: You do not need to buy a licence.
            - 13 to 16 years old: The price is Free. (You must still register for a Junior licence online).
            - 17 years old or older: Go to 2.
        2: How long do you want the licence to last?
            - 1 Day: Go to 3.
            - 8 Days: Go to 4.
            - 12 Months: Go to 5.
        3: What type of fishing and rod limit do you require? _Note:_ 3-rod licences are not available for 1-day durations.
            - Trout and coarse (up to 2 rods): £7.30
            - Salmon and sea trout: £13.50 
        4: What type of fishing and rod limit do you require? _Note:_ 3-rod licences are not available for 8-day durations.
            - Trout and coarse (up to 2 rods): £14.70
            - Salmon and sea trout: £30.50
        5: (For 12-Month Licences) Do you meet ANY of the concession criteria? List these for the user. 
            - If so, go to 6
            - If not go to 7.
        6: (Concession 12-Month) What type of fishing and rod limit do you require?
            - Trout and coarse (up to 2 rods): £24.50
            - Trout and coarse (up to 3 rods): £36.80
            - Salmon and sea trout: £62.00
        7: (Standard 12-Month) What type of fishing and rod limit do you require?
            - Trout and coarse (up to 2 rods): £36.80
            - Trout and coarse (up to 3 rods): £55.30
            - Salmon and sea trout: £93.10
"""
)

a2a_app = to_a2a(root_agent, port=8005)