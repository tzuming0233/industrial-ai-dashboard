"""사업 온톨로지(지식그래프) 조회 + 그래프 화면에서 직접 편집(노드 클릭으로 관계 추가/삭제).

AI 채팅이 만드는 제안(propose_add_relations 등, chat.py)과 별개로, 그래프에서
노드를 클릭해 바로 관계를 잇거나 선을 클릭해 지우는 기능을 위한 엔드포인트.
"""

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app import auth, projects, repository as repo

router = APIRouter(dependencies=[Depends(auth.인증_확인)], prefix="/api/ontology")


def _프로젝트_스코프_확인(project_id: int | None, 사용자: dict) -> None:
    if project_id is not None:
        projects.소유권_확인(project_id, 사용자["id"])


def _NaN_정리(df: pd.DataFrame) -> list[dict]:
    # df.where(pd.notna(df), None)만 쓰면 사업_id/노트_id처럼 NULL 섞인 정수 컬럼이
    # float64로 읽혀서, 대입한 None이 다시 NaN으로 되돌아간다(float64 배열은 파이썬
    # None을 못 담음) — json.dumps가 NaN을 못 쓰는 값으로 보고 500을 낸다. astype(object)로
    # 먼저 바꿔야 None이 실제로 남는다.
    return df.astype(object).where(df.notna(), None).to_dict("records")


@router.get("/nodes")
def 노드_목록(project_id: int | None = None, 사용자: dict = Depends(auth.현재_사용자)):
    _프로젝트_스코프_확인(project_id, 사용자)
    return _NaN_정리(repo.온톨로지_노드_불러오기(project_id))


@router.get("/relations")
def 관계_목록(project_id: int | None = None, 사용자: dict = Depends(auth.현재_사용자)):
    _프로젝트_스코프_확인(project_id, 사용자)
    return _NaN_정리(repo.온톨로지_관계_불러오기(project_id))


class _직접_추가_요청(BaseModel):
    node1_id: int
    node2_id: int
    relation_type: str
    description: str = ""
    author: str = "그래프클릭"
    project_id: int | None = None


@router.post("/relations/direct")
def 관계_직접추가(요청: _직접_추가_요청, 사용자: dict = Depends(auth.현재_사용자)):
    _프로젝트_스코프_확인(요청.project_id, 사용자)
    # 두 노드가 실제로 이 스코프(프로젝트 또는 전역)에 속하는지 확인 — 다른 프로젝트나
    # 전역 그래프의 노드를 잘못 끌어와 잇는 것을 막는다.
    for 노드_id in (요청.node1_id, 요청.node2_id):
        if repo.온톨로지_노드_프로젝트_id_조회(노드_id) != 요청.project_id:
            raise HTTPException(status_code=400, detail="다른 그래프에 속한 노드는 연결할 수 없습니다.")
    repo.온톨로지_관계_직접추가(요청.node1_id, 요청.node2_id, 요청.relation_type, 요청.description, 요청.author)
    return {"ok": True}


@router.delete("/relations/{relation_id}")
def 관계_삭제(relation_id: int, 사용자: dict = Depends(auth.현재_사용자)):
    _프로젝트_스코프_확인(repo.온톨로지_관계_프로젝트_id_조회(relation_id), 사용자)
    repo.온톨로지_관계_삭제(relation_id)
    return {"ok": True}


class _초기화_요청(BaseModel):
    project_id: int | None = None


@router.post("/reset")
def 전체_초기화(요청: _초기화_요청 = _초기화_요청(), 사용자: dict = Depends(auth.현재_사용자)):
    _프로젝트_스코프_확인(요청.project_id, 사용자)
    repo.온톨로지_초기화(요청.project_id)
    return {"ok": True}
