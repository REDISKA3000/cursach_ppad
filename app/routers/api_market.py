import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.role_relevance import RoleRelevancePipelineResult, RoleRelevanceRequest
from app.services.role_relevance_pipeline import run_role_relevance_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/market/role-relevance", response_model=RoleRelevancePipelineResult)
def role_relevance(request: RoleRelevanceRequest, db: Session = Depends(get_db)):
    return run_role_relevance_pipeline(
        db,
        target_role=request.target_role,
        limit=request.limit,
        use_llm_reranker=request.use_llm_reranker,
    )
