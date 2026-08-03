"""사업 온톨로지(지식그래프) 조회 + 그래프 화면에서 직접 편집(노드 클릭으로 관계 추가/삭제).

AI 채팅이 만드는 제안(propose_add_relations 등, chat.py)과 별개로, 그래프에서
노드를 클릭해 바로 관계를 잇거나 선을 클릭해 지우는 기능을 위한 엔드포인트.
"""

import pandas as pd
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app import auth, repository as repo

router = APIRouter(dependencies=[Depends(auth.인증_확인)], prefix="/api/ontology")


def _NaN_정리(df: pd.DataFrame) -> list[dict]:
    return df.where(pd.notna(df), None).to_dict("records")


@router.get("/nodes")
def 노드_목록():
    return _NaN_정리(repo.온톨로지_노드_불러오기())


@router.get("/relations")
def 관계_목록():
    return _NaN_정리(repo.온톨로지_관계_불러오기())


class _직접_추가_요청(BaseModel):
    node1_id: int
    node2_id: int
    relation_type: str
    description: str = ""
    author: str = "그래프클릭"


@router.post("/relations/direct")
def 관계_직접추가(요청: _직접_추가_요청):
    repo.온톨로지_관계_직접추가(요청.node1_id, 요청.node2_id, 요청.relation_type, 요청.description, 요청.author)
    return {"ok": True}


@router.delete("/relations/{relation_id}")
def 관계_삭제(relation_id: int):
    repo.온톨로지_관계_삭제(relation_id)
    return {"ok": True}


@router.post("/reset")
def 전체_초기화():
    repo.온톨로지_초기화()
    return {"ok": True}
