"""옵시디언풍 "위키" 노트 CRUD + AI 위키 정리.

ontology.py만큼 얇은 라우터 — 로직은 repository.py(저장)와 ai_agent.py(AI 정리)에 있고,
여기는 그걸 그대로 REST로 노출만 한다. AI 채팅에서의 노트 추가/수정(propose_add_note 등)은
chat.py의 제안(propose) 흐름을 타므로 이 파일과는 별개 경로다.
"""

import ai_agent
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app import auth, repository as repo

router = APIRouter(dependencies=[Depends(auth.인증_확인)], prefix="/api/notes")


class _노트_생성_요청(BaseModel):
    제목: str
    내용: str = ""
    태그: str = ""


class _노트_수정_요청(BaseModel):
    제목: str | None = None
    내용: str | None = None
    위키_내용: str | None = None
    태그: str | None = None


@router.get("")
def 노트_목록():
    return repo.노트_목록_불러오기()


@router.post("")
def 노트_생성(요청: _노트_생성_요청):
    새_id = repo.노트_생성(요청.제목, 요청.내용, 요청.태그)
    return {"id": 새_id}


@router.get("/{note_id}")
def 노트_상세(note_id: int):
    노트 = repo.노트_불러오기(note_id)
    if not 노트:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다.")
    return 노트


@router.put("/{note_id}")
def 노트_수정(note_id: int, 요청: _노트_수정_요청):
    변경필드 = {k: v for k, v in 요청.model_dump().items() if v is not None}
    repo.노트_수정(note_id, 변경필드)
    return {"ok": True}


@router.delete("/{note_id}")
def 노트_삭제(note_id: int):
    repo.노트_삭제(note_id)
    return {"ok": True}


@router.post("/{note_id}/organize")
def 노트_위키_정리(note_id: int):
    노트 = repo.노트_불러오기(note_id)
    if not 노트:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다.")
    if not (노트.get("내용") or "").strip():
        raise HTTPException(status_code=400, detail="정리할 내용이 없습니다.")
    위키_내용 = ai_agent.노트_위키_정리(노트["내용"])
    return {"위키_내용": 위키_내용}
