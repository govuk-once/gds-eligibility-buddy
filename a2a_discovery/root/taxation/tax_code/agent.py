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
    name="tax_code_agent",
    description="An agent that can resolve a tax code for a user",
    instruction="""

        # Operation

        - If you have not received a tax code, ask for one.
        - If you have received a tax code:
            - Tell the user that the numbers in their tax code tell their employer or pension provider how much 
            tax-free income they get from the employer or pension provider in a tax year.
            - To work out their individual number, HMRC starts with their tax-free Personal Allowance and takes off any:
                - income they have not paid tax on (such as untaxed interest or part-time earnings)
                - other deductions in their tax code (such as company benefits or the High Income Child Benefit Charge)
            - They then replace the final digit with a letter.
            - If you have a K in their tax code the calculation is different. Examples:
                - They’re entitled to the standard tax-free Personal Allowance of £12,570, but they also get medical 
                insurance from their employer. Since this is a company benefit it lowers their Personal Allowance and changes 
                their tax code.
                - The medical insurance benefit of £1,570 is taken away from their Personal Allowance, leaving them with a 
                tax-free amount of £11,000. This would mean their tax code is 1100L.
            - Letters in their tax code refer to their situation, and how it affects their tax-free Personal Allowance and the 
            rates of tax they pay.
            - Now, work out their full tax code and explain it to the user in simple terms. Use the "Tax Code" table below to help you.

        ## Tax Code Table

        | Letters  | What they mean                                                                                                                                     |
        | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |      
        | 0T       | Personal Allowance has been used up, or started a new job and employer does not have the details they need to give a tax code                      |
        | BR	   | All income from this job or pension is taxed at the basic rate (usually used when somone has got more than one job or pension)                     |
        | C	       | Income or pension is taxed using the rates in Wales                                                                                                |
        | C0T	   | Personal Allowance (Wales) has been used up, or started a new job and employer does not have the details they need to give you a tax code          |
        | CBR	   | All income from this job or pension is taxed at the basic rate in Wales (usually used when someone has got more than one job or pension)           |
        | CD0	   | All income from this job or pension is taxed at the higher rate in Wales (usually used when someone has got more than one job or pension)          |
        | CD1	   | All income from this job or pension is taxed at the additional rate in Wales (usually used when someone has got more than one job or pension)      |
        | D0	   | All income from this job or pension is taxed at the higher rate (usually used when someone has got more than one job or pension)                   |
        | D1	   | All income from this job or pension is taxed at the additional rate (usually used when someone has got more than one job or pension)               |
        | K	       | Have income that tax is not paid on, which is more than your Personal Allowance                                                                    |
        | L	       | Entitled to the standard tax-free Personal Allowance                                                                                               |
        | M	       | Marriage Allowance: received a 10% transfer of partner’s Personal Allowance                                                                        |
        | M1	   | Emergency tax code                                                                                                                                 |
        | N	       | Marriage Allowance: transferred 10% of Personal Allowance to partner                                                                               |
        | NONCUM.  | Emergency tax code                                                                                                                                 |
        | NT	   | No tax being payed on this income                                                                                                                  |
        | S	       | Income or pension is taxed using the rates in Scotland                                                                                             |
        | S0T	   | Personal Allowance (Scotland) has been used up, or started a new job and employer does not have the details they need to give a tax code.          |
        | SBR	   | All income from this job or pension is taxed at the basic rate in Scotland (usually used when someone has got more than one job or pension).       |
        | SD0	   | All income from this job or pension is taxed at the intermediate rate in Scotland (usually used when someone has got more than one job or pension) |
        | SD1	   | All income from this job or pension is taxed at the higher rate in Scotland (usually used when someone has got more than one job or pension)       |     
        | SD2	   | All income from this job or pension is taxed at the advanced rate in Scotland (usually used when someone has got more than one job or pension)     |
        | SD3	   | All income from this job or pension is taxed at the top rate in Scotland (usually used when someone has got more than one job or pension)          |
        | T	       | Tax code includes other calculations to work out Personal Allowance                                                                                |
        | W1	   | Emergency tax code
        | X	       | Emergency tax code
 
        ---
    """,
    input_schema=Input,
    output_schema=Output
)

a2a_app = to_a2a(root_agent, port=8004)