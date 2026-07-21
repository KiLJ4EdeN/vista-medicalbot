from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from api.dependencies import CurrentUser
from schemas.stt import SpeechToTextResponse
from services.stt import transcribe_audio

router = APIRouter(tags=["speech-to-text"])


@router.post("/stt", response_model=SpeechToTextResponse)
async def speech_to_text(
    file: Annotated[UploadFile, File()], _user: CurrentUser
) -> SpeechToTextResponse:
    return SpeechToTextResponse(text=await transcribe_audio(file))
