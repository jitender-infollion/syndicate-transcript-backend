from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from apis.controllers.transcripts import transcripts_controller
from apis.controllers.transcripts.transcripts_schema import TranscriptFilterRequest
from apis.dependencies import get_current_user_id
from apis.rate_limiting.dependencies import rate_limit_transcripts_public
from utils.pagination import PaginationParams
from utils.response import pdf_response, success_response

from .paths import P

router = APIRouter(prefix=P.transcripts.BASE, tags=["Transcripts"])


@router.get(P.transcripts.LIST, dependencies=[Depends(rate_limit_transcripts_public)])
def list_transcripts(
    domain: str | None = None,
    geography: str | None = None,
    params: PaginationParams = Depends(),
):
    result = transcripts_controller.list_transcripts(params, domain, geography)
    return success_response(data=result)


@router.post(P.transcripts.FILTER, dependencies=[Depends(rate_limit_transcripts_public)])
def filter_transcripts(filters: TranscriptFilterRequest):
    result = transcripts_controller.filter_transcripts(filters)
    return success_response(data=result)


@router.get(P.transcripts.MY_PURCHASED)
def list_purchased_transcripts(
    params: PaginationParams = Depends(),
    user_id: int = Depends(get_current_user_id),
):
    result = transcripts_controller.list_purchased_transcripts(user_id, params)
    return success_response(data=result)


@router.get(P.transcripts.DOMAINS, dependencies=[Depends(rate_limit_transcripts_public)])
def list_domains():
    result = transcripts_controller.list_domains()
    return success_response(data=result)


@router.get(P.transcripts.DETAIL, dependencies=[Depends(rate_limit_transcripts_public)])
def get_transcript_detail(transcript_id: int):
    result = transcripts_controller.get_transcript_detail(transcript_id)
    return success_response(data=result)


@router.get(P.transcripts.VIEW)
def view_transcript(transcript_id: int, user_id: int = Depends(get_current_user_id)):
    result = transcripts_controller.get_transcript_access(user_id, transcript_id, mode="view")
    return success_response(data=result)


@router.get(P.transcripts.DOWNLOAD)
def download_transcript(transcript_id: int, user_id: int = Depends(get_current_user_id)):
    result = transcripts_controller.download_transcript(user_id, transcript_id)
    if result.redirect_url:
        return RedirectResponse(url=result.redirect_url, status_code=307)
    return pdf_response(result.pdf_bytes, f"transcript-{transcript_id}.pdf", disposition="attachment")


@router.get(P.transcripts.FULL_TEXT)
def get_full_text(transcript_id: int, user_id: int = Depends(get_current_user_id)):
    result = transcripts_controller.get_full_text(user_id, transcript_id)
    return success_response(data=result)
