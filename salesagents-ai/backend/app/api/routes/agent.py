"""Agent configuration route (Step 7: config values, never LLM decided)."""

from fastapi import APIRouter

from app.api.schemas import AgentConfigResponse
from app.core.config import settings

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/config", response_model=AgentConfigResponse)
def get_agent_config() -> AgentConfigResponse:
    return AgentConfigResponse(
        agent_name=settings.AGENT_NAME,
        agent_gender=settings.AGENT_GENDER,
        company_name=settings.COMPANY_NAME,
    )
