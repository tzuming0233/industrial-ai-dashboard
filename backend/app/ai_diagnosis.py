"""제조 AI수준진단 — "풀스택 AI팩토리" 9개 레이어(L1~L9) 참조모델 기반 자가진단.

레이어 정의(코드/이름/설명/AI 개입 지점/P1~P3 기준)는 이제 DB
(repository.py의 제조AI진단_레이어 테이블)에 있다 — 최초 실행 시 참조 문서
("풀스택 AI팩토리_배재현.pdf") 내용으로 시드되고, 이후에는 AI 채팅의
propose_add_diagnosis_layer 등으로 계속 편집될 수 있다. 세션(누가 어느
대상을 언제 진단했는지)과 레이어별 응답도 같은 파일의 제조AI진단_*에 있다.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app import auth, repository as repo

router = APIRouter(dependencies=[Depends(auth.인증_확인)], prefix="/api/ai-diagnosis")

# 5단계 종합 밴드 — 문서(page 3)의 "성숙 레이어" 조합을 그대로 옮김.
# "성숙"의 판정 기준(수준 >= 2, 즉 P2 추상화 이상)은 문서에 명시된 알고리즘이
# 아니라 이 진단 도구가 임의로 정한 실무적 가정이다 — 필요하면 조정한다.
_성숙_임계값 = 2
_5단계_밴드 = [
    (1, "Connected Foundation", "설비 연결", ["L8", "L9"]),
    (2, "Integrated Platform", "데이터 통합", ["L7", "L3"]),
    (3, "Digital Model Factory", "의미·모델화", ["L6", "L7", "L8"]),
    (4, "AI Operationalization", "AI 운영화", ["L4", "L5"]),
    (5, "Full-Stack AI Factory", "자율 운영", ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9"]),
]


def _전체단계_계산(레이어_수준: dict[str, int]) -> dict:
    """레이어별 수준(0~3)으로 5단계 밴드 중 가장 높이 도달한 단계를 계산한다."""
    도달_단계 = None
    for 단계, 이름, 부제, 필요_레이어들 in _5단계_밴드:
        if all(레이어_수준.get(코드, 0) >= _성숙_임계값 for 코드 in 필요_레이어들):
            도달_단계 = (단계, 이름, 부제)
    if 도달_단계 is None:
        return {"단계": 0, "이름": "Pre-Connected", "부제": "연결 전 — 설비 연결부터 시작 필요"}
    단계, 이름, 부제 = 도달_단계
    return {"단계": 단계, "이름": 이름, "부제": 부제}


class _세션_생성_요청(BaseModel):
    대상명: str
    사업_id: int | None = None
    메모: str = ""


class _세션_수정_요청(BaseModel):
    대상명: str | None = None
    메모: str | None = None


class _응답_항목(BaseModel):
    레이어코드: str
    수준: int
    메모: str = ""


class _응답_일괄_요청(BaseModel):
    응답: list[_응답_항목]


def _단계_포함_세션(세션: dict) -> dict:
    레이어_수준 = {row["레이어코드"]: row["수준"] for row in 세션.get("응답", [])}
    세션["종합단계"] = _전체단계_계산(레이어_수준)
    return 세션


@router.get("/layers")
def 레이어_정의():
    return repo.제조AI진단_레이어_목록()


@router.get("/sessions")
def 세션_목록():
    세션들 = repo.제조AI진단_세션_목록()
    결과 = []
    for 세션 in 세션들:
        상세 = repo.제조AI진단_세션_조회(세션["id"])
        결과.append(_단계_포함_세션(상세) if 상세 else 세션)
    return 결과


@router.post("/sessions")
def 세션_생성(요청: _세션_생성_요청, 사용자: dict = Depends(auth.현재_사용자)):
    if not 요청.대상명.strip():
        raise HTTPException(status_code=400, detail="대상명을 입력해주세요.")
    새_id = repo.제조AI진단_세션_생성(요청.대상명.strip(), 사용자["이름"], 요청.사업_id, 요청.메모)
    return {"id": 새_id}


@router.get("/sessions/{session_id}")
def 세션_상세(session_id: int):
    세션 = repo.제조AI진단_세션_조회(session_id)
    if not 세션:
        raise HTTPException(status_code=404, detail="진단 세션을 찾을 수 없습니다.")
    return _단계_포함_세션(세션)


@router.put("/sessions/{session_id}")
def 세션_수정(session_id: int, 요청: _세션_수정_요청):
    세션 = repo.제조AI진단_세션_조회(session_id)
    if not 세션:
        raise HTTPException(status_code=404, detail="진단 세션을 찾을 수 없습니다.")
    repo.제조AI진단_세션_수정(session_id, 요청.대상명, 요청.메모)
    return {"ok": True}


@router.put("/sessions/{session_id}/responses")
def 응답_일괄저장(session_id: int, 요청: _응답_일괄_요청):
    세션 = repo.제조AI진단_세션_조회(session_id)
    if not 세션:
        raise HTTPException(status_code=404, detail="진단 세션을 찾을 수 없습니다.")
    레이어_코드_집합 = {레이어["코드"] for 레이어 in repo.제조AI진단_레이어_목록()}
    for 항목 in 요청.응답:
        if 항목.레이어코드 not in 레이어_코드_집합:
            raise HTTPException(status_code=400, detail=f"알 수 없는 레이어 코드입니다: {항목.레이어코드}")
        if not (0 <= 항목.수준 <= 3):
            raise HTTPException(status_code=400, detail="수준은 0~3 사이여야 합니다.")
    repo.제조AI진단_응답_일괄저장(session_id, [항목.model_dump() for 항목 in 요청.응답])
    return _단계_포함_세션(repo.제조AI진단_세션_조회(session_id))


@router.delete("/sessions/{session_id}")
def 세션_삭제(session_id: int):
    repo.제조AI진단_세션_삭제(session_id)
    return {"ok": True}
