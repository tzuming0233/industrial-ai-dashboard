"""
산업AI팀 사업 통합관리 - AI 채팅 자연어 질의

SQLite 조회 함수 1개를 Claude의 tool(도구 호출)로 등록해
자연어 질의에 답한다.

사용 전 준비:
    1) pip install -r requirements.txt
    2) 환경변수 ANTHROPIC_API_KEY 설정 (.env.example 참고)
"""

import base64
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
    "말투와 태도: 유능하고 직접적인 동료처럼 말하세요 — 콜센터 상담원이나 챗봇 톤이 아닙니다. "
    "'무엇이든 도와드릴게요!', '편하게 말씀하세요!', '필요한 거 있으면 말씀해주세요' 같은 상투적인 "
    "서비스업 인사말이나 스몰토크로 답을 열지 마세요. 이모지는 원칙적으로 쓰지 않습니다(사용자가 먼저 "
    "이모지를 쓰며 그런 분위기를 원하는 게 분명할 때만 아주 가끔 예외). 느낌표도 과하게 쓰지 말고, 실제로 "
    "놀랍거나 강조할 내용이 있을 때만 쓰세요. 질문을 받으면 인사치레 없이 바로 본론부터 답하고, 자기소개나 "
    "'무엇을 도와드릴까요' 같은 문구는 사용자가 먼저 인사하거나 뭘 할 수 있는지 물었을 때만 짧게 답하세요. "
    "확신 있게 말하되 뻔한 소리로 채우지 말고, 모르면 모른다고 하세요.\n\n"
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
    "(예: '이번주 월요일'을 특정 날짜로 해석했다고 언급). 지나치게 자주 되묻는 것은 사용자를 피곤하게 합니다. "
    "정말 되물어야 할 때, 그 갈림길이 2~4개의 명확한 선택지로 나뉜다면 자유 텍스트 질문 대신 "
    "ask_clarifying_question 도구를 써서 구조화된 선택지로 물으세요 — 사용자가 버튼 하나로 답할 수 있어 "
    "훨씬 편합니다. 선택지가 명확히 나뉘지 않거나 자유 서술이 필요하면 그냥 자연어로 물으세요.\n"
    "- query_business_status의 '검색어'는 업체명·용역명에 대한 단순 문자열 부분일치(SQL LIKE)일 뿐, "
    "의미나 약어를 이해하지 못합니다. '대학이 들어간 사업'처럼 이름의 의미·줄임말까지 판단해야 하는 "
    "질문에서는 검색어 필터에 의존하지 말고 인자 없이 호출해 전체 목록을 받아온 뒤 당신의 지식으로 "
    "직접 판단하세요 (예: '포항공대'·'한국공대'는 '포항공과대학교'·'한국공과대학교'의 약칭이므로 대학입니다 — "
    "이 글자들이 문자 그대로 '대학'을 포함하지 않아도 의미상 맞다고 판단해야 합니다). 이 시스템의 사업 "
    "건수는 많지 않으므로 전체를 가져와 직접 훑어봐도 괜찮습니다.\n"
    "- '몇 건이야', '담당자별로 얼마씩이야', '단계별 건수', '전체 계약금액 합계' 같은 개수·합계·그룹별 "
    "통계 질문에는 query_business_status로 전체 행을 받아 직접 세거나 더하지 말고 summarize_business_status를 "
    "먼저 쓰세요 — 서버가 SQL로 정확히 집계해줍니다. 단, 위처럼 이름의 의미·약칭까지 판단해야 하는 "
    "그룹핑(예: '대학이 들어간 사업 몇 건')은 이 도구의 group_by가 다루지 못하므로 query_business_status로 "
    "전체를 받아 직접 판단하세요.\n"
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
    "만들며, '위키' 탭의 그래프 뷰에서 쌓입니다. 새 관계를 제안하기 전에 query_ontology로 이미 같은 "
    "관계가 있는지 확인해 중복 추가를 피하세요. 사용자가 '이 사업이랑 연결된 게 뭐야?' 같은 질문을 하면 "
    "query_ontology로 실제로 찾아본 뒤 답하세요. 사용자가 관계를 완전히 지우고 싶어하면 query_ontology로 "
    "정확한 관계 id를 확인한 뒤 propose_delete_relations로 제안하세요. 관계유형이나 설명만 잘못됐다면 "
    "(어느 노드끼리 연결됐는지는 그대로) 지우고 새로 만들 필요 없이 propose_update_relations로 그 부분만 "
    "고치자고 제안하세요.\n"
    "- 사용자가 '저번에', '예전에 얘기했잖아', '이전 대화에서' 같은 표현으로 지금 보이는 대화 범위보다 "
    "더 오래된 내용이나 다른 대화창에서 나눴던 내용을 참조하면, search_past_conversations로 이 시스템의 "
    "전체 대화 기록(다른 대화창 포함)을 검색해서 실제로 찾아본 뒤 답하세요. 짐작으로 답하지 말고, 못 찾으면 "
    "못 찾았다고 말하세요.\n"
    "- '위키' 탭에는 사용자가 쓴 개인 노트가 쌓입니다. 노트 관련 질문이나 '이거 노트로 남겨줘' 같은 요청을 "
    "받으면 query_notes로 먼저 실제로 찾아본 뒤 답하거나, propose_add_note/propose_update_note로 추가·수정을 "
    "제안하세요(수정은 반드시 먼저 query_notes로 정확한 id를 확인). 노트를 지워달라는 요청도 같은 방식으로 "
    "query_notes로 id를 확인한 뒤 propose_delete_note로 제안하세요. 노트끼리, 또는 노트와 사업 사이에 관련이 "
    "있다는 이야기가 나오면 propose_add_relations를 그대로 쓰되 노드 유형을 '노트'로, 이름은 노트 제목으로 "
    "지정하세요 — 옵시디언의 위키링크처럼 노트는 제목으로 식별되므로 같은 제목이면 같은 노드로 합쳐집니다. "
    "다만 노트끼리의 연결이라면, 노트 본문에 [[다른 노트 제목]]을 써넣으면 저장할 때 시스템이 자동으로 "
    "그래프에 연결한다는 점도 알아두세요 — 노트 내용을 정리하며 다른 노트를 언급할 때는 이 문법을 직접 "
    "써주는 것도 좋은 방법입니다(propose_add_note/propose_update_note의 content에 [[제목]]을 포함시키면 됨).\n"
    "- 사내 데이터로 답할 수 없는 최신 정보(뉴스, 특정 기업/기술 동향, 최근 정책·규정, 업계 시황 등)가 "
    "필요하면 web_search로 실제로 찾아본 뒤 답하세요. 사업현황·노트·온톨로지로 답할 수 있는 질문에는 "
    "굳이 웹 검색을 쓰지 마세요.\n"
    "- 답변은 훑어보기 좋게 정돈하세요. 숫자 하나·예/아니오처럼 짧은 사실 하나만 답할 땐 자연스러운 "
    "문장 한두 줄로 충분하지만, 근거·항목·단계가 여러 개 섞인 답변을 전부 이어 쓴 문단 하나로 몰아넣지 "
    "마세요 — 핵심 결론이나 답부터 굵게 한 줄로 먼저 제시한 뒤 근거를 풀어내고, 서로 구분되는 항목·비교· "
    "단계가 3개 이상이면 목록이나 표로 나누고, 핵심 수치·사업명·결론처럼 훑어볼 때 바로 눈에 띄어야 할 "
    "부분은 굵게 표시하세요. 문단이 길어지면 한 문단에 여러 화제를 몰아넣지 말고 줄바꿈으로 나누세요. "
    "다만 이 채팅 패널은 좁아서 '#'/'##' 같은 큰 제목은 문서처럼 무겁게 보입니다 — 화제를 나눌 땐 제목 "
    "대신 굵은 소제목 문구나 '###' 정도의 작은 제목만 쓰세요. 그리고 모든 문장을 목록화하거나 두 문장짜리 "
    "답에까지 제목·표를 붙이는 과한 형식주의도 피하세요 — 목적은 장식이 아니라 빠르게 훑고 필요한 부분을 "
    "바로 찾게 하는 것입니다.\n"
    "- 요청이 여러 갈래로 해석되고 그 차이가 결과에 실질적인 영향을 줄 때는(예: 어느 사업을 가리키는지 "
    "특정이 안 될 때, 삭제·수정 범위가 애매할 때) 짐작해서 진행하지 말고 짧게 되물으세요. 상식적으로 뜻이 "
    "분명한 경우까지 되묻지 말라는 원칙은 그대로입니다 — 정말 갈림길일 때만 확인하세요.\n"
    "- 조회 결과(query_business_status, query_ontology, query_notes, web_search 등)를 근거로 답할 때는 "
    "어디서 나온 정보인지 자연스럽게 밝히세요(예: '현재 DB 기준으로는...', '웹 검색 결과에 따르면...'). "
    "특히 web_search로 얻은 정보는 사내 데이터와 성격이 다르므로, 시점이나 출처가 중요한 맥락이면 "
    "언급하세요.\n"
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
        "name": "summarize_business_status",
        "description": (
            "사업현황 데이터를 건수/금액 기준으로 집계해서 반환한다. '사업단계별로 몇 건이야', "
            "'담당자별 계약금액 합계는', '전체 몇 건이야' 같은 개수·합계·그룹별 통계 질문에는 "
            "query_business_status로 전체 행을 받아 직접 세지 말고 이 도구를 먼저 써라 — 서버가 "
            "SQL로 정확히 집계해서 돌려준다. group_by를 지정하면 그 기준별로 나눠서, 지정하지 "
            "않으면 전체 합계 한 줄을 반환한다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "group_by": {
                    "type": "string",
                    "enum": ["담당자", "사업구분", "사업단계", "구분"],
                    "description": "이 기준으로 그룹을 나눠 집계한다. 생략하면 전체 합계만 반환.",
                },
                "metric": {
                    "type": "string",
                    "enum": ["건수", "계약금액합계", "기수입금액합계"],
                    "description": "집계할 지표. 생략하면 건수/계약금액합계/기수입금액합계 모두 반환.",
                },
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
        "name": "propose_update_relations",
        "description": (
            "기존 관계(엣지) 1건 이상의 관계유형/설명을 수정하자고 제안한다. 실제로 저장하지 않고 화면에 "
            "미리보기를 띄워 사용자 확인을 받기 위한 제안만 만든다. 관계 id는 반드시 query_ontology로 "
            "먼저 조회해 확인한 값을 사용해야 한다. 어느 노드끼리 연결됐는지(출발/도착) 자체를 바꾸려면 "
            "이 도구 대신 propose_delete_relations로 지우고 propose_add_relations로 새로 추가하라 — "
            "이 도구는 관계유형·설명만 고친다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "relation_id": {"type": "integer", "description": "수정할 관계의 id (query_ontology 결과에서 확인)"},
                            "relation_type": {"type": "string", "description": "새 관계유형(선택 — 안 바꾸려면 생략)"},
                            "description": {"type": "string", "description": "새 설명(선택 — 안 바꾸려면 생략)"},
                        },
                        "required": ["relation_id"],
                    },
                },
            },
            "required": ["updates"],
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
    {
        "name": "query_notes",
        "description": (
            "'위키' 탭에 사용자가 쓴 노트를 조회한다. 검색어를 지정하면 제목·내용·태그에서 부분일치로 "
            "찾아준다. 검색어 없이 호출하면 전체 노트 목록(제목/태그만, 내용은 요약 없이 생략)을 반환한다 "
            "— 특정 노트 내용을 인용하거나 답변 근거로 쓰려면 먼저 이걸로 후보를 찾은 뒤, 필요하면 "
            "제목으로 다시 좁혀 검색해 내용까지 확인하라. 노트를 수정/정리하자고 제안하기 전에는 반드시 "
            "이걸로 먼저 조회해 정확한 id를 확인해야 한다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "제목/내용/태그에서 찾을 키워드(선택, 없으면 전체 목록)"},
            },
        },
    },
    {
        "name": "propose_add_note",
        "description": (
            "새 노트를 위키 탭에 추가하자고 제안한다. 실제로 저장하지 않고 화면에 미리보기를 띄워 사용자 "
            "확인을 받기 위한 제안만 만든다. 사용자가 대화 중 이야기한 내용을 노트로 남겨달라고 하거나, "
            "정리해서 저장해달라고 할 때 사용하라."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "노트 제목 — 옵시디언처럼 이 제목으로 다른 노트와 연결/식별된다"},
                "content": {"type": "string", "description": "노트 본문(마크다운)"},
                "tags": {"type": "string", "description": "콤마로 구분한 태그(선택, 예: '기술,아이디어')"},
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "propose_update_note",
        "description": (
            "기존 노트의 제목/내용/태그를 수정하자고 제안한다. 실제로 저장하지 않고 화면에 미리보기를 "
            "띄워 사용자 확인을 받기 위한 제안만 만든다. id는 반드시 query_notes로 먼저 조회해 확인한 "
            "값을 사용해야 한다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "수정할 노트의 id (query_notes 결과에서 확인)"},
                "changes": {
                    "type": "object",
                    "description": (
                        "한글 필드명: 새 값 쌍(이 안의 키는 한글 그대로 사용). "
                        "예: {\"제목\": \"새 제목\", \"내용\": \"새 본문\", \"태그\": \"기술,아이디어\"}"
                    ),
                },
            },
            "required": ["id", "changes"],
        },
    },
    {
        "name": "propose_delete_note",
        "description": (
            "'위키' 탭의 노트 1건 이상을 삭제하자고 제안한다. 실제로 삭제하지 않고 화면에 삭제 대상 "
            "미리보기를 띄워 사용자 확인을 받기 위한 제안만 만든다. id는 반드시 query_notes로 먼저 "
            "조회해 확인한 값을 사용해야 한다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "note_ids": {"type": "array", "items": {"type": "integer"}, "description": "삭제할 노트 id 목록"},
            },
            "required": ["note_ids"],
        },
    },
    {
        "name": "create_file",
        "description": (
            "사용자가 다운로드할 수 있는 실제 파일을 만든다. 확인 없이 즉시 만들어져 채팅에 다운로드 "
            "링크로 뜬다(다른 propose_* 도구와 달리 사용자 확인 절차가 없음 — 되돌릴 위험이 있는 "
            "동작이 아니기 때문). 답변이 코드/보고서/정리된 문서/표 형태의 데이터처럼 그 자체로 "
            "파일로 저장해둘 가치가 있다고 판단되면, 사용자가 명시적으로 요청하지 않아도 먼저 "
            "제안하듯 만들어도 된다. 단, content의 형식은 filename 확장자에 따라 반드시 다음 규칙을 "
            "따라야 한다 — 규칙을 어기면 파일이 깨진다:\n"
            "- .xlsx: content를 쉼표로 구분된 CSV 텍스트로 작성(첫 줄은 헤더). 예: 'a,b\\n1,2\\n3,4'\n"
            "- .docx: content를 마크다운으로 작성. '# '는 제목1, '## '는 제목2, '### '는 제목3, "
            "'- '는 글머리 목록, 그 외 줄은 일반 본문 문단으로 변환된다.\n"
            "- .pptx: 슬라이드를 줄 단독으로 '---'만 있는 줄로 구분한다. 각 슬라이드의 첫 줄이 제목"
            "('# ' 접두사는 있어도 없어도 됨), 이후 줄들이 본문 목록이 된다.\n"
            "- 그 외 확장자(.md/.txt/.py/.js/.ts/.html/.svg/.css/.json/.csv/.sql/.yaml 등)는 content를 "
            "그대로 텍스트 파일로 만든다 — 실제 만들려는 내용 그대로 작성하면 된다.\n"
            "- .html/.svg는 다운로드 대신 새 탭에서 바로 렌더링되어 보인다 — 인포그래픽, 카드형 "
            "요약, 다이어그램, 시각적으로 꾸민 보고서처럼 '보여주는' 게 목적인 결과물은 완결된 "
            "<style> 태그를 포함한 자체완결형(self-contained) HTML로 만드는 게 markdown/docx보다 "
            "훨씬 낫다(진짜 이미지를 생성하는 건 아니므로 CSS/이모지/SVG로 시각을 구성하라).\n"
            "한 턴에 파일은 최대 1개만 만드세요."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "확장자를 포함한 파일명. 예: '분기보고서.docx', '데이터.xlsx'"},
                "content": {"type": "string", "description": "위 설명의 확장자별 규칙에 맞춰 작성한 파일 내용"},
            },
            "required": ["filename", "content"],
        },
    },
    {
        "name": "ask_clarifying_question",
        "description": (
            "요청이 여러 갈래로 해석될 수 있고 그 차이가 결과에 실질적인 영향을 줄 때, 자유 텍스트로 "
            "되묻는 대신 선택지가 2~4개로 명확히 나뉘면 이 도구로 구조화된 질문을 던진다. 선택지가 "
            "애매하거나 자유 서술형 답이 필요한 경우에는 이 도구를 쓰지 말고 그냥 자연어로 물어라. "
            "이 도구를 호출하면 이번 턴은 그 즉시 끝나고 사용자의 선택을 기다린다 — 같은 턴 안에서 "
            "다른 도구를 이어서 호출하거나 텍스트를 더 생성하지 마라."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "사용자에게 물어볼 질문"},
                "options": {
                    "type": "array",
                    "description": "사용자가 고를 수 있는 선택지 2~4개",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "선택지의 짧은 이름"},
                            "description": {"type": "string", "description": "선택지에 대한 부연 설명(선택)"},
                        },
                        "required": ["label"],
                    },
                },
            },
            "required": ["question", "options"],
        },
    },
    # Anthropic이 서버에서 직접 실행하는 서버 도구 — 클라이언트 쪽 실행 코드(_도구_실행 분기)가
    # 필요 없다. tool_use가 아니라 server_tool_use/web_search_tool_result 블록으로 응답에 섞여
    # 오고, stop_reason도 보통 "tool_use"가 아니라 "end_turn"이라 기존 도구 호출 루프를 그대로
    # 통과한다(질의하기_스트림의 for block ... if block.type != "tool_use": continue가 자연히
    # 걸러줌).
    {
        "type": "web_search_20260209",
        "name": "web_search",
        "max_uses": 5,
        # 도구 목록 전체(꽤 큰 정적 텍스트)를 여기 한 곳에서 캐싱 — 마지막 블록에 걸면
        # 그 앞의 모든 도구 정의가 함께 캐시된다. 한 턴 안에서 도구 호출이 이어질 때나
        # 다음 대화 턴에서 똑같은 도구 목록을 다시 보낼 때 그대로 재사용된다.
        "cache_control": {"type": "ephemeral"},
    },
]

제안_도구명들 = {
    "propose_add_business", "propose_update_business", "propose_delete_business", "propose_add_relations",
    "import_uploaded_file_as_data", "propose_delete_relations", "propose_update_relations",
    "propose_add_note", "propose_update_note", "propose_delete_note",
}

# 스트리밍 중 "지금 뭘 하고 있는지" 화면에 보여주기 위한 도구별 상태 문구.
_도구_상태_문구 = {
    "query_business_status": "사업현황을 조회하는 중...",
    "summarize_business_status": "사업현황을 집계하는 중...",
    "search_past_conversations": "과거 대화를 검색하는 중...",
    "query_ontology": "온톨로지를 조회하는 중...",
    "propose_add_business": "추가할 내용을 정리하는 중...",
    "propose_update_business": "수정할 내용을 정리하는 중...",
    "propose_delete_business": "삭제 대상을 정리하는 중...",
    "propose_add_relations": "추가할 관계를 정리하는 중...",
    "propose_delete_relations": "삭제할 관계를 정리하는 중...",
    "propose_update_relations": "수정할 관계를 정리하는 중...",
    "import_uploaded_file_as_data": "업로드한 파일을 반영할 준비를 하는 중...",
    "query_notes": "노트를 조회하는 중...",
    "propose_add_note": "노트 내용을 정리하는 중...",
    "propose_update_note": "수정할 노트 내용을 정리하는 중...",
    "propose_delete_note": "삭제할 노트를 정리하는 중...",
    "create_file": "파일을 만드는 중...",
    "ask_clarifying_question": "질문을 정리하는 중...",
    "web_search": "웹을 검색하는 중...",
}


def _텍스트_추출(response) -> str:
    """Anthropic 응답의 content 블록들 중 text 타입만 이어붙인다."""
    return "".join(block.text for block in response.content if block.type == "text")


# "최대한 다채롭게", "표·그래프 다 넣어서" 같은 요청은 생각(thinking)+본문 텍스트+
# create_file의 큰 HTML을 한 응답 안에서 전부 만들다 max_tokens에 걸려 중간에
# 끊기는 사고가 실제로 재현됐다(라이브 테스트로 확인) — 도구 호출 반복 상한도
# 5회는 "자료 조회 여러 번 + 파일 생성 + 마무리 답변"에 빠듯해서 8회로 올렸다.
_도구_호출_반복_상한 = 8
_블로킹_최대_출력_토큰 = 16000
_스트리밍_최대_출력_토큰 = 32000


def _잘림_안내(부분_텍스트: str) -> str:
    """stop_reason이 max_tokens일 때(응답이 중간에 잘렸을 때) 빈 화면 대신 사용자가
    실제로 무슨 일이 있었는지 알 수 있게 안내를 덧붙인다."""
    안내 = "\n\n*(※ 답변이 길어져 여기서 잘렸습니다. 더 간단하게 나눠서 다시 요청해주세요.)*"
    return (부분_텍스트 or "") + 안내


def _사용자_메시지_구성(question: str, 첨부_문서_바이트: bytes | None):
    """PDF를 텍스트로 미리 뽑아내는 대신 원본 그대로 첨부해, Claude가 텍스트뿐
    아니라 스캔본·표·차트가 이미지로 박힌 페이지까지 직접 읽게 한다 — Anthropic
    공식 document 콘텐츠 블록(별도 OCR/래스터화 코드 불필요, docs.anthropic.com
    으로 확인한 실제 API 모양)."""
    if not 첨부_문서_바이트:
        return question
    return [
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.standard_b64encode(첨부_문서_바이트).decode("ascii"),
            },
        },
        {"type": "text", "text": question},
    ]


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


_집계_지표_컬럼 = {
    "건수": "COUNT(*) AS 건수",
    "계약금액합계": "SUM(계약금액) AS 계약금액합계",
    "기수입금액합계": "SUM(기수입금액) AS 기수입금액합계",
}
_집계_허용_그룹기준 = {"담당자", "사업구분", "사업단계", "구분"}


def 조회_사업현황_집계(그룹기준: str | None = None, 지표: str | None = None) -> list[dict]:
    if not DB_PATH.exists():
        return []
    if 그룹기준 and 그룹기준 not in _집계_허용_그룹기준:
        raise ValueError(f"지원하지 않는 group_by입니다: {그룹기준}")
    if 지표 and 지표 not in _집계_지표_컬럼:
        raise ValueError(f"지원하지 않는 metric입니다: {지표}")

    지표_목록 = [지표] if 지표 else list(_집계_지표_컬럼)
    선택절 = ", ".join(_집계_지표_컬럼[m] for m in 지표_목록)
    그룹_선택 = f"{그룹기준}, " if 그룹기준 else ""
    쿼리 = f"""
        SELECT {그룹_선택}{선택절}
        FROM 사업현황
        {"GROUP BY " + 그룹기준 if 그룹기준 else ""}
        {"ORDER BY " + 그룹기준 if 그룹기준 else ""}
    """

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(쿼리).fetchall()
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


def propose_update_relations(변경목록: list[dict]) -> dict:
    return {"확인": f"{len(변경목록)}개 관계 수정을 제안했습니다. 화면에서 확인 후 반영됩니다."}


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


def 노트_임베딩_생성(텍스트: str, 용도: str = "document", api_key: str | None = None) -> list[float] | None:
    """Voyage AI(voyage-4-lite)로 텍스트 임베딩 1건을 만든다. 노트 저장 시 재임베딩과
    query_notes의 시맨틱 검색에 쓰인다. 용도는 Voyage의 input_type 그대로("document"는
    저장할 노트, "query"는 검색어) — 같은 모델이라도 이 구분이 검색 품질에 영향을 준다.
    키가 없거나 호출이 실패하면 None을 돌려주고, 이 실패가 노트 저장 자체를 막지는
    않는다(다른 보조 AI 호출들과 같은 관례 — 실패해도 앱이 멈추지 않음)."""
    key = api_key or os.environ.get("VOYAGE_API_KEY")
    if not key or not (텍스트 or "").strip():
        return None
    try:
        import voyageai

        client = voyageai.Client(api_key=key)
        결과 = client.embed([텍스트], model="voyage-4-lite", input_type=용도)
        return 결과.embeddings[0]
    except Exception:
        return None


def _노트_의미검색(conn: sqlite3.Connection, 검색어: str, 제외_id: set[int], 상위_개수: int = 5) -> list[dict]:
    """키워드로 못 찾은, 의미상 관련된 노트를 임베딩 유사도로 추가 검색한다."""
    질의_벡터 = 노트_임베딩_생성(검색어, 용도="query")
    if 질의_벡터 is None:
        return []
    임베딩_행들 = conn.execute("SELECT 노트_id, 벡터 FROM 노트_임베딩").fetchall()
    if not 임베딩_행들:
        return []

    import numpy as np

    질의 = np.array(질의_벡터, dtype=np.float32)
    질의_크기 = np.linalg.norm(질의) or 1.0
    후보들 = []
    for 노트_id, 벡터_바이트 in 임베딩_행들:
        if 노트_id in 제외_id:
            continue
        벡터 = np.frombuffer(벡터_바이트, dtype=np.float32)
        유사도 = float(np.dot(질의, 벡터) / (질의_크기 * (np.linalg.norm(벡터) or 1.0)))
        if 유사도 >= 0.3:
            후보들.append((유사도, 노트_id))
    if not 후보들:
        return []
    후보들.sort(key=lambda x: x[0], reverse=True)
    상위_id들 = [노트_id for _, 노트_id in 후보들[:상위_개수]]

    conn.row_factory = sqlite3.Row
    자리표시자 = ",".join("?" * len(상위_id들))
    rows = conn.execute(
        f"SELECT id, 제목, 태그, 생성일시, 수정일시 FROM 노트 WHERE id IN ({자리표시자})",
        상위_id들,
    ).fetchall()
    순서 = {노트_id: i for i, 노트_id in enumerate(상위_id들)}
    결과 = [dict(row) for row in rows]
    결과.sort(key=lambda r: 순서.get(r["id"], len(상위_id들)))
    return 결과


def query_notes(검색어: str | None = None) -> list[dict]:
    """repository.py의 노트_검색과 같은 쿼리를 여기서도 직접 짠다 — 이 파일은 다른 조회 도구들과
    마찬가지로 repository.py를 거치지 않고 자체 커넥션으로 SQLite를 읽는 관례를 따른다.

    검색어가 있으면 기존 키워드(LIKE) 검색 결과에 더해, 임베딩 기반 시맨틱 검색으로
    찾은 의미상 관련된 노트도 뒤에 이어붙인다(Voyage 키가 없으면 조용히 건너뜀 —
    키워드 검색만으로도 그대로 동작)."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        if 검색어:
            rows = conn.execute(
                "SELECT id, 제목, 태그, 생성일시, 수정일시 FROM 노트 "
                "WHERE 제목 LIKE ? OR 내용 LIKE ? OR 태그 LIKE ? ORDER BY 수정일시 DESC LIMIT 50",
                (f"%{검색어}%", f"%{검색어}%", f"%{검색어}%"),
            ).fetchall()
            결과 = [dict(row) for row in rows]
            기존_id_집합 = {행["id"] for 행 in 결과}
            결과 += _노트_의미검색(conn, 검색어, 기존_id_집합)
            return 결과
        rows = conn.execute(
            "SELECT id, 제목, 태그, 생성일시, 수정일시 FROM 노트 ORDER BY 수정일시 DESC LIMIT 50"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def propose_add_note(제목: str, 내용: str, 태그: str = "") -> dict:
    return {"확인": f"'{제목}' 노트 추가를 제안했습니다. 화면에서 확인 후 반영됩니다."}


def propose_update_note(id: int, 변경필드: dict) -> dict:
    return {"확인": f"id={id} 노트의 {list(변경필드.keys())} 변경을 제안했습니다. 화면에서 확인 후 반영됩니다."}


def propose_delete_note(노트_id_목록: list[int]) -> dict:
    return {"확인": f"{len(노트_id_목록)}개 노트 삭제를 제안했습니다. 화면에서 확인 후 반영됩니다."}


def create_file(파일명: str, 내용: str) -> dict:
    """다른 propose_* 함수들처럼 확인 문구만 돌려준다 — 실제 바이트 생성은 스트리밍 루프
    (질의하기_스트림)에서만 하고 tool_result에는 포함하지 않는다(컨텍스트에 바이너리를 안 넣기 위함).
    블로킹 버전(질의하기, Streamlit용)에서 호출돼도 에러 없이 확인만 하고 끝난다."""
    return {"확인": f"'{파일명}' 파일을 만들었습니다. 화면에 다운로드 링크가 표시됩니다."}


def ask_clarifying_question(질문: str, 선택지: list[dict]) -> dict:
    """create_file과 같은 패턴 — 실제 화면 표시(질문_대기 필드)는 스트리밍 루프에서 처리하고,
    여기서는 확인 문구만 돌려준다."""
    return {"확인": f"'{질문}' 질문을 사용자에게 구조화된 선택지로 물었습니다. 사용자의 다음 메시지를 기다리세요."}


def 노트_위키_정리(내용: str, api_key: str | None = None) -> str:
    """원본 노트를 구조화된 위키 문서로 정리한다. 원문에 없는 사실을 지어내지 않고, 제목/섹션 구성만 다듬는다."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            key = None
    if not key:
        return 내용

    client = Anthropic(api_key=key)
    프롬프트 = f"""다음은 사용자가 쓴 원본 노트입니다. 이 내용을 위키 문서처럼 명확한 구조(제목, 필요하면
소제목·목록)를 갖춘 마크다운으로 정리해주세요. 원문에 없는 사실을 지어내지 말고, 정리·재구성만 하세요.
설명 없이 정리된 마크다운 본문만 출력하세요.

원본 노트:
{내용}"""
    response = client.messages.create(
        model=MODEL_NAME, max_tokens=4096, messages=[{"role": "user", "content": 프롬프트}],
    )
    return _텍스트_추출(response).strip()


_상위_키_매핑 = {
    "query_business_status": {
        "query": "검색어", "category": "사업구분", "type": "구분", "stage": "사업단계",
        "manager": "담당자", "end_before": "종료일_이전", "end_after": "종료일_이후",
    },
    "summarize_business_status": {"group_by": "그룹기준", "metric": "지표"},
    "search_past_conversations": {"query": "검색어"},
    "propose_add_business": {"business_list": "사업목록"},
    "propose_update_business": {"changes": "변경필드"},
    "propose_add_relations": {"relations": "관계목록"},
    "propose_update_relations": {"updates": "변경목록"},
    "query_ontology": {"query": "검색어"},
    "propose_delete_relations": {"relation_ids": "관계_id_목록"},
    "query_notes": {"query": "검색어"},
    "propose_add_note": {"title": "제목", "content": "내용", "tags": "태그"},
    "propose_update_note": {"changes": "변경필드"},
    "propose_delete_note": {"note_ids": "노트_id_목록"},
    "create_file": {"filename": "파일명", "content": "내용"},
    "ask_clarifying_question": {"question": "질문", "options": "선택지"},
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

_관계수정항목_키_매핑 = {"relation_id": "관계_id", "relation_type": "관계유형", "description": "설명"}


def _키_변환(항목: dict, 매핑: dict) -> dict:
    return {매핑.get(k, k): v for k, v in 항목.items()}


def _도구_인자_한글화(name: str, tool_input: dict) -> dict:
    """Claude가 ASCII 키로 보낸 tool 인자를 기존 로직이 쓰는 한글 키로 되돌린다."""
    변환됨 = _키_변환(tool_input, _상위_키_매핑.get(name, {}))
    if name == "propose_add_business":
        변환됨["사업목록"] = [_키_변환(항목, _사업항목_키_매핑) for 항목 in 변환됨.get("사업목록", [])]
    elif name == "propose_add_relations":
        변환됨["관계목록"] = [_키_변환(항목, _관계항목_키_매핑) for 항목 in 변환됨.get("관계목록", [])]
    elif name == "propose_update_relations":
        변환됨["변경목록"] = [_키_변환(항목, _관계수정항목_키_매핑) for 항목 in 변환됨.get("변경목록", [])]
    return 변환됨


def _도구_실행(name: str, tool_input: dict):
    if name == "query_business_status":
        return 조회_사업현황(**tool_input)
    if name == "summarize_business_status":
        return 조회_사업현황_집계(**tool_input)
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
    if name == "propose_update_relations":
        return propose_update_relations(**tool_input)
    if name == "import_uploaded_file_as_data":
        return import_uploaded_file_as_data(**tool_input)
    if name == "query_ontology":
        return query_ontology(**tool_input)
    if name == "propose_delete_relations":
        return propose_delete_relations(**tool_input)
    if name == "query_notes":
        return query_notes(**tool_input)
    if name == "propose_add_note":
        return propose_add_note(**tool_input)
    if name == "propose_update_note":
        return propose_update_note(**tool_input)
    if name == "propose_delete_note":
        return propose_delete_note(**tool_input)
    if name == "create_file":
        return create_file(**tool_input)
    if name == "ask_clarifying_question":
        return ask_clarifying_question(**tool_input)
    raise ValueError(f"알 수 없는 도구: {name}")


def _도구_실행_안전(name: str, tool_input: dict) -> tuple[dict, bool]:
    """_도구_실행()을 try/except로 감싼다 — 전에는 잘못된 id, DB 제약 위반 같은
    예외가 그대로 새서 대화 전체가 원시 에러와 함께 끊겼다(스트리밍 경로는
    backend/app/chat.py의 바깥쪽 try/except가 SSE error 이벤트로 잘라버림).
    이제는 실패도 tool_result(is_error=True)로 모델에 돌려줘서, 모델이 실패를
    자연어로 설명하거나 다른 방식으로 재시도할 수 있게 한다."""
    try:
        return _도구_실행(name, tool_input), False
    except Exception as e:
        return {"오류": f"{name} 실행 중 문제가 발생했습니다: {e}"}, True


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


def 대화_요약_생성(기존_요약: str | None, 새_메시지들: list[dict], api_key: str | None = None) -> str:
    """대화 중 화면 범위(최근 20개)보다 오래돼 API에 그대로 안 보내는 부분을 요약한다.

    매번 전체를 다시 요약하지 않고, 이미 요약된 부분 이후로 새로 오래된 취급을 받게 된
    메시지들만 기존 요약에 덧붙여 갱신한다(호출부가 이 델타만 넘겨줌) — 대화가 아무리
    길어져도 매 턴 비용이 늘지 않는다. 제목 생성처럼 가벼운 작업이라 저렴한 모델을 쓴다.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            key = None
    if not key:
        return 기존_요약 or ""

    대화_텍스트 = "\n".join(f"{m['role']}: {m['content']}" for m in 새_메시지들)
    프롬프트 = (
        "다음은 사용자와 AI 사이의 대화 중, 화면에 보이는 최근 범위보다 오래돼 앞으로는 요약으로만 "
        "참조될 부분입니다. 이후 대화에서 이 요약만 보고도 맥락을 이어갈 수 있도록, 핵심 사실(언급된 "
        "사업명·수치·날짜, 사용자가 내린 결정이나 선호, 반복해서 나온 주제)을 중심으로 간결한 한국어 "
        "요약을 작성하세요. 사소한 인사말이나 일반적인 대화 흐름은 굳이 담지 않아도 됩니다.\n\n"
        + (f"[기존 요약]\n{기존_요약}\n\n" if 기존_요약 else "")
        + f"[새로 반영할 대화]\n{대화_텍스트}\n\n"
        "설명 없이 갱신된 요약 본문만 출력하세요."
    )
    try:
        client = Anthropic(api_key=key)
        response = client.messages.create(
            model=제목생성_MODEL_NAME, max_tokens=1024, messages=[{"role": "user", "content": 프롬프트}],
        )
        return _텍스트_추출(response).strip() or (기존_요약 or "")
    except Exception:
        return 기존_요약 or ""


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


_고정_컨텍스트_최대_글자수 = 6000


def _시스템_프롬프트_구성() -> list[dict]:
    """사용자가 위키에서 '고정컨텍스트'로 표시한 노트를, Claude Code의 CLAUDE.md처럼
    모든 AI 채팅 요청에 항상 참고하도록 시스템 프롬프트 뒤에 덧붙인다.

    캐싱을 위해 문자열 하나가 아니라 블록 리스트로 돌려준다 — 절대 안 바뀌는
    SYSTEM_PROMPT 블록에만 cache_control을 걸어두면, 고정컨텍스트 노트가 매번
    달라져도(혹은 아예 없어도) 그 앞의 SYSTEM_PROMPT 캐시는 그대로 재사용된다."""
    블록들 = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]
    if not DB_PATH.exists():
        return 블록들
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        고정_노트들 = conn.execute(
            "SELECT 제목, 내용 FROM 노트 WHERE 고정컨텍스트 = 1 ORDER BY 수정일시 DESC"
        ).fetchall()
    finally:
        conn.close()
    if not 고정_노트들:
        return 블록들
    묶음 = "\n\n".join(f"## {행['제목']}\n{행['내용'] or ''}" for 행 in 고정_노트들)
    if len(묶음) > _고정_컨텍스트_최대_글자수:
        묶음 = 묶음[:_고정_컨텍스트_최대_글자수] + "\n...(이하 생략)"
    블록들.append({
        "type": "text",
        "text": "[사용자가 위키에서 '고정컨텍스트'로 표시해 항상 참고하라고 지정한 노트]\n" + 묶음,
    })
    return 블록들


def 질의하기(
    question: str,
    history: list[dict] | None = None,
    api_key: str | None = None,
    첨부_문서_바이트: bytes | None = None,
) -> dict:
    """자연어 질문 -> Claude가 SQLite를 조회하거나 변경을 제안하며 답변 생성

    history: [{"role": "user"/"assistant", "content": "..."}] 형태의 이전 대화 이력.
    도구 호출 내역은 이번 턴 안에서만 쓰고 반환값에는 포함하지 않는다.
    첨부_문서_바이트: PDF 원본 바이트(있으면 Claude가 텍스트+시각적 레이아웃을
    직접 읽는다 — 스캔 이미지 PDF도 대응됨).

    반환값: {"text": 답변 문자열, "pending_action": {"유형": 도구명, "인자": {...}} 또는 None,
    "질문_대기": {"질문": ..., "선택지": [...]} 또는 None}
    pending_action은 실제로 반영된 것이 아니라 사용자 확인이 필요한 제안이다. 질문_대기가 있으면
    ask_clarifying_question이 호출된 것 — 이번 턴은 끝났고 사용자의 선택을 기다려야 한다.
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
            "질문_대기": None,
        }

    client = Anthropic(api_key=key)
    messages = list(history or []) + [
        {"role": "user", "content": _사용자_메시지_구성(question, 첨부_문서_바이트)}
    ]
    system_prompt = _시스템_프롬프트_구성()

    대기중_제안 = None
    for _ in range(_도구_호출_반복_상한):
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=_블로킹_최대_출력_토큰,
            system=system_prompt,
            messages=messages,
            tools=TOOLS,
            thinking={"type": "adaptive"},
        )

        if response.stop_reason != "tool_use":
            텍스트 = _텍스트_추출(response)
            if response.stop_reason == "max_tokens":
                텍스트 = _잘림_안내(텍스트)
            return {"text": 텍스트, "pending_action": 대기중_제안, "질문_대기": None}

        messages.append({"role": "assistant", "content": response.content})

        결과_블록들 = []
        질문_대기 = None
        for block in response.content:
            if block.type != "tool_use":
                continue
            도구_인자 = _도구_인자_한글화(block.name, block.input or {})
            결과, 실패함 = _도구_실행_안전(block.name, 도구_인자)
            if block.name in 제안_도구명들 and not 실패함:
                대기중_제안 = {"유형": block.name, "인자": 도구_인자}
            if block.name == "ask_clarifying_question" and not 실패함:
                질문_대기 = 도구_인자
            결과_블록들.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(결과, ensure_ascii=False),
                "is_error": 실패함,
            })

        if 질문_대기 is not None:
            return {"text": _텍스트_추출(response), "pending_action": 대기중_제안, "질문_대기": 질문_대기}

        messages.append({"role": "user", "content": 결과_블록들})

    return {
        "text": "질의 처리 중 도구 호출 횟수 상한을 초과했습니다.",
        "pending_action": 대기중_제안, "질문_대기": None,
    }


def 질의하기_스트림(
    question: str,
    history: list[dict] | None = None,
    api_key: str | None = None,
    첨부_문서_바이트: bytes | None = None,
):
    """질의하기()의 스트리밍 버전 — FastAPI SSE 엔드포인트 전용.

    제너레이터: 텍스트가 도착할 때마다 {"type": "token", "text": "..."}를 yield하고,
    턴이 끝나면 마지막으로 {"type": "final", "text": 전체답변, "pending_action": ...,
    "생성된_파일": ..., "질문_대기": ...}을 한 번 yield한다(Streamlit용 질의하기()와 반환 형태를
    맞췄다 — 다만 생성된_파일/질문_대기는 스트리밍 전용 필드). tool_use 루프 로직은 질의하기()와
    동일 — 브라우저가 받은 토큰이 아니라 stream.get_final_message()만 신뢰해서 도구 호출을 판단한다.
    첨부_문서_바이트: PDF 원본 바이트(질의하기()와 동일 — 스캔 이미지 PDF도 대응됨).
    질문_대기: ask_clarifying_question이 호출되면 {"질문": ..., "선택지": [...]}로 채워지고,
    그 즉시 턴이 끝난다(추가 도구 호출/텍스트 생성 없음) — create_file과 같은 특수 처리 패턴.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        yield {
            "type": "final",
            "text": "ANTHROPIC_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인하세요.",
            "pending_action": None,
            "생성된_파일": None,
            "질문_대기": None,
        }
        return

    client = Anthropic(api_key=key)
    messages = list(history or []) + [
        {"role": "user", "content": _사용자_메시지_구성(question, 첨부_문서_바이트)}
    ]
    system_prompt = _시스템_프롬프트_구성()

    대기중_제안 = None
    생성된_파일 = None
    for 회차 in range(_도구_호출_반복_상한):
        yield {
            "type": "status",
            "text": "요청을 확인하는 중..." if 회차 == 0 else "조회 결과를 반영해서 답변을 정리하는 중...",
        }
        with client.messages.stream(
            model=MODEL_NAME, max_tokens=_스트리밍_최대_출력_토큰, system=system_prompt, messages=messages,
            tools=TOOLS, thinking={"type": "adaptive"},
        ) as stream:
            # text_stream만 쓰면 web_search 같은 서버 도구가 실행되는 동안(같은 응답 안에서
            # 클라이언트 왕복 없이 일어남) 화면에 아무 신호도 안 뜬다. 원시 이벤트를 직접 봐서
            # server_tool_use 블록이 시작될 때도 상태 문구를 띄운다. thinking_delta는 일부러
            # 안 잡는다 — 화면엔 보여줄 UI가 없으니 조용히 건너뛰고 최종 답변 텍스트만 스트리밍.
            for event in stream:
                if event.type == "content_block_start" and event.content_block.type == "server_tool_use":
                    yield {
                        "type": "status",
                        "text": _도구_상태_문구.get(event.content_block.name, f"{event.content_block.name} 실행 중..."),
                    }
                elif event.type == "content_block_start" and event.content_block.type == "thinking":
                    yield {"type": "status", "text": "곰곰이 생각하는 중..."}
                elif event.type == "content_block_delta" and event.delta.type == "text_delta":
                    yield {"type": "token", "text": event.delta.text}
            response = stream.get_final_message()

        if response.stop_reason != "tool_use":
            텍스트 = _텍스트_추출(response)
            if response.stop_reason == "max_tokens":
                # 실제로 재현된 사고: "최대한 다채롭게" 같은 요청은 생각+본문+큰 HTML
                # 파일을 한 응답에 다 만들다 여기 걸려서 잘렸다. 프론트(ChatMain.tsx)는
                # 스트리밍 도중 받은 토큰이 아니라 이 final의 text로 메시지를 만들고,
                # text가 빈 문자열이면 메시지 자체를 안 그려서 "화면에 아무 것도 안
                # 뜨는" 것처럼 보였다 — 안내문을 붙여 절대 빈 문자열이 안 되게 한다.
                텍스트 = _잘림_안내(텍스트)
            yield {
                "type": "final", "text": 텍스트,
                "pending_action": 대기중_제안, "생성된_파일": 생성된_파일, "질문_대기": None,
            }
            return

        messages.append({"role": "assistant", "content": response.content})

        결과_블록들 = []
        질문_대기 = None
        for block in response.content:
            if block.type != "tool_use":
                continue
            yield {"type": "status", "text": _도구_상태_문구.get(block.name, f"{block.name} 실행 중...")}
            도구_인자 = _도구_인자_한글화(block.name, block.input or {})
            결과, 실패함 = _도구_실행_안전(block.name, 도구_인자)
            if block.name in 제안_도구명들 and not 실패함:
                대기중_제안 = {"유형": block.name, "인자": 도구_인자}
            if block.name == "create_file" and not 실패함:
                from backend.app.files import 파일_mime타입, 파일_생성_바이트

                파일명 = 도구_인자.get("파일명", "생성파일.txt")
                내용_바이트 = 파일_생성_바이트(파일명, 도구_인자.get("내용", ""))
                생성된_파일 = {"파일명": 파일명, "mime타입": 파일_mime타입(파일명), "내용": 내용_바이트}
            if block.name == "ask_clarifying_question" and not 실패함:
                질문_대기 = 도구_인자
            결과_블록들.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(결과, ensure_ascii=False),
                "is_error": 실패함,
            })

        if 질문_대기 is not None:
            yield {
                "type": "final", "text": _텍스트_추출(response),
                "pending_action": 대기중_제안, "생성된_파일": 생성된_파일, "질문_대기": 질문_대기,
            }
            return

        messages.append({"role": "user", "content": 결과_블록들})

    yield {
        "type": "final", "text": "질의 처리 중 도구 호출 횟수 상한을 초과했습니다.",
        "pending_action": 대기중_제안, "생성된_파일": 생성된_파일, "질문_대기": None,
    }
