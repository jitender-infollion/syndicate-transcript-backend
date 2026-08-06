from fastapi import APIRouter, Depends, Response
from fastapi.responses import RedirectResponse

from apis.controllers.transcripts import transcripts_controller
from apis.controllers.transcripts.transcripts_schema import TranscriptFilterRequest
from apis.dependencies import get_current_user_id
from utils.pagination import PaginationParams
from utils.response import success_response

from .paths import P

router = APIRouter(prefix=P.transcripts.BASE, tags=["Transcripts"])


@router.get(P.transcripts.LIST)
def list_transcripts(
    domain: str | None = None,
    geography: str | None = None,
    params: PaginationParams = Depends(),
):
    result = transcripts_controller.list_transcripts(params, domain, geography)
    return success_response(data=result)


@router.post(P.transcripts.FILTER)
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


@router.get(P.transcripts.DOMAINS)
def list_domains():
    result = transcripts_controller.list_domains()
    return success_response(data=result)


@router.get(P.transcripts.DETAIL)
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
    return Response(
        content=result.pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="transcript-{transcript_id}.pdf"'},
    )


@router.get(P.transcripts.FULL_TEXT)
def get_full_text(transcript_id: int, user_id: int = Depends(get_current_user_id)):
    result = transcripts_controller.get_full_text(user_id, transcript_id)
    return success_response(data=result)
