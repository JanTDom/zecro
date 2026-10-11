from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ..models.schemas import StoryInput, PagePlan
from ..models.database import db
from ..engine.page_planner import plan_page, validate_page_plan
router=APIRouter(prefix='/projects',tags=['page-plan'])
class PlanRequest(BaseModel):
    stories: list[StoryInput] = Field(default_factory=list)
    page_zone: str = 'front_page'
@router.post('/{project_id}/page-plan',response_model=PagePlan)
def calculate_page_plan(project_id: str, request: PlanRequest):
    dna=db.get_title_dna(project_id)
    if not dna: raise HTTPException(status_code=404,detail='Title DNA not found')
    plan=plan_page(dna,request.stories,page_zone=request.page_zone)
    errors=validate_page_plan(plan,request.stories)
    if errors: plan.status='invalid'; plan.warnings.extend(errors)
    return plan
