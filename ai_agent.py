"""
산업AI팀 사업 통합관리 - AI 채팅 자연어 질의

SQLite 조회 함수 1개를 Claude API의 tool(도구)로 등록해
자연어 질의에 답한다.

사용 전 준비:
    1) pip install -r requirements.txt
    2) 환경변수 ANTHROPIC_API_KEY 설정 (.env.example 참고)
"""

import json
import os
import sqlite3
from pathlib import Path

from anthropic import Anthropic

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db" / "실적관리.db"

# 필요 시 다른 모델로 교체 가능 (예: 비용을 낮추려면 claude-haiku-4-5-20251001)
MODEL_NAME = "claude-sonnet-5"

SYSTEM_PROMPT = (
    "당신은 산업AI팀 사업 통합관리 시스템의 AI 비서입니다. "
    "사용자의 질문에 답하기 위해 반드시 '조회_사업현황' 도구로 SQLite 데이터를 조회한 뒤, "
    "조회된 실제 데이터만 근거로 한국어로 간결하게 답변하세요. 데이터에 없는 내용은 지어내지 마세요."
)

TOOLS = [
    {
        "name": "조회_사업현황",
        "description": (
            "사업현황 테이블에서 조건에 맞는 사업(계약) 목록을 조회한다. "
            "사업구분, 구분(신규/이월), 진행상태, 종료일 범위로 필터링할 수 있으며, "
            "인자를 지정하지 않으면 전체 건수 요약만 반환한다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "사업구분": {"type": "string", "description": "예: 상생형 스마트공장, 자율형공장 컨설팅 등"},
                "구분": {"type": "string", "description": "예: 컨설팅_신규, 컨설팅_이월, 수탁_신규, 수탁_이월"},
                "진행상태": {"type": "string", "description": "예: 진행중, 완료, 보류"},
                "종료일_이전": {"type": "string", "description": "YYYY-MM-DD, 이 날짜 이전에 종료되는 건만"},
                "종료일_이후": {"type": "string", "description": "YYYY-MM-DD, 이 날짜 이후에 종료되는 건만"},
            },
        },
    }
]


def 조회_사업현황(사업구분=None, 구분=None, 진행상태=None, 종료일_이전=None, 종료일_이후=None) -> list[dict]:
    if not DB_PATH.exists():
        return []

    조건절 = []
    파라미터 = []
    if 사업구분:
        조건절.append("사업구분 = ?")
        파라미터.append(사업구분)
    if 구분:
        조건절.append("구분 = ?")
        파라미터.append(구분)
    if 진행상태:
        조건절.append("진행상태 = ?")
        파라미터.append(진행상태)
    if 종료일_이전:
        조건절.append("종료일 <= ?")
        파라미터.append(종료일_이전)
    if 종료일_이후:
        조건절.append("종료일 >= ?")
        파라미터.append(종료일_이후)

    where절 = f"WHERE {' AND '.join(조건절)}" if 조건절 else ""
    쿼리 = f"""
        SELECT 구분, 업체명, 용역명, 사업구분, 진행상태, 진행률, 시작일, 종료일,
               계약금액, 기수입금액, 당해년도수입금액
        FROM 사업현황
        {where절}
        ORDER BY 종료일
    """

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(쿼리, 파라미터).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _도구_실행(name: str, tool_input: dict) -> list[dict]:
    if name == "조회_사업현황":
        return 조회_사업현황(**tool_input)
    raise ValueError(f"알 수 없는 도구: {name}")


def 질의하기(question: str, history: list[dict] | None = None, api_key: str | None = None) -> str:
    """자연어 질문 -> Claude가 SQLite를 조회하며 답변 생성

    history: [{"role": "user"/"assistant", "content": "..."}] 형태의 이전 대화 이력.
    도구 호출(tool_use) 내역은 이번 턴 안에서만 쓰고 반환값에는 포함하지 않는다.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            key = None
    if not key:
        return "ANTHROPIC_API_KEY가 설정되어 있지 않습니다. .env 파일(로컬) 또는 Streamlit Cloud의 Secrets 설정을 확인하세요."

    client = Anthropic(api_key=key)
    messages = list(history or []) + [{"role": "user", "content": question}]

    for _ in range(5):  # 도구 호출 반복 상한
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            return "".join(block.text for block in response.content if block.type == "text")

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            결과 = _도구_실행(block.name, block.input)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(결과, ensure_ascii=False),
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return "질의 처리 중 도구 호출 횟수 상한을 초과했습니다."
