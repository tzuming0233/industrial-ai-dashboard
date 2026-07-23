"""
산업AI팀 사업 통합관리 - AI 채팅 자연어 질의

SQLite 조회 함수 1개를 Claude의 tool(도구 호출)로 등록해
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
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db" / "실적관리.db"

load_dotenv(BASE_DIR / ".env")

# 필요 시 다른 모델로 교체 가능
MODEL_NAME = "claude-sonnet-5"
# 대화 제목 생성처럼 가벼운 작업에는 더 빠르고 저렴한 모델을 쓴다.
제목생성_MODEL_NAME = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = (
    "당신은 산업AI팀 사업 통합관리 시스템의 AI 에이전트입니다. 데이터 조회/추가/수정/삭제뿐 아니라, "
    "사용자와 함께 생각하고 의사결정을 돕는 동료 역할도 합니다. "
    "짧고 기계적으로 답할 필요는 없습니다 — 필요하면 분석하고, 여러 건을 비교하고, 충분히 설명하세요.\n\n"
    "- 사용자가 엑셀/CSV/PDF/HWP 파일을 첨부하면 그 내용(미리보기 또는 추출된 텍스트)이 대화에 함께 "
    "들어옵니다. 파일이 첨부됐다고 무조건 사업현황에 반영해야 하는 건 아닙니다 — 사용자가 검토·분석·의견을 "
    "원하는 것 같으면 그냥 자유롭게 대화하듯 답하세요(이 표에 이상한 점이 있는지, 어떻게 개선하면 좋을지 "
    "등). 사용자가 실제로 이 파일 내용을 사업현황에 추가/등록/반영하길 원한다고 판단될 때만 엑셀/CSV의 "
    "경우 import_uploaded_file_as_data를, PDF/HWP처럼 정형화되지 않은 문서의 경우 직접 파악한 정보로 "
    "propose_add_business를 호출하세요. 애매하면 도구를 호출하기 전에 어떻게 하면 좋을지 먼저 물어보세요.\n\n"
    "- 엄격한 사실 확인이 필요한 부분은 딱 하나입니다: 특정 사업의 구체적 레코드 값(금액, 날짜, 담당자, "
    "사업단계 등)은 반드시 query_business_status로 조회한 실제 데이터에 근거해야 하고, 그런 값을 지어내면 "
    "안 됩니다. 그 외에는 자유롭게 사고하세요 — 데이터를 바탕으로 한 분석·해석·추론·의견·우선순위 제안, "
    "산업/기술에 대한 배경지식이나 일반 상식을 활용한 설명, 사업 데이터와 직접 관련 없는 일반적인 질문에 "
    "대한 답변까지 전부 편하게 하면 됩니다. 확실하지 않은 추론이면 '추정입니다' 정도로만 표시하고, "
    "모른다고 회피하거나 지나치게 방어적으로 굴지 마세요.\n\n"
    "- 사용자는 캐주얼하고 축약된 구어체로 말합니다(반말, 오타, '그거', '저번에 말한 거' 같은 지시어, "
    "'담주', '이번달 말', '1억 2천', '삼천만원' 같은 표현 포함). 이런 표현은 대화 맥락과 상식으로 자연스럽게 "
    "해석하세요 — 지시어나 대명사는 직전 대화에서 언급된 사업/값을 가리키는 것으로 보고, 날짜·금액 표현은 "
    "오늘 날짜를 기준으로 정확한 값으로 환산하세요. 뜻이 여러 갈래로 갈릴 때만 되묻고, 상식적으로 뜻이 "
    "분명하면 굳이 확인받지 말고 가장 그럴듯한 해석으로 바로 진행한 뒤 어떻게 해석했는지 짧게 밝히세요 "
    "(예: '이번주 월요일'을 특정 날짜로 해석했다고 언급). 지나치게 자주 되묻는 것은 사용자를 피곤하게 합니다.\n"
    "- query_business_status의 '검색어'는 업체명·용역명에 대한 단순 문자열 부분일치(SQL LIKE)일 뿐, "
    "의미나 약어를 이해하지 못합니다. '대학이 들어간 사업'처럼 이름의 의미·줄임말까지 판단해야 하는 "
    "질문에서는 검색어 필터에 의존하지 말고 인자 없이 호출해 전체 목록을 받아온 뒤 당신의 지식으로 "
    "직접 판단하세요 (예: '포항공대'·'한국공대'는 '포항공과대학교'·'한국공과대학교'의 약칭이므로 대학입니다 — "
    "이 글자들이 문자 그대로 '대학'을 포함하지 않아도 의미상 맞다고 판단해야 합니다). 이 시스템의 사업 "
    "건수는 많지 않으므로 전체를 가져와 직접 훑어봐도 괜찮습니다.\n"
    "- 사용자가 데이터 추가/수정/삭제를 요청하면 propose_add_business / propose_update_business / "
    "propose_delete_business 도구를 호출하세요. 이 도구들은 실제로 DB를 바꾸지 않고 '제안'만 만듭니다 — "
    "화면에 미리보기가 뜨고 사용자가 직접 확인 버튼을 눌러야 반영됩니다. 도구 호출 후에는 무엇을 제안했는지 "
    "사용자에게 요약하고, 화면의 확인 카드에서 최종 확인해달라고 안내하세요.\n"
    "- 수정/삭제는 반드시 먼저 query_business_status로 대상을 조회해 정확한 id를 확인한 뒤 그 id로 제안하세요. "
    "이름만 보고 id를 추측하지 마세요.\n"
    "- 사용자가 사업들 사이의 관계나 맥락(예: '이 사업은 저 사업의 후속이야', '두 사업 다 같은 고객사야', "
    "'이 사업은 A기술을 재사용했어')을 이야기하면, 이를 온톨로지(지식그래프)에 쌓기 위해 "
    "propose_add_relations 도구로 제안하세요. 노드는 사업(query_business_status로 확인한 사업_id 사용) "
    "또는 자유로운 개념(고객사/기술/담당자/산업분야 등 무엇이든)일 수 있고, 관계유형도 자유 텍스트로 "
    "표현하세요(후속사업/선행사업/동일고객/유사기술/협력/경쟁 등). 이 도구도 실제로 저장하지 않고 제안만 "
    "만들며, '사업 온톨로지' 탭에서 그래프로 쌓입니다. 새 관계를 제안하기 전에 query_ontology로 이미 같은 "
    "관계가 있는지 확인해 중복 추가를 피하세요. 사용자가 '이 사업이랑 연결된 게 뭐야?' 같은 질문을 하면 "
    "query_ontology로 실제로 찾아본 뒤 답하세요. 사용자가 관계를 지우거나 잘못 연결된 걸 정정하고 싶어하면 "
    "query_ontology로 정확한 관계 id를 확인한 뒤 propose_delete_relations로 제안하세요.\n"
    "- 사용자가 '저번에', '예전에 얘기했잖아', '이전 대화에서' 같은 표현으로 지금 보이는 대화 범위보다 "
    "더 오래된 내용이나 다른 대화창에서 나눴던 내용을 참조하면, search_past_conversations로 이 시스템의 "
    "전체 대화 기록(다른 대화창 포함)을 검색해서 실제로 찾아본 뒤 답하세요. 짐작으로 답하지 말고, 못 찾으면 "
    "못 찾았다고 말하세요.\n"
    "- 한 턴에 제안 도구는 한 번만 호출하세요."
)

# Anthropic의 tool input_schema는 property 키가 ^[a-zA-Z0-9_.-]{1,64}$ 패턴이어야 해서
# (한글 키 불가) 한글 필드명을 그대로 쓰던 기존 스키마를 ASCII로 바꿨다. 실제 DB/화면 로직은
# 여전히 한글 필드명 그대로이므로, Claude가 ASCII 키로 호출하면 _도구_실행()에서 한글 키로
# 되돌려 기존 함수들에 넘긴다 (_ASCII_TO_한글, _사업항목_매핑, _관계항목_매핑 참고).
TOOLS = [
    {
        "name": "query_business_status",
        "description": (
            "사업현황 테이블에서 조건에 맞는 사업(계약) 목록을 조회한다. 인자를 하나도 지정하지 않으면 "
            "전체 목록을 반환한다(요약이 아니라 전체 행 전부). 업체명이나 용역명으로 특정 사업을 찾으려면 "
            "'query'를 사용하라 — 업체명·용역명 부분일치로 찾아준다. 그 외 사업구분(category), "
            "구분/신규·이월(type), 사업단계(stage), 담당자/PM(manager), 종료일 범위로도 필터링할 수 있다. "
            "결과에는 각 건의 id가 포함되며(결과는 한글 필드명: 구분/업체명/용역명/사업구분/담당자/"
            "주관참여구분/사업단계/진행률/시작일/종료일/계약금액/기수입금액/당해년도수입금액), "
            "수정/삭제/온톨로지 관계를 제안하려면 이 id가 필요하다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "업체명 또는 용역명에 포함된 단어로 검색 (부분일치)"},
                "category": {"type": "string", "description": "사업구분. 예: 상생형 스마트공장, 자율형공장 컨설팅 등"},
                "type": {"type": "string", "description": "구분(신규/이월). 예: 컨설팅_신규, 컨설팅_이월, 수탁_신규, 수탁_이월"},
                "stage": {
                    "type": "string",
                    "description": "사업단계. 예: 미분류, 사업 발굴, 수주 계획, 제안 진행, 계약 체결, 사업 수행",
                },
                "manager": {"type": "string", "description": "이 사업을 담당하는 PM/실무자 이름"},
                "end_before": {"type": "string", "description": "YYYY-MM-DD, 이 날짜 이전에 종료되는 건만"},
                "end_after": {"type": "string", "description": "YYYY-MM-DD, 이 날짜 이후에 종료되는 건만"},
            },
        },
    },
    {
        "name": "search_past_conversations",
        "description": (
            "이 시스템에서 나눈 모든 과거 대화(현재 보이는 대화창뿐 아니라 사용자가 만들었던 다른 "
            "대화창, 그리고 지금 대화에서 화면에 보이는 범위보다 더 오래된 부분까지 전부)에서 키워드로 "
            "텍스트를 검색한다. 사용자가 예전에 나눈 대화 내용을 참조할 때 사용한다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "찾고자 하는 키워드나 문구"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "import_uploaded_file_as_data",
        "description": (
            "지금 대화에 첨부된 엑셀/CSV 파일의 내용을 사업현황 데이터로 추가하자고 제안한다. "
            "사용자가 이 파일을 검토·분석해달라는 것이 아니라 실제로 데이터로 반영/등록하길 원한다고 "
            "판단될 때만 호출하라. 실제 컬럼 매핑과 값 정리는 시스템이 별도로 처리하며, 사용자 확인 "
            "후에만 반영된다."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "propose_add_business",
        "description": (
            "새 사업(계약) 1건 이상을 추가하자고 제안한다. 실제로 저장하지 않고 화면에 "
            "미리보기를 띄워 사용자 확인을 받기 위한 제안만 만든다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "business_list": {
                    "type": "array",
                    "description": "추가할 사업 목록. 각 항목은 아래 필드를 최대한 채워서 전달한다.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "description": "구분(신규/이월 등)"},
                            "company": {"type": "string", "description": "업체명"},
                            "project_name": {"type": "string", "description": "용역명"},
                            "category": {"type": "string", "description": "사업구분"},
                            "manager": {"type": "string", "description": "담당자 — 이 사업의 과제 책임자 1명"},
                            "role_type": {"type": "string", "description": "주관참여구분 — '주관' 또는 '참여' 중 하나"},
                            "stage": {
                                "type": "string",
                                "description": "사업단계 — 미분류/사업 발굴/수주 계획/제안 진행/계약 체결/사업 수행 중 하나",
                            },
                            "progress": {"type": "number", "description": "진행률(%)"},
                            "start_date": {"type": "string", "description": "시작일, YYYY-MM-DD"},
                            "end_date": {"type": "string", "description": "종료일, YYYY-MM-DD"},
                            "contract_amount": {"type": "number", "description": "계약금액"},
                            "received_amount": {"type": "number", "description": "기수입금액"},
                            "this_year_amount": {"type": "number", "description": "당해년도수입금액"},
                        },
                    },
                }
            },
            "required": ["business_list"],
        },
    },
    {
        "name": "propose_update_business",
        "description": (
            "기존 사업(계약) 1건의 특정 필드를 수정하자고 제안한다. 실제로 저장하지 않고 "
            "화면에 미리보기를 띄워 사용자 확인을 받기 위한 제안만 만든다. id는 반드시 "
            "query_business_status로 먼저 조회해 확인한 값을 사용해야 한다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "수정할 사업의 id (query_business_status 결과에서 확인)"},
                "changes": {
                    "type": "object",
                    "description": (
                        "한글 필드명: 새 값 쌍(이 안의 키는 한글 그대로 사용, ASCII 변환 대상 아님). "
                        "예: {\"사업단계\": \"사업 수행\", \"진행률\": 100}"
                    ),
                },
            },
            "required": ["id", "changes"],
        },
    },
    {
        "name": "propose_delete_business",
        "description": (
            "기존 사업(계약) 1건 이상을 삭제하자고 제안한다. 실제로 삭제하지 않고 화면에 "
            "삭제 대상 미리보기를 띄워 사용자 확인을 받기 위한 제안만 만든다. id는 반드시 "
            "query_business_status로 먼저 조회해 확인한 값을 사용해야 한다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ids": {"type": "array", "items": {"type": "integer"}, "description": "삭제할 사업 id 목록"},
            },
            "required": ["ids"],
        },
    },
    {
        "name": "propose_add_relations",
        "description": (
            "사업들 사이, 또는 사업과 개념(고객사/기술/담당자/산업분야 등) 사이의 관계(온톨로지 엣지)를 "
            "하나 이상 추가하자고 제안한다. 실제로 저장하지 않고 화면에 미리보기를 띄워 사용자 확인을 "
            "받기 위한 제안만 만든다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "relations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "node1_type": {
                                "type": "string",
                                "description": "'사업'이면 node1_business_id를 채운다. 아니면 자유 개념 유형(예: 고객사, 기술, 담당자, 산업분야)",
                            },
                            "node1_business_id": {
                                "type": "integer",
                                "description": "node1_type이 '사업'일 때, query_business_status로 확인한 정확한 id",
                            },
                            "node1_name": {
                                "type": "string",
                                "description": (
                                    "node1_type이 '사업'이 아니면 필수. '사업'이면 생략 가능(자동으로 용역명 "
                                    "사용). 직접 채운다면 업체명이 아니라 사업명/용역명을 사용할 것 — 같은 "
                                    "업체가 여러 사업을 진행할 수 있어 업체명만으로는 사업이 구분되지 않는다."
                                ),
                            },
                            "node2_type": {"type": "string", "description": "node1_type과 동일한 규칙"},
                            "node2_business_id": {"type": "integer"},
                            "node2_name": {"type": "string", "description": "node1_name과 동일한 규칙(업체명이 아닌 사업명/용역명 사용)"},
                            "relation_type": {
                                "type": "string",
                                "description": "예: 후속사업, 선행사업, 동일고객, 유사기술, 협력, 경쟁, 재사용 등 자유 텍스트",
                            },
                            "description": {"type": "string", "description": "관계에 대한 부가 설명(선택)"},
                        },
                        "required": ["node1_type", "node2_type", "relation_type"],
                    },
                }
            },
            "required": ["relations"],
        },
    },
    {
        "name": "query_ontology",
        "description": (
            "온톨로지(사업/개념 간 관계)에 이미 등록된 관계를 조회한다. 검색어를 지정하면 관련된 노드 이름, "
            "관계유형, 설명에서 부분일치로 찾아준다. 검색어 없이 호출하면 전체 관계를 반환한다. 새 관계를 "
            "제안하기 전에 이미 같은 관계가 있는지 확인하거나, 사용자가 '이 사업이랑 연결된 게 뭐야?' 같은 "
            "질문을 할 때 사용한다. 결과에는 각 관계의 id가 포함되며, 삭제를 제안하려면 이 id가 필요하다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "노드 이름, 관계유형, 설명에서 찾을 키워드(선택)"},
            },
        },
    },
    {
        "name": "propose_delete_relations",
        "description": (
            "온톨로지에 등록된 관계(엣지) 1건 이상을 삭제하자고 제안한다. 실제로 삭제하지 않고 화면에 "
            "삭제 대상 미리보기를 띄워 사용자 확인을 받기 위한 제안만 만든다. 관계 id는 반드시 "
            "query_ontology로 먼저 조회해 확인한 값을 사용해야 한다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "relation_ids": {"type": "array", "items": {"type": "integer"}, "description": "삭제할 관계 id 목록"},
            },
            "required": ["relation_ids"],
        },
    },
]

제안_도구명들 = {
    "propose_add_business", "propose_update_business", "propose_delete_business", "propose_add_relations",
    "import_uploaded_file_as_data", "propose_delete_relations",
}


def _텍스트_추출(response) -> str:
    """Anthropic 응답의 content 블록들 중 text 타입만 이어붙인다."""
    return "".join(block.text for block in response.content if block.type == "text")


def 조회_사업현황(
    검색어=None, 사업구분=None, 구분=None, 사업단계=None, 담당자=None, 종료일_이전=None, 종료일_이후=None
) -> list[dict]:
    if not DB_PATH.exists():
        return []

    조건절 = []
    파라미터 = []
    if 검색어:
        조건절.append("(업체명 LIKE ? OR 용역명 LIKE ?)")
        파라미터.append(f"%{검색어}%")
        파라미터.append(f"%{검색어}%")
    if 사업구분:
        조건절.append("사업구분 = ?")
        파라미터.append(사업구분)
    if 구분:
        조건절.append("구분 = ?")
        파라미터.append(구분)
    if 사업단계:
        조건절.append("사업단계 = ?")
        파라미터.append(사업단계)
    if 담당자:
        조건절.append("담당자 = ?")
        파라미터.append(담당자)
    if 종료일_이전:
        조건절.append("종료일 <= ?")
        파라미터.append(종료일_이전)
    if 종료일_이후:
        조건절.append("종료일 >= ?")
        파라미터.append(종료일_이후)

    where절 = f"WHERE {' AND '.join(조건절)}" if 조건절 else ""
    쿼리 = f"""
        SELECT id, 구분, 업체명, 용역명, 사업구분, 담당자, 주관참여구분, 사업단계, 진행률, 시작일, 종료일,
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


def search_past_conversations(검색어: str) -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT d.제목 AS 대화제목, c.role, c.content, c.생성일시
            FROM 채팅기록 c
            JOIN 대화 d ON d.id = c.대화_id
            WHERE c.content LIKE ?
            ORDER BY c.id DESC
            LIMIT 20
            """,
            (f"%{검색어}%",),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def propose_add_business(사업목록: list[dict]) -> dict:
    return {"확인": f"{len(사업목록)}건 추가를 제안했습니다. 화면에서 확인 후 반영됩니다."}


def propose_update_business(id: int, 변경필드: dict) -> dict:
    return {"확인": f"id={id} 건의 {list(변경필드.keys())} 변경을 제안했습니다. 화면에서 확인 후 반영됩니다."}


def propose_delete_business(ids: list[int]) -> dict:
    return {"확인": f"{len(ids)}건 삭제를 제안했습니다. 화면에서 확인 후 반영됩니다."}


def propose_add_relations(관계목록: list[dict]) -> dict:
    return {"확인": f"{len(관계목록)}개 관계 추가를 제안했습니다. 화면에서 확인 후 온톨로지에 반영됩니다."}


def import_uploaded_file_as_data() -> dict:
    return {"확인": "첨부 파일의 데이터 반영을 제안했습니다. 실제 해석은 시스템이 처리하며, 화면에서 확인 후 반영됩니다."}


def query_ontology(검색어: str | None = None) -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        쿼리 = """
            SELECT r.id, n1.이름 AS 출발, n1.유형 AS 출발유형, r.관계유형,
                   n2.이름 AS 도착, n2.유형 AS 도착유형, r.설명, r.작성자, r.생성일시
            FROM 온톨로지_관계 r
            JOIN 온톨로지_노드 n1 ON n1.id = r.출발_노드_id
            JOIN 온톨로지_노드 n2 ON n2.id = r.도착_노드_id
        """
        파라미터 = []
        if 검색어:
            쿼리 += " WHERE n1.이름 LIKE ? OR n2.이름 LIKE ? OR r.관계유형 LIKE ?"
            파라미터 = [f"%{검색어}%"] * 3
        쿼리 += " ORDER BY r.id DESC LIMIT 50"
        rows = conn.execute(쿼리, 파라미터).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def propose_delete_relations(관계_id_목록: list[int]) -> dict:
    return {"확인": f"{len(관계_id_목록)}개 관계 삭제를 제안했습니다. 화면에서 확인 후 반영됩니다."}


_상위_키_매핑 = {
    "query_business_status": {
        "query": "검색어", "category": "사업구분", "type": "구분", "stage": "사업단계",
        "manager": "담당자", "end_before": "종료일_이전", "end_after": "종료일_이후",
    },
    "search_past_conversations": {"query": "검색어"},
    "propose_add_business": {"business_list": "사업목록"},
    "propose_update_business": {"changes": "변경필드"},
    "propose_add_relations": {"relations": "관계목록"},
    "query_ontology": {"query": "검색어"},
    "propose_delete_relations": {"relation_ids": "관계_id_목록"},
}

_사업항목_키_매핑 = {
    "type": "구분", "company": "업체명", "project_name": "용역명", "category": "사업구분",
    "manager": "담당자", "role_type": "주관참여구분", "stage": "사업단계", "progress": "진행률",
    "start_date": "시작일", "end_date": "종료일", "contract_amount": "계약금액",
    "received_amount": "기수입금액", "this_year_amount": "당해년도수입금액",
}

_관계항목_키_매핑 = {
    "node1_type": "노드1_유형", "node1_business_id": "노드1_사업_id", "node1_name": "노드1_이름",
    "node2_type": "노드2_유형", "node2_business_id": "노드2_사업_id", "node2_name": "노드2_이름",
    "relation_type": "관계유형", "description": "설명",
}


def _키_변환(항목: dict, 매핑: dict) -> dict:
    return {매핑.get(k, k): v for k, v in 항목.items()}


def _도구_인자_한글화(name: str, tool_input: dict) -> dict:
    """Claude가 ASCII 키로 보낸 tool 인자를 기존 로직이 쓰는 한글 키로 되돌린다."""
    변환됨 = _키_변환(tool_input, _상위_키_매핑.get(name, {}))
    if name == "propose_add_business":
        변환됨["사업목록"] = [_키_변환(항목, _사업항목_키_매핑) for 항목 in 변환됨.get("사업목록", [])]
    elif name == "propose_add_relations":
        변환됨["관계목록"] = [_키_변환(항목, _관계항목_키_매핑) for 항목 in 변환됨.get("관계목록", [])]
    return 변환됨


def _도구_실행(name: str, tool_input: dict):
    if name == "query_business_status":
        return 조회_사업현황(**tool_input)
    if name == "search_past_conversations":
        return search_past_conversations(**tool_input)
    if name == "propose_add_business":
        return propose_add_business(**tool_input)
    if name == "propose_update_business":
        return propose_update_business(**tool_input)
    if name == "propose_delete_business":
        return propose_delete_business(**tool_input)
    if name == "propose_add_relations":
        return propose_add_relations(**tool_input)
    if name == "import_uploaded_file_as_data":
        return import_uploaded_file_as_data(**tool_input)
    if name == "query_ontology":
        return query_ontology(**tool_input)
    if name == "propose_delete_relations":
        return propose_delete_relations(**tool_input)
    raise ValueError(f"알 수 없는 도구: {name}")


대상_필드_설명 = {
    "구분": "계약 구분(신규/이월 등). 자유 텍스트이며 원본 표현을 그대로 사용.",
    "업체명": "고객사/발주처 이름",
    "용역명": "사업명/프로젝트명",
    "사업구분": "사업 카테고리/분야 (자유 텍스트)",
    "담당자": "이 사업의 과제 책임자 1명 이름",
    "주관참여구분": "'주관' 또는 '참여' 중 하나",
    "사업단계": "다음 6개 중 정확히 하나로만 매핑: 미분류, 사업 발굴, 수주 계획, 제안 진행, 계약 체결, 사업 수행",
    "진행률": "0~100 사이 진행률(%) 숫자",
    "시작일": "사업 시작일 (날짜)",
    "종료일": "사업 종료일 (날짜)",
    "계약금액": "총 계약금액(원)",
    "기수입금액": "지금까지 수금/기수입된 금액(원)",
    "당해년도수입금액": "올해 수입으로 잡히는 금액(원)",
}


def 업로드_매핑_추론(원본_컬럼들: list[str], 샘플_행들: list[dict], api_key: str | None = None) -> dict:
    """형식이 자유로운 업로드 파일의 컬럼명 -> 우리 시스템 필드명 매핑을 AI로 추론한다.

    금액/날짜 등 실제 값은 여기서 다루지 않는다(수치 오기 위험) — 어느 원본 컬럼이
    어떤 필드에 해당하는지, 그리고 사업단계 표현을 어떻게 표준값으로 바꿀지만 판단시킨다.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            key = None
    if not key:
        return {"오류": "ANTHROPIC_API_KEY가 설정되어 있지 않습니다."}

    client = Anthropic(api_key=key)
    프롬프트 = f"""다음은 사용자가 업로드한 엑셀/CSV의 컬럼명과 샘플 데이터입니다.
컬럼명이나 순서가 우리 시스템 형식과 다를 수 있습니다.

원본 컬럼명: {json.dumps(원본_컬럼들, ensure_ascii=False)}
샘플 행(최대 5개): {json.dumps(샘플_행들, ensure_ascii=False, default=str)}

아래 대상 필드 각각에 대해, 원본 컬럼 중 가장 적합한 것을 하나씩 골라 매핑하세요.
대응되는 원본 컬럼이 없으면 null로 두세요.

대상 필드 설명:
{json.dumps(대상_필드_설명, ensure_ascii=False, indent=2)}

그리고 원본 데이터의 사업단계(또는 그에 해당하는 컬럼)에 등장하는 표현들을
반드시 미분류/사업 발굴/수주 계획/제안 진행/계약 체결/사업 수행 중 하나로 매핑하는
"사업단계_값매핑" 딕셔너리도 함께 만드세요 (예: "진행중" -> "사업 수행", "제안중" -> "제안 진행").
확신이 없으면 "미분류"로 매핑하세요 — 예전 값과 이 5단계는 정확히 대응하지 않을 수 있습니다.

다른 설명 없이 아래 JSON 형식으로만 답하세요(코드블록 없이 JSON만):
{{"매핑": {{"구분": "원본컬럼명 또는 null", "업체명": "...", ...}}, "사업단계_값매핑": {{"원본표현": "표준값"}}}}"""

    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=2048,
        messages=[{"role": "user", "content": 프롬프트}],
    )
    return json.loads(_텍스트_추출(response).strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())


def 대화_제목_생성(첫_메시지: str, api_key: str | None = None) -> str:
    """대화의 첫 메시지를 짧은 제목으로 요약한다. 실패하면 원문을 잘라 그대로 돌려준다."""
    기본_제목 = 첫_메시지.strip().splitlines()[0][:30] if 첫_메시지.strip() else "새 대화"

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            key = None
    if not key:
        return 기본_제목

    try:
        client = Anthropic(api_key=key)
        response = client.messages.create(
            model=제목생성_MODEL_NAME,
            max_tokens=30,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "다음 메시지를 대화 제목으로 쓸 수 있도록 5~10자 내외의 한국어 명사구로 "
                        "간결하게 요약하세요. 따옴표, 마침표, 설명 없이 제목 텍스트만 출력하세요.\n\n"
                        f"메시지: {첫_메시지[:500]}"
                    ),
                }
            ],
        )
        제목 = _텍스트_추출(response).strip().strip('"').strip("'")
        return 제목 or 기본_제목
    except Exception:
        return 기본_제목


def 질의하기(question: str, history: list[dict] | None = None, api_key: str | None = None) -> dict:
    """자연어 질문 -> Claude가 SQLite를 조회하거나 변경을 제안하며 답변 생성

    history: [{"role": "user"/"assistant", "content": "..."}] 형태의 이전 대화 이력.
    도구 호출 내역은 이번 턴 안에서만 쓰고 반환값에는 포함하지 않는다.

    반환값: {"text": 답변 문자열, "pending_action": {"유형": 도구명, "인자": {...}} 또는 None}
    pending_action은 실제로 반영된 것이 아니라 사용자 확인이 필요한 제안이다.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            key = None
    if not key:
        return {
            "text": "ANTHROPIC_API_KEY가 설정되어 있지 않습니다. .env 파일(로컬) 또는 Streamlit Cloud의 Secrets 설정을 확인하세요.",
            "pending_action": None,
        }

    client = Anthropic(api_key=key)
    messages = list(history or []) + [{"role": "user", "content": question}]

    대기중_제안 = None
    for _ in range(5):  # 도구 호출 반복 상한
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=TOOLS,
        )

        if response.stop_reason != "tool_use":
            return {"text": _텍스트_추출(response), "pending_action": 대기중_제안}

        messages.append({"role": "assistant", "content": response.content})

        결과_블록들 = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            도구_인자 = _도구_인자_한글화(block.name, block.input or {})
            결과 = _도구_실행(block.name, 도구_인자)
            if block.name in 제안_도구명들:
                대기중_제안 = {"유형": block.name, "인자": 도구_인자}
            결과_블록들.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(결과, ensure_ascii=False),
            })
        messages.append({"role": "user", "content": 결과_블록들})

    return {"text": "질의 처리 중 도구 호출 횟수 상한을 초과했습니다.", "pending_action": 대기중_제안}
