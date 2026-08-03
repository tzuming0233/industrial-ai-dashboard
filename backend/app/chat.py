"""AI 채팅 — 대화 CRUD + SSE 스트리밍 + 제안(추가/수정/삭제) 적용·취소.

app.py(Streamlit)의 AI 채팅 탭과 완전히 같은 ai_agent/repository 로직을 쓴다. 다만 여기서는:
- 블로킹 질의하기() 대신 스트리밍 질의하기_스트림()을 쓰고,
- 확인 대기 중인 제안(pending_action)을 Streamlit의 session_state 대신 프로세스 메모리
  (_대기중_제안)에 대화_id로 키를 걸어 보관한다. 서버가 --workers 1로 단일 프로세스라
  세션별 상태가 섞이지 않는다(session_state와 동등한 보장 수준). 서버 재시작 시 미확인
  제안이 사라지는 것도 기존 Streamlit이 앱 재시작 시 session_state를 잃는 것과 동일한 특성.
- 더블클릭/재연결에도 안전하도록 제안마다 action_token(uuid4)을 발급해, 이미 처리된
  토큰으로 다시 적용/취소를 눌러도 에러 없이 무시한다(idempotent).
"""

import datetime as _dt
import io
import json
import shutil
import uuid

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import ai_agent
from backend.app import auth, repository as repo
from backend.app.files import (
    _업로드_원본_읽기, _pdf_텍스트_추출, _hwp_텍스트_추출, _LLM_매핑_적용, _제안_추가행들,
)

router = APIRouter(dependencies=[Depends(auth.인증_확인)])

# 대화_id -> {"제안": {...}, "token": "..."} — 확인 대기 중인 제안(서버 메모리, session_state 대체).
_대기중_제안: dict[int, dict] = {}


class _파일버퍼(io.BytesIO):
    """UploadFile을 기존 files.py 함수들(Streamlit UploadedFile 인터페이스 기대)이
    바로 쓸 수 있게 .name을 붙인 얇은 어댑터."""

    def __init__(self, content: bytes, name: str):
        super().__init__(content)
        self.name = name


def _df_레코드(df: pd.DataFrame) -> list[dict]:
    return df.where(pd.notna(df), None).to_dict("records")


def _사업_라벨_맵(전체_df: pd.DataFrame) -> dict[int, str]:
    라벨_맵: dict[int, str] = {}
    if "id" not in 전체_df.columns:
        return 라벨_맵
    for _, 행 in 전체_df.iterrows():
        try:
            sid = int(행["id"])
        except (TypeError, ValueError):
            continue
        라벨_맵[sid] = f"{행.get('업체명', '') or ''} · {행.get('용역명', '') or ''}".strip(" ·")
    return 라벨_맵


def _프로젝트_컨텍스트(연결된_사업_id: int | None, 전체_df: pd.DataFrame) -> str:
    if not 연결된_사업_id or "id" not in 전체_df.columns:
        return ""
    행목록 = 전체_df[전체_df["id"] == 연결된_사업_id]
    if 행목록.empty:
        return ""
    r = 행목록.iloc[0]
    return (
        "[이 대화는 다음 사업에 연결되어 있습니다 — "
        f"업체명: {r.get('업체명', '')}, 용역명: {r.get('용역명', '')}, "
        f"사업구분: {r.get('사업구분', '')}, 기간: {r.get('시작일', '')}~{r.get('종료일', '')}, "
        f"계약금액: {r.get('계약금액', '')}, 진행률: {r.get('진행률', '')}%, "
        f"담당자: {r.get('담당자', '')}, 사업단계: {r.get('사업단계', '')}. "
        "질문에 사업 이름이 없어도 이 사업을 가리키는 것으로 우선 해석하세요.]\n\n"
    )


def _제안_요약(제안: dict, 전체_df: pd.DataFrame) -> dict:
    """대기 중인 제안을 프론트가 그대로 렌더링할 수 있는 JSON으로 요약한다."""
    유형 = 제안.get("유형")
    인자 = 제안.get("인자", {})

    if 유형 == "업로드":
        return {
            "유형": 유형,
            "경고": 제안.get("경고") or [],
            "행": _df_레코드(제안["결과_df"].drop(columns=["id"])),
        }
    if 유형 == "propose_add_business":
        return {
            "유형": 유형,
            "행": _df_레코드(_제안_추가행들(인자.get("사업목록", [])).drop(columns=["id"])),
        }
    if 유형 == "propose_update_business":
        대상id = 인자.get("id")
        변경필드 = 인자.get("변경필드", {})
        기존행 = 전체_df[전체_df["id"] == 대상id] if "id" in 전체_df.columns else 전체_df.iloc[0:0]
        if 기존행.empty:
            return {"유형": 유형, "오류": f"id={대상id} 건을 찾을 수 없습니다."}
        기존 = 기존행.iloc[0]
        return {
            "유형": 유형,
            "대상id": 대상id,
            "제목": f"{기존.get('업체명', '')} · {기존.get('용역명', '')} (id={대상id})",
            "변경": [
                {
                    "필드": 필드,
                    "이전값": None if 필드 not in 기존 or pd.isna(기존[필드]) else 기존[필드],
                    "새값": 새값,
                }
                for 필드, 새값 in 변경필드.items()
            ],
        }
    if 유형 == "propose_delete_business":
        ids = 인자.get("ids", [])
        대상_df = 전체_df[전체_df["id"].isin(ids)] if "id" in 전체_df.columns else 전체_df.iloc[0:0]
        return {"유형": 유형, "행": _df_레코드(대상_df.drop(columns=["id"]))}
    if 유형 == "propose_add_relations":
        관계목록 = [
            {
                "노드1": 관계.get("노드1_이름") or (f"사업#{관계.get('노드1_사업_id')}" if 관계.get("노드1_사업_id") else "?"),
                "노드2": 관계.get("노드2_이름") or (f"사업#{관계.get('노드2_사업_id')}" if 관계.get("노드2_사업_id") else "?"),
                "관계유형": 관계.get("관계유형", ""),
                "설명": 관계.get("설명", ""),
            }
            for 관계 in 인자.get("관계목록", [])
        ]
        return {"유형": 유형, "관계": 관계목록}
    if 유형 == "propose_delete_relations":
        관계_id_목록 = 인자.get("관계_id_목록", [])
        노드_df = repo.온톨로지_노드_불러오기()
        관계_df = repo.온톨로지_관계_불러오기()
        대상_df = 관계_df[관계_df["id"].isin(관계_id_목록)]
        if 대상_df.empty:
            return {"유형": 유형, "오류": "삭제할 관계를 찾을 수 없습니다."}
        노드_이름표 = 노드_df[["id", "이름"]]
        표시용_df = (
            대상_df.merge(노드_이름표.rename(columns={"id": "출발_노드_id", "이름": "출발"}), on="출발_노드_id", how="left")
            .merge(노드_이름표.rename(columns={"id": "도착_노드_id", "이름": "도착"}), on="도착_노드_id", how="left")
        )
        return {
            "유형": 유형,
            "관계": [
                {"노드1": 행["출발"], "노드2": 행["도착"], "관계유형": 행["관계유형"], "설명": ""}
                for _, 행 in 표시용_df.iterrows()
            ],
        }
    return {"유형": 유형, "오류": "알 수 없는 제안 유형"}


def _제안_반영(제안: dict, 전체_df: pd.DataFrame, 작성자: str = "AI채팅") -> None:
    유형 = 제안.get("유형")
    인자 = 제안.get("인자", {})

    if 유형 == "업로드":
        반영대상_df = pd.concat([전체_df, 제안["결과_df"]], ignore_index=True)
        repo.사업현황_저장(반영대상_df, 전체_df, 작성자)
    elif 유형 == "propose_add_business":
        추가_df = _제안_추가행들(인자.get("사업목록", []))
        반영대상_df = pd.concat([전체_df, 추가_df], ignore_index=True)
        repo.사업현황_저장(반영대상_df, 전체_df, 작성자)
    elif 유형 == "propose_update_business":
        대상id = 인자.get("id")
        변경필드 = 인자.get("변경필드", {})
        편집_df = 전체_df.copy()
        마스크 = 편집_df["id"] == 대상id
        for 필드, 새값 in 변경필드.items():
            if 필드 in 편집_df.columns:
                편집_df.loc[마스크, 필드] = 새값
        repo.사업현황_저장(편집_df, 전체_df, 작성자)
    elif 유형 == "propose_delete_business":
        ids = 인자.get("ids", [])
        편집_df = 전체_df[~전체_df["id"].isin(ids)]
        repo.사업현황_저장(편집_df, 전체_df, 작성자)
    elif 유형 == "propose_add_relations":
        repo.온톨로지_관계_추가(인자.get("관계목록", []), 전체_df, 작성자)
    elif 유형 == "propose_delete_relations":
        for 관계_id in 인자.get("관계_id_목록", []):
            repo.온톨로지_관계_삭제(관계_id)


# ---------------- 대화 CRUD ----------------


class _대화_생성_요청(BaseModel):
    사업_id: int | None = None


@router.get("/api/conversations")
def 대화_목록():
    전체_df = repo.사업현황_불러오기()
    라벨_맵 = _사업_라벨_맵(전체_df)
    목록 = repo.대화_목록_불러오기()
    for d in 목록:
        d["사업_라벨"] = 라벨_맵.get(d.get("사업_id")) if d.get("사업_id") else None
    return 목록


@router.post("/api/conversations")
def 대화_생성_엔드포인트(요청: _대화_생성_요청):
    return {"id": repo.대화_생성(사업_id=요청.사업_id)}


@router.delete("/api/conversations/{conversation_id}")
def 대화_삭제_엔드포인트(conversation_id: int):
    # Starlette의 경로 파라미터 매칭 정규식이 ASCII만 인식해서(Anthropic tool_use의
    # input_schema 키 제약과 같은 종류의 제약) URL 경로 파라미터명만 영문으로 쓰고,
    # 나머지 내부 로직은 기존처럼 한글 변수명을 그대로 쓴다.
    대화_id = conversation_id
    repo.대화_삭제(대화_id)
    _대기중_제안.pop(대화_id, None)
    return {"ok": True}


@router.get("/api/conversations/{conversation_id}/messages")
def 대화_메시지(conversation_id: int):
    대화_id = conversation_id
    전체_df = repo.사업현황_불러오기()
    라벨_맵 = _사업_라벨_맵(전체_df)
    현재_대화 = next((d for d in repo.대화_목록_불러오기() if d["id"] == 대화_id), None)
    연결된_사업_id = 현재_대화.get("사업_id") if 현재_대화 else None
    보류중 = _대기중_제안.get(대화_id)
    return {
        "메시지": repo.채팅기록_불러오기(대화_id),
        "연결된_사업_id": 연결된_사업_id,
        "사업_라벨": 라벨_맵.get(연결된_사업_id) if 연결된_사업_id else None,
        "제안": (
            {"요약": _제안_요약(보류중["제안"], 전체_df), "action_token": 보류중["token"]}
            if 보류중 else None
        ),
    }


# ---------------- 제안 적용/취소 ----------------


class _제안_처리_요청(BaseModel):
    action_token: str


@router.post("/api/conversations/{conversation_id}/proposal/apply")
def 제안_적용(conversation_id: int, 요청: _제안_처리_요청):
    대화_id = conversation_id
    보류중 = _대기중_제안.get(대화_id)
    if not 보류중 or 보류중["token"] != 요청.action_token:
        return {"적용됨": False, "메시지": "이미 처리되었거나 만료된 제안입니다."}
    제안 = 보류중["제안"]
    전체_df = repo.사업현황_불러오기()
    if 제안.get("유형") == "업로드":
        백업_경로 = repo.DB_PATH.with_name(f"실적관리_{_dt.datetime.now():%Y%m%d%H%M%S}.bak")
        shutil.copy(repo.DB_PATH, 백업_경로)
    _제안_반영(제안, 전체_df)
    _대기중_제안.pop(대화_id, None)
    repo.채팅기록_저장(대화_id, "assistant", "반영했습니다.")
    return {"적용됨": True}


@router.post("/api/conversations/{conversation_id}/proposal/cancel")
def 제안_취소(conversation_id: int, 요청: _제안_처리_요청):
    대화_id = conversation_id
    보류중 = _대기중_제안.get(대화_id)
    if not 보류중 or 보류중["token"] != 요청.action_token:
        return {"취소됨": False}
    _대기중_제안.pop(대화_id, None)
    repo.채팅기록_저장(대화_id, "assistant", "제안을 취소했습니다.")
    return {"취소됨": True}


# ---------------- SSE 스트리밍 메시지 전송 ----------------


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _마무리(대화_id: int, 텍스트: str, 제안: dict | None, 전체_df: pd.DataFrame | None = None):
    repo.채팅기록_저장(대화_id, "assistant", 텍스트)
    if not 제안:
        yield _sse("done", {"text": 텍스트, "제안": None, "action_token": None})
        return
    토큰 = uuid.uuid4().hex
    _대기중_제안[대화_id] = {"제안": 제안, "token": 토큰}
    if 전체_df is None:
        전체_df = repo.사업현황_불러오기()
    yield _sse("done", {"text": 텍스트, "제안": _제안_요약(제안, 전체_df), "action_token": 토큰})


def _이벤트_전달(이벤트: dict):
    """ai_agent.질의하기_스트림()의 token/status 이벤트를 그대로 SSE로 옮긴다."""
    if 이벤트["type"] == "token":
        return _sse("token", {"text": 이벤트["text"]})
    return _sse("status", {"message": 이벤트["text"]})


def _일반_질문_스트림(대화_id: int, 질문: str, 프로젝트_컨텍스트: str, API용_기록: list):
    for 이벤트 in ai_agent.질의하기_스트림(프로젝트_컨텍스트 + 질문, history=API용_기록):
        if 이벤트["type"] in ("token", "status"):
            yield _이벤트_전달(이벤트)
        else:
            yield from _마무리(대화_id, 이벤트["text"], 이벤트.get("pending_action"))


def _문서_파일_스트림(대화_id: int, 첨부, 질문: str, 프로젝트_컨텍스트: str, API용_기록: list):
    try:
        문서_텍스트 = (
            _pdf_텍스트_추출(첨부) if 첨부.name.lower().endswith(".pdf") else _hwp_텍스트_추출(첨부)
        )
    except Exception as e:
        답변 = f"'{첨부.name}' 문서를 읽지 못했습니다: {e}"
        yield from _마무리(대화_id, 답변, None)
        return

    if not 문서_텍스트.strip():
        답변 = f"'{첨부.name}'에서 텍스트를 추출하지 못했습니다(스캔 이미지 PDF일 수 있습니다)."
        yield from _마무리(대화_id, 답변, None)
        return

    합쳐진_질문 = (
        프로젝트_컨텍스트 +
        f"[첨부 문서 '{첨부.name}' 내용]\n{문서_텍스트}\n\n"
        f"[사용자 질문]\n{질문 or '이 문서 내용을 요약해줘.'}"
    )
    for 이벤트 in ai_agent.질의하기_스트림(합쳐진_질문, history=API용_기록):
        if 이벤트["type"] in ("token", "status"):
            yield _이벤트_전달(이벤트)
        else:
            yield from _마무리(대화_id, 이벤트["text"], 이벤트.get("pending_action"))


def _표_파일_스트림(대화_id: int, 첨부, 질문: str, 프로젝트_컨텍스트: str, API용_기록: list, 전체_df: pd.DataFrame):
    원본_df = _업로드_원본_읽기(첨부)
    if 원본_df.empty:
        yield from _마무리(대화_id, "첨부된 파일에서 데이터를 찾지 못했습니다.", None)
        return

    미리보기_행수 = min(8, len(원본_df))
    합쳐진_질문 = (
        프로젝트_컨텍스트 +
        f"[첨부 파일 '{첨부.name}' 미리보기 — 총 {len(원본_df)}행, 컬럼: {list(원본_df.columns)}]\n"
        f"{원본_df.head(미리보기_행수).to_csv(index=False)}"
        + (f"...(이하 {len(원본_df) - 미리보기_행수}행 생략)\n" if len(원본_df) > 미리보기_행수 else "")
        + f"\n[사용자 메시지]\n{질문 or '이 파일을 검토해줘.'}"
    )

    최종_텍스트 = ""
    제안 = None
    for 이벤트 in ai_agent.질의하기_스트림(합쳐진_질문, history=API용_기록):
        if 이벤트["type"] in ("token", "status"):
            yield _이벤트_전달(이벤트)
        else:
            최종_텍스트 = 이벤트["text"]
            제안 = 이벤트.get("pending_action")

    if 제안 and 제안.get("유형") == "import_uploaded_file_as_data":
        yield _sse("status", {"message": "AI가 사업현황 필드에 맞게 정리하는 중..."})
        매핑결과 = ai_agent.업로드_매핑_추론(list(원본_df.columns), 원본_df.head(5).to_dict("records"))
        if "오류" in 매핑결과:
            최종_텍스트 += f"\n\n(반영 중 오류가 있었습니다: {매핑결과['오류']})"
            yield from _마무리(대화_id, 최종_텍스트, None)
        else:
            결과_df, 경고_목록 = _LLM_매핑_적용(원본_df, 매핑결과)
            yield from _마무리(
                대화_id, 최종_텍스트, {"유형": "업로드", "결과_df": 결과_df, "경고": 경고_목록}, 전체_df,
            )
    else:
        yield from _마무리(대화_id, 최종_텍스트, 제안, 전체_df)


@router.post("/api/conversations/{conversation_id}/messages/stream")
async def 메시지_스트림(conversation_id: int, message: str = Form(""), file: UploadFile | None = File(None)):
    대화_id = conversation_id
    질문 = (message or "").strip()
    첨부 = None
    if file is not None and file.filename:
        내용 = await file.read()
        첨부 = _파일버퍼(내용, file.filename)

    이전_기록 = repo.채팅기록_불러오기(대화_id)
    첫_메시지_여부 = not 이전_기록

    표시_메시지 = 질문
    if 첨부:
        표시_메시지 = (표시_메시지 + f"\n\n📎 {첨부.name}").strip()
    if 표시_메시지:
        repo.채팅기록_저장(대화_id, "user", 표시_메시지)
        if 첫_메시지_여부:
            repo.대화_제목_설정(대화_id, ai_agent.대화_제목_생성(표시_메시지))

    전체_df = repo.사업현황_불러오기()
    현재_대화 = next((d for d in repo.대화_목록_불러오기() if d["id"] == 대화_id), None)
    연결된_사업_id = 현재_대화.get("사업_id") if 현재_대화 else None
    프로젝트_컨텍스트 = _프로젝트_컨텍스트(연결된_사업_id, 전체_df)
    API용_기록 = [{"role": m["role"], "content": m["content"]} for m in 이전_기록[-20:]]

    파일명_소문자 = 첨부.name.lower() if 첨부 else ""
    표_파일 = 파일명_소문자.endswith((".csv", ".xlsx", ".xls"))
    문서_파일 = 파일명_소문자.endswith((".pdf", ".hwp"))

    def 이벤트_스트림():
        try:
            if 표_파일:
                yield from _표_파일_스트림(대화_id, 첨부, 질문, 프로젝트_컨텍스트, API용_기록, 전체_df)
            elif 문서_파일:
                yield from _문서_파일_스트림(대화_id, 첨부, 질문, 프로젝트_컨텍스트, API용_기록)
            elif 질문:
                yield from _일반_질문_스트림(대화_id, 질문, 프로젝트_컨텍스트, API용_기록)
            else:
                yield _sse("done", {"text": "", "제안": None, "action_token": None})
        except Exception as e:
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        이벤트_스트림(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
