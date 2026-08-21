"""'데이터 관리' 탭의 연간 목표 / 투입 인력 REST 래퍼.

notes.py/ontology.py와 같은 얇은 라우터 — 로직은 전부 repository.py에 있고
(Streamlit과 공유하는 계층이라 여기서 새로 안 만듦), 여기는 REST로 노출만 한다.
사업현황 자체의 저장은 GET /api/business와 짝을 맞추기 위해 main.py에 있다.
"""

import pandas as pd
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app import auth, repository as repo

router = APIRouter(dependencies=[Depends(auth.인증_확인)], prefix="/api")


def _NaN_정리(df: pd.DataFrame) -> list[dict]:
    # astype(object) 없이 .where(notna, None)만 쓰면 NULL 섞인 정수 컬럼(float64로 읽힘)에서
    # 대입한 None이 다시 NaN으로 되돌아가 json.dumps가 500을 낸다(ontology.py에서 겪은 버그).
    return df.astype(object).where(df.notna(), None).to_dict("records")


# ---------------- 연간 목표 ----------------


class _목표_저장_요청(BaseModel):
    연도: int
    목표매출: int
    목표손익: int


@router.get("/targets")
def 연간목표_목록():
    return _NaN_정리(repo.연간목표_불러오기())


@router.post("/targets")
def 연간목표_저장_엔드포인트(요청: _목표_저장_요청):
    repo.연간목표_저장(요청.연도, 요청.목표매출, 요청.목표손익)
    return {"ok": True}


# ---------------- 투입 인력 ----------------


class _인력_추가_요청(BaseModel):
    사업_id: int
    이름: str
    역할: str = ""


@router.get("/staffing/{business_id}")
def 투입인력_목록(business_id: int):
    return _NaN_정리(repo.투입인력_불러오기(business_id))


@router.post("/staffing")
def 투입인력_추가(요청: _인력_추가_요청):
    repo.투입인력_저장(요청.사업_id, 요청.이름, 요청.역할)
    return {"ok": True}


@router.delete("/staffing/{staffing_id}")
def 투입인력_삭제_엔드포인트(staffing_id: int):
    repo.투입인력_삭제(staffing_id)
    return {"ok": True}
