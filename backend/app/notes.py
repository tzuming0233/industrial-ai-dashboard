"""옵시디언풍 "위키" 노트 CRUD + AI 위키 정리.

ontology.py만큼 얇은 라우터 — 로직은 repository.py(저장)와 ai_agent.py(AI 정리)에 있고,
여기는 그걸 그대로 REST로 노출만 한다. AI 채팅에서의 노트 추가/수정(propose_add_note 등)은
chat.py의 제안(propose) 흐름을 타므로 이 파일과는 별개 경로다.
"""

import numpy as np

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
    고정컨텍스트: bool | None = None


def _노트_재임베딩(note_id: int, 제목: str, 내용: str) -> None:
    """의미검색용 벡터를 갱신한다. Voyage 키가 없거나 호출이 실패해도 노트 저장
    자체는 이미 끝난 뒤이므로 여기서는 그냥 조용히 넘어간다."""
    try:
        벡터 = ai_agent.노트_임베딩_생성(f"{제목}\n{내용}".strip())
        if 벡터:
            repo.노트_임베딩_저장(note_id, np.asarray(벡터, dtype="float32").tobytes())
    except Exception:
        pass


@router.get("")
def 노트_목록():
    return repo.노트_목록_불러오기()


@router.post("")
def 노트_생성(요청: _노트_생성_요청):
    새_id = repo.노트_생성(요청.제목, 요청.내용, 요청.태그)
    _노트_재임베딩(새_id, 요청.제목, 요청.내용)
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
    if "제목" in 변경필드 or "내용" in 변경필드:
        최신 = repo.노트_불러오기(note_id)
        if 최신:
            _노트_재임베딩(note_id, 최신.get("제목", ""), 최신.get("내용", "") or "")
    return {"ok": True}


@router.get("/{note_id}/versions")
def 노트_버전_목록(note_id: int):
    return repo.노트_버전_목록(note_id)


@router.post("/{note_id}/versions/{version_id}/restore")
def 노트_버전_복원(note_id: int, version_id: int):
    버전 = repo.노트_버전_불러오기(version_id)
    if not 버전 or 버전.get("노트_id") != note_id:
        raise HTTPException(status_code=404, detail="해당 버전을 찾을 수 없습니다.")
    repo.노트_수정(
        note_id,
        {"제목": 버전["제목"], "내용": 버전["내용"], "태그": 버전["태그"]},
        작성자=f"{버전['작성자']} 버전 복원",
    )
    최신 = repo.노트_불러오기(note_id)
    if 최신:
        _노트_재임베딩(note_id, 최신.get("제목", ""), 최신.get("내용", "") or "")
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
