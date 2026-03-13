from __future__ import annotations

from fastapi import APIRouter, Depends

from app.ai.service import AIService
from app.api.dependencies import get_ai_service
from app.api.models import MedicationReconcileRequest, ReconciliationResult
from app.core.auth import require_api_key
from app.services.reconciliation import reconcile_medication_request


router = APIRouter(
    prefix="/api/reconcile",
    tags=["reconcile"],
    dependencies=[Depends(require_api_key)],
)


@router.post("/medication", response_model=ReconciliationResult)
async def reconcile_medication(
    payload: MedicationReconcileRequest,
    ai_service: AIService = Depends(get_ai_service),
) -> ReconciliationResult:
    base_result = reconcile_medication_request(payload)
    enriched_result = await ai_service.enrich_reconciliation(payload.model_dump(mode="json"), base_result)
    return ReconciliationResult(**enriched_result)
