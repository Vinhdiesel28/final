from typing import Literal
from pydantic import Field
from services.agent_llm import Object

class Plan(Object):
    intent:Literal['knowledge','personal_guidance','prediction','statistics','unsafe','out_of_scope']
    goal:str
    queries:list[str] = Field(max_length=2)
    clarification_questions:list[str] = Field(max_length=2)
    can_answer_general:bool
    requested_sources:list[str]

class Claim(Object):
    text:str
    evidence_id:str
    quote:str

class Draft(Object):
    claims:list[Claim] = Field(max_length=3)
    followup_questions:list[str] = Field(max_length=2)
    evidence_sufficient:bool
    missing_information:str

class Critique(Object):
    action:Literal['accept','revise','retrieve_again','clarify','abstain']
    answers_question:bool
    all_claims_supported:bool
    reasons:list[str]
    revised_query:str
    followup_questions:list[str]
