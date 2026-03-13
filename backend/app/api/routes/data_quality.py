from __future__ import annotations

from fastapi import APIRouter, Depends

from app.ai.service import AIService
from app.api.dependencies import get_ai_service
from app.api.models import DataQualityRequest, DataQualityResult
from app.core.auth import require_api_key
from app.services.data_quality import assess_data_quality


router = APIRouter(
    prefix="/api/validate",
    tags=["data-quality"],
    dependencies=[Depends(require_api_key)],
)


@router.post("/data-quality", response_model=DataQualityResult)
async def validate_data_quality(
    payload: DataQualityRequest,
    ai_service: AIService = Depends(get_ai_service),
) -> DataQualityResult:
    base_result = assess_data_quality(payload)
    enriched_result = await ai_service.enrich_data_quality(payload.model_dump(mode="json"), base_result)
    return DataQualityResult(**enriched_result)
