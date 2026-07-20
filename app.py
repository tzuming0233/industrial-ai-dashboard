"""
산업AI팀 사업 통합관리 대시보드

산업AI팀 전용 실적관리 Streamlit 앱.
    - 대시보드(집계 차트) / 매출현황 표 / 간트차트
    - 데이터 관리: 사업현황을 엑셀처럼 직접 입력·수정
    - AI 채팅: 화면 우측에 항상 떠 있는 자연어 질의 패널 (Claude API tool-use, 대화 이력 DB 저장)

(README.md 참고)
"""

import datetime as _dt
import importlib.util
import io
import shutil
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db" / "실적관리.db"

금액_컬럼들 = ["계약금액", "기수입금액", "당해년도수입금액"]
편집_컬럼순서 = [
    "id", "구분", "업체명", "용역명", "사업구분", "담당자", "진행상태", "진행률",
    "시작일", "종료일", "계약금액", "기수입금액", "당해년도수입금액",
]
# 제안 파이프라인: RFP접수 -> 제안서작성 -> 제출 -> 평가 -> 수행 -> 완료, 보류는 별도 상태
진행상태_옵션 = ["RFP접수", "제안서작성", "제출", "평가", "수행", "완료", "보류"]
업로드_필수_컬럼 = ["구분", "업체명", "용역명", "사업구분", "시작일", "종료일", "계약금액", "기수입금액", "당해년도수입금액"]


def _이관_모듈_불러오기():
    spec = importlib.util.spec_from_file_location(
        "이관스크립트", BASE_DIR / "scripts" / "01_excel_SQLite_transport.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def DB_준비():
    """db/실적관리.db 가 없으면 data 폴더의 원본 데이터를 이관해 최초 1회 생성한다."""
    if DB_PATH.exists():
        return
    이관 = _이관_모듈_불러오기()
    df = 이관.원본_데이터_읽기()
    이관.SQLite로_적재(df)


def 채팅_DB_준비():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS 채팅기록 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,
                content TEXT,
                생성일시 TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def 사업현황_컬럼_보강():
    """기존 DB에 없는 컬럼을 추가하고, 옛 상태값을 새 파이프라인 값으로 옮긴다 (데이터 유지)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        기존_컬럼 = {row[1] for row in conn.execute("PRAGMA table_info(사업현황)")}
        if "진행상태" not in 기존_컬럼:
            conn.execute("ALTER TABLE 사업현황 ADD COLUMN 진행상태 TEXT DEFAULT 'RFP접수'")
        if "진행률" not in 기존_컬럼:
            conn.execute("ALTER TABLE 사업현황 ADD COLUMN 진행률 INTEGER DEFAULT 0")
        if "담당자" not in 기존_컬럼:
            conn.execute("ALTER TABLE 사업현황 ADD COLUMN 담당자 TEXT DEFAULT ''")
        # 예전 3단계(진행중/완료/보류) 데이터를 새 파이프라인 값으로 이관.
        # '진행중'은 이미 수주해 진행 중이던 건이라는 뜻이므로 '수행'으로 옮긴다 — 실제로 더 이른
        # 단계(제출/평가 등)에 있어야 할 건이 있다면 데이터 관리 탭에서 개별적으로 다시 확인 필요.
        conn.execute("UPDATE 사업현황 SET 진행상태 = '수행' WHERE 진행상태 = '진행중'")
        conn.commit()
    finally:
        conn.close()


def 이력_DB_준비():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS 이력 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                사업_id INTEGER,
                사업명 TEXT,
                유형 TEXT,
                내용 TEXT,
                작성자 TEXT,
                작성일시 TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


@st.cache_data
def 사업현황_불러오기() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql("SELECT * FROM 사업현황", conn)
    finally:
        conn.close()


def _sqlite호환값(값):
    if pd.isna(값):
        return None
    if isinstance(값, (int, float, str)):
        return 값
    return 값.item() if hasattr(값, "item") else str(값)


def _이력_저장(conn: sqlite3.Connection, 사업_id, 사업명: str, 유형: str, 내용: str, 작성자: str) -> None:
    conn.execute(
        "INSERT INTO 이력 (사업_id, 사업명, 유형, 내용, 작성자, 작성일시) VALUES (?, ?, ?, ?, ?, ?)",
        (
            int(사업_id) if 사업_id is not None else None,
            사업명,
            유형,
            내용,
            작성자 or "미상",
            _dt.datetime.now().isoformat(timespec="seconds"),
        ),
    )


def 사업현황_저장(편집_df: pd.DataFrame, 원본_df: pd.DataFrame, 작성자: str = "") -> None:
    """데이터 관리 탭에서 편집한 결과를 원본과 비교해 SQLite에 반영하고, 변경 이력을 함께 남긴다."""
    편집_df = 편집_df.dropna(subset=["업체명", "용역명"], how="all").copy()
    for 컬럼 in 금액_컬럼들:
        편집_df[컬럼] = pd.to_numeric(편집_df[컬럼], errors="coerce").fillna(0).astype(int)
    편집_df["진행률"] = pd.to_numeric(편집_df["진행률"], errors="coerce").fillna(0).clip(0, 100).astype(int)
    편집_df["진행상태"] = 편집_df["진행상태"].fillna("RFP접수")
    편집_df["담당자"] = 편집_df["담당자"].fillna("")
    for 컬럼 in ["시작일", "종료일"]:
        편집_df[컬럼] = pd.to_datetime(편집_df[컬럼], errors="coerce").dt.strftime("%Y-%m-%d")

    원본_id_별로 = {int(row["id"]): row.to_dict() for _, row in 원본_df.iterrows()}
    원본_id_집합 = set(원본_id_별로.keys())
    편집_id_집합 = set(편집_df["id"].dropna().astype(int))

    conn = sqlite3.connect(DB_PATH)
    try:
        삭제할_id = 원본_id_집합 - 편집_id_집합
        for id_ in 삭제할_id:
            원본행 = 원본_id_별로[id_]
            conn.execute("DELETE FROM 사업현황 WHERE id = ?", (int(id_),))
            _이력_저장(
                conn, id_, f"{원본행['업체명']} · {원본행['용역명']}",
                "삭제", "사업이 삭제되었습니다.", 작성자,
            )

        나머지_컬럼 = [c for c in 편집_컬럼순서 if c != "id"]
        for _, row in 편집_df.iterrows():
            값들 = [_sqlite호환값(row[c]) for c in 나머지_컬럼]
            사업명 = f"{row['업체명']} · {row['용역명']}"
            if pd.isna(row["id"]):
                cur = conn.execute(
                    f"INSERT INTO 사업현황 ({', '.join(나머지_컬럼)}) VALUES ({', '.join(['?'] * len(나머지_컬럼))})",
                    값들,
                )
                _이력_저장(conn, cur.lastrowid, 사업명, "추가", "신규 사업이 등록되었습니다.", 작성자)
            else:
                id_ = int(row["id"])
                원본행 = 원본_id_별로.get(id_, {})
                변경내용 = []
                for 컬럼 in 나머지_컬럼:
                    이전값 = _sqlite호환값(원본행.get(컬럼))
                    새값 = _sqlite호환값(row[컬럼])
                    if 이전값 != 새값:
                        변경내용.append(f"{컬럼}: {이전값} → {새값}")
                if 변경내용:
                    set절 = ", ".join(f"{c} = ?" for c in 나머지_컬럼)
                    conn.execute(f"UPDATE 사업현황 SET {set절} WHERE id = ?", 값들 + [id_])
                    _이력_저장(conn, id_, 사업명, "수정", "; ".join(변경내용), 작성자)
        conn.commit()
    finally:
        conn.close()
    사업현황_불러오기.clear()


def 이력_불러오기(사업_id: int) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT 유형, 내용, 작성자, 작성일시 FROM 이력 WHERE 사업_id = ? ORDER BY id DESC",
            (int(사업_id),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def 이력_저장(사업_id: int, 유형: str, 내용: str, 작성자: str, 사업명: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        _이력_저장(conn, 사업_id, 사업명, 유형, 내용, 작성자)
        conn.commit()
    finally:
        conn.close()


def 채팅기록_불러오기() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM 채팅기록 ORDER BY id").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def 채팅기록_저장(role: str, content: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO 채팅기록 (role, content, 생성일시) VALUES (?, ?, ?)",
            (role, content, _dt.datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()


def 엑셀로_변환(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, sheet_name="사업현황")
    return buffer.getvalue()


def 업로드_파일_읽기(업로드_파일) -> pd.DataFrame:
    """업로드된 엑셀/CSV를 사업현황_저장()에 그대로 넘길 수 있는 형태로 정리한다."""
    파일명 = 업로드_파일.name.lower()
    if 파일명.endswith(".csv"):
        df = pd.read_csv(업로드_파일)
    else:
        df = pd.read_excel(업로드_파일)

    누락_컬럼 = [c for c in 업로드_필수_컬럼 if c not in df.columns]
    if 누락_컬럼:
        raise ValueError(f"필수 컬럼이 없습니다: {', '.join(누락_컬럼)}")

    df = df.copy()
    if "담당자" not in df.columns:
        df["담당자"] = ""
    if "진행상태" not in df.columns:
        df["진행상태"] = "RFP접수"
    if "진행률" not in df.columns:
        df["진행률"] = 0

    # 엑셀에서 흔한 "30,000,000원" / "40%" 같은 표기를 숫자로 인식할 수 있게 정리
    for 컬럼 in 금액_컬럼들:
        df[컬럼] = df[컬럼].astype(str).str.replace(",", "", regex=False).str.replace("원", "", regex=False).str.strip()
    df["진행률"] = df["진행률"].astype(str).str.replace("%", "", regex=False).str.strip()

    df["id"] = pd.NA
    return df[편집_컬럼순서]


def 채팅기록_초기화() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM 채팅기록")
        conn.commit()
    finally:
        conn.close()


# 한국생산성본부(KPC) 등 공공기관 사이트 톤을 참고한 팔레트: 네이비 중심, 흰 배경, 절제된 radius
남색 = "#123A6B"
남색_진하게 = "#0D2A4F"
남색_연하게 = "#E8F0FE"
배경색 = "#F5F7FA"
테두리색 = "#E2E8F0"
본문색 = "#1A2233"
보조텍스트색 = "#5B6B82"

상태_배지_색상 = {
    "RFP접수": ("#F1F3F5", 보조텍스트색),
    "제안서작성": ("#FDF1DC", "#92670B"),
    "제출": ("#EAF1FB", "#2A5C99"),
    "평가": ("#FBEAE5", "#B54A34"),
    "수행": (남색_연하게, 남색),
    "완료": ("#E6F4EA", "#1E7A34"),
    "보류": ("#ECEAF5", "#5B4E8A"),
}


def _진행상태_배지(값: str) -> str:
    bg, fg = 상태_배지_색상.get(값, ("#F1F3F5", 보조텍스트색))
    return f"background-color: {bg}; color: {fg}; font-weight: 600; border-radius: 4px;"


# 카테고리(사업구분/구분) 고정 색상 팔레트 — 필터링해도 같은 값은 항상 같은 색을 유지한다.
카테고리_팔레트 = ["#2a78d6", "#008300", "#e87ba4", "#eda100", "#1baf7a", "#eb6834", "#4a3aa7", "#e34948"]

# 진행상태는 카테고리가 아니라 파이프라인 단계이므로, RFP접수~수행까지는 순서형(ordinal) 블루 램프를
# 쓰고 완료(success)/보류(muted)만 별도 의미 색상을 쓴다.
상태_차트_색상 = {
    "RFP접수": "#898781",
    "제안서작성": "#eda100",
    "제출": "#86b6ef",
    "평가": "#eb6834",
    "수행": "#2a78d6",
    "완료": "#0ca30c",
    "보류": "#4a3aa7",
}


def _고정_색상맵(고유값들) -> dict:
    return {값: 카테고리_팔레트[i % len(카테고리_팔레트)] for i, 값 in enumerate(sorted(고유값들))}


def _차트_공통레이아웃(fig, showlegend: bool = False) -> None:
    """모든 차트에 공통 크롬(폰트·배경·격자)을 적용해 대시보드 톤과 통일한다."""
    fig.update_layout(
        showlegend=showlegend,
        plot_bgcolor="#fff",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif", size=12, color=본문색),
        title_font=dict(size=14, color=남색),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    fig.update_xaxes(gridcolor="#eef0f3", zeroline=False, linecolor=테두리색)
    fig.update_yaxes(gridcolor="#eef0f3", zeroline=False, linecolor=테두리색)


def _스타일_적용() -> None:
    st.markdown(
        f"""
        <style>
        .stApp, [data-testid="stAppViewContainer"] {{
            background: {배경색};
            color: {본문색};
            font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', 'Noto Sans KR',
                -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
        }}
        h1[data-testid="stHeading"], .stApp h1 {{
            color: {남색};
            font-weight: 800;
            letter-spacing: -0.01em;
        }}
        [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3 {{
            color: {남색};
            font-weight: 700;
            border-left: 4px solid {남색};
            padding-left: 10px;
        }}

        /* 사이드바: 흰 배경 유지 + 네이비 포인트로 정돈된 톤 */
        [data-testid="stSidebar"] {{
            background: #FFFFFF;
            border-right: 1px solid {테두리색};
        }}
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
            color: {남색};
            border-left: none;
            padding-left: 0;
            border-bottom: 2px solid {남색};
            padding-bottom: 6px;
        }}
        [data-testid="stSidebar"] [data-baseweb="tag"] {{
            background: {남색} !important;
        }}

        /* 지표 -> 좌측 포인트 바가 있는 카드 스타일 + hover 시 살짝 떠오르는 느낌 */
        [data-testid="stMetric"] {{
            background: #fff;
            border: 1px solid {테두리색};
            border-left: 4px solid {남색};
            border-radius: 8px;
            padding: 14px 16px;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }}
        [data-testid="stMetric"]:hover {{
            transform: translateY(-3px);
            box-shadow: 0 10px 20px rgba(18, 58, 107, 0.12);
        }}
        [data-testid="stMetricLabel"] {{
            text-transform: uppercase;
            letter-spacing: 0.03em;
            font-size: 12px !important;
            color: {보조텍스트색} !important;
        }}
        [data-testid="stMetricValue"] {{
            font-weight: 700;
            color: {본문색};
        }}

        /* 탭 -> 밑줄 강조형 + 부드러운 색 전환 */
        [data-baseweb="tab-list"] {{
            background: transparent;
            border-bottom: 1px solid {테두리색};
            gap: 4px;
        }}
        [data-baseweb="tab-list"] button[data-baseweb="tab"] {{
            border-radius: 0;
            color: {보조텍스트색};
            font-weight: 600;
            transition: color 0.15s ease;
        }}
        [data-baseweb="tab-list"] button[data-baseweb="tab"]:hover {{
            color: {남색};
        }}
        [data-baseweb="tab-list"] button[aria-selected="true"] {{
            color: {남색};
        }}
        [data-baseweb="tab-highlight"] {{
            background: linear-gradient(90deg, {남색}, #2E77C2);
            height: 3px;
            transition: left 0.2s ease, width 0.2s ease;
        }}

        /* 버튼: 그라디언트 + hover 시 떠오르는 느낌 */
        button[kind="primary"] {{
            background: linear-gradient(135deg, {남색} 0%, #1E56A0 100%);
            border-radius: 8px;
            border: none;
            box-shadow: 0 2px 8px rgba(18, 58, 107, 0.25);
            transition: transform 0.12s ease, box-shadow 0.12s ease;
        }}
        button[kind="primary"]:hover {{
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(18, 58, 107, 0.35);
        }}
        button[kind="secondary"] {{
            border-radius: 8px;
            border-color: {테두리색};
            color: {남색};
            transition: border-color 0.12s ease, transform 0.12s ease;
        }}
        button[kind="secondary"]:hover {{
            border-color: {남색};
            transform: translateY(-1px);
        }}

        /* 표 / 차트 컨테이너: 카드화 + hover 강조 */
        [data-testid="stDataFrame"], [data-testid="stDataFrameResizable"],
        [data-testid="stPlotlyChart"] {{
            border: 1px solid {테두리색};
            border-radius: 8px;
            transition: box-shadow 0.15s ease;
        }}
        [data-testid="stDataFrame"]:hover, [data-testid="stDataFrameResizable"]:hover,
        [data-testid="stPlotlyChart"]:hover {{
            box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
        }}

        /* 탭 전환 시 콘텐츠가 살짝 떠오르며 나타나는 애니메이션 */
        [data-testid="stTabContent"] {{
            animation: dc-fade-in 0.25s ease;
        }}
        @keyframes dc-fade-in {{
            from {{ opacity: 0; transform: translateY(4px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="산업AI팀 사업 통합관리(시범판)", layout="wide")
_스타일_적용()

DB_준비()
사업현황_컬럼_보강()
채팅_DB_준비()
이력_DB_준비()
사업현황_불러오기.clear()  # 스키마 변경 직후에는 캐시된 옛 결과가 남아있지 않도록 강제로 비운다
전체_df = 사업현황_불러오기()

st.markdown(
    f"""
    <div style="background: linear-gradient(135deg, {남색} 0%, #1E56A0 55%, #2E77C2 100%);
                border-radius: 12px; padding: 26px 30px; margin-bottom: 22px;
                box-shadow: 0 8px 24px rgba(18, 58, 107, 0.25); position: relative; overflow: hidden;">
        <div style="position: absolute; top: -40px; right: -40px; width: 160px; height: 160px;
                    border-radius: 50%; background: rgba(255,255,255,0.08);"></div>
        <div style="position: absolute; bottom: -60px; right: 60px; width: 120px; height: 120px;
                    border-radius: 50%; background: rgba(255,255,255,0.06);"></div>
        <div style="font-size: 26px; font-weight: 800; color: #fff; letter-spacing: -0.01em; position: relative;">
            산업AI팀 사업 통합관리
        </div>
        <div style="font-size: 14px; color: rgba(255,255,255,0.85); margin-top: 4px; position: relative;">
            산업AI팀 전용 실적관리 대시보드
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("필터")
    사업구분_옵션 = sorted(전체_df["사업구분"].dropna().unique())
    구분_옵션 = sorted(전체_df["구분"].dropna().unique())
    담당자_옵션 = sorted(전체_df["담당자"].fillna("").unique())

    선택_사업구분 = st.multiselect("사업구분", 사업구분_옵션, default=사업구분_옵션)
    선택_구분 = st.multiselect("구분(신규/이월)", 구분_옵션, default=구분_옵션)
    선택_담당자 = st.multiselect(
        "담당자(PM)", 담당자_옵션, default=담당자_옵션,
        format_func=lambda v: v if v else "(미지정)",
    )

사업구분_색상맵 = _고정_색상맵(사업구분_옵션)
구분_색상맵 = _고정_색상맵(구분_옵션)

필터_df = 전체_df[
    전체_df["사업구분"].isin(선택_사업구분)
    & 전체_df["구분"].isin(선택_구분)
    & 전체_df["담당자"].fillna("").isin(선택_담당자)
]

메인_영역, 채팅_영역 = st.columns([7, 3], gap="medium")

with 메인_영역:
    탭_대시보드, 탭_표, 탭_간트, 탭_데이터관리, 탭_메모이력 = st.tabs(
        ["대시보드", "매출현황 표", "간트차트", "데이터 관리", "메모·이력"]
    )

    with 탭_대시보드:
        오늘 = _dt.date.today()
        임박_df = 전체_df.copy()
        임박_df["종료일_dt"] = pd.to_datetime(임박_df["종료일"], errors="coerce")
        임박_df["D-day"] = (임박_df["종료일_dt"] - pd.Timestamp(오늘)).dt.days
        임박_df = 임박_df[
            임박_df["종료일_dt"].notna()
            & (임박_df["D-day"] <= 30)
            & (임박_df["진행상태"] != "완료")
        ].sort_values("D-day")

        if 임박_df.empty:
            st.success("30일 이내 마감 임박 사업이 없습니다.")
        else:
            st.warning(f"마감 임박 {len(임박_df)}건 (완료 처리되지 않은 사업 중 종료일 30일 이내 또는 기한 초과)")
            st.dataframe(
                임박_df[["업체명", "용역명", "종료일", "D-day", "진행상태"]].style.map(
                    _진행상태_배지, subset=["진행상태"]
                ),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "종료일": st.column_config.DateColumn("종료일", format="YYYY-MM-DD"),
                    "D-day": st.column_config.NumberColumn("D-day", help="음수는 이미 기한이 지난 건수입니다."),
                },
            )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("전체 건수", len(필터_df))
        col2.metric("사업구분 수", 필터_df["사업구분"].nunique())
        col3.metric("구분(신규/이월) 수", 필터_df["구분"].nunique())
        col4.metric("평균 진행률", f"{필터_df['진행률'].mean():.0f}%" if len(필터_df) else "0%")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            사업구분별_건수 = 필터_df["사업구분"].value_counts().reset_index()
            사업구분별_건수.columns = ["사업구분", "건수"]
            사업구분별_건수 = 사업구분별_건수.sort_values("건수")
            fig1 = px.bar(
                사업구분별_건수, x="건수", y="사업구분", orientation="h",
                title="사업구분별 건수", text="건수",
            )
            fig1.update_traces(marker_color="#2a78d6", marker_line_width=0, textposition="outside")
            _차트_공통레이아웃(fig1)
            st.plotly_chart(fig1, use_container_width=True)

        with col_b:
            구분별_건수 = 필터_df["구분"].value_counts().reindex(구분_옵션).fillna(0).reset_index()
            구분별_건수.columns = ["구분", "건수"]
            fig2 = px.bar(
                구분별_건수, x="구분", y="건수", title="구분(신규/이월)별 건수",
                color="구분", color_discrete_map=구분_색상맵, text="건수",
            )
            fig2.update_traces(marker_line_width=0, textposition="outside")
            _차트_공통레이아웃(fig2, showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)

        with col_c:
            상태_순서 = 진행상태_옵션
            상태별_건수 = 필터_df["진행상태"].value_counts().reindex(상태_순서).fillna(0).reset_index()
            상태별_건수.columns = ["진행상태", "건수"]
            fig4 = px.bar(
                상태별_건수, x="진행상태", y="건수", title="진행상태별 건수",
                color="진행상태", color_discrete_map=상태_차트_색상, text="건수",
            )
            fig4.update_traces(marker_line_width=0, textposition="outside")
            fig4.update_xaxes(tickangle=-20)
            _차트_공통레이아웃(fig4, showlegend=False)
            st.plotly_chart(fig4, use_container_width=True)

        if 담당자_옵션 != [""]:
            담당자별_건수 = (
                필터_df.assign(담당자=필터_df["담당자"].replace("", "(미지정)"))["담당자"]
                .value_counts().reset_index()
            )
            담당자별_건수.columns = ["담당자", "건수"]
            담당자별_건수 = 담당자별_건수.sort_values("건수")
            fig5 = px.bar(
                담당자별_건수, x="건수", y="담당자", orientation="h",
                title="담당자(PM)별 투입 건수", text="건수",
            )
            fig5.update_traces(marker_color=남색, marker_line_width=0, textposition="outside")
            _차트_공통레이아웃(fig5)
            st.plotly_chart(fig5, use_container_width=True)

    with 탭_표:
        검색어 = st.text_input("업체명·용역명 검색", placeholder="예: 한국공대, 스마트공장")
        표시_df = 필터_df
        if 검색어.strip():
            검색_조건 = (
                표시_df["업체명"].str.contains(검색어, case=False, na=False)
                | 표시_df["용역명"].str.contains(검색어, case=False, na=False)
            )
            표시_df = 표시_df[검색_조건]

        표시_df = 표시_df.copy()
        표시_df["미수금"] = 표시_df["계약금액"] - 표시_df["기수입금액"]
        표시_df["수금률"] = (
            (표시_df["기수입금액"] / 표시_df["계약금액"].replace(0, pd.NA) * 100).fillna(0).round(1)
        )

        총계약금액 = 표시_df["계약금액"].sum()
        총기수입금액 = 표시_df["기수입금액"].sum()
        총미수금 = 표시_df["미수금"].sum()
        총당해년도수입금액 = 표시_df["당해년도수입금액"].sum()
        평균수금률 = (총기수입금액 / 총계약금액 * 100) if 총계약금액 else 0

        재무1, 재무2, 재무3, 재무4, 재무5 = st.columns(5)
        재무1.metric("총 계약금액", f"{총계약금액:,.0f}원")
        재무2.metric("총 기수입금액", f"{총기수입금액:,.0f}원")
        재무3.metric("총 미수금", f"{총미수금:,.0f}원")
        재무4.metric("당해년도 수입금액", f"{총당해년도수입금액:,.0f}원")
        재무5.metric("평균 수금률", f"{평균수금률:.0f}%")

        if not 표시_df.empty and 총계약금액 > 0:
            사업구분별_재무 = 표시_df.groupby("사업구분")[["기수입금액", "미수금"]].sum().reset_index()
            사업구분별_재무 = 사업구분별_재무.sort_values("기수입금액")
            재무_long = 사업구분별_재무.melt(
                id_vars="사업구분", value_vars=["기수입금액", "미수금"],
                var_name="구분", value_name="금액",
            )
            fig_수금 = px.bar(
                재무_long, y="사업구분", x="금액", color="구분", orientation="h",
                color_discrete_map={"기수입금액": "#0ca30c", "미수금": "#eda100"},
                title="사업구분별 수금 현황 (기수입 vs 미수금)",
            )
            _차트_공통레이아웃(fig_수금, showlegend=True)
            st.plotly_chart(fig_수금, use_container_width=True)

        st.caption(f"총 {len(표시_df)}건")
        st.dataframe(
            표시_df.style.map(_진행상태_배지, subset=["진행상태"]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "시작일": st.column_config.DateColumn("시작일", format="YYYY-MM-DD"),
                "종료일": st.column_config.DateColumn("종료일", format="YYYY-MM-DD"),
                "진행률": st.column_config.ProgressColumn("진행률", min_value=0, max_value=100, format="%d%%"),
                "계약금액": st.column_config.NumberColumn("계약금액", format="%,d"),
                "기수입금액": st.column_config.NumberColumn("기수입금액", format="%,d"),
                "당해년도수입금액": st.column_config.NumberColumn("당해년도수입금액", format="%,d"),
                "미수금": st.column_config.NumberColumn("미수금", format="%,d", help="계약금액 - 기수입금액"),
                "수금률": st.column_config.ProgressColumn(
                    "수금률", min_value=0, max_value=100, format="%.0f%%",
                    help="기수입금액 / 계약금액",
                ),
            },
        )
        버튼_col1, 버튼_col2 = st.columns(2)
        with 버튼_col1:
            st.download_button(
                "엑셀로 내보내기 (.xlsx)",
                data=엑셀로_변환(표시_df),
                file_name="사업현황_필터결과.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        with 버튼_col2:
            st.download_button(
                "CSV로 내보내기",
                data=표시_df.to_csv(index=False).encode("utf-8-sig"),
                file_name="사업현황_필터결과.csv",
                mime="text/csv",
            )

    with 탭_간트:
        간트_df = 필터_df.dropna(subset=["시작일", "종료일"]).copy()
        if 간트_df.empty:
            st.info("선택된 조건에 시작일/종료일이 모두 있는 건이 없습니다.")
        else:
            간트_df["표시명"] = 간트_df["업체명"] + " · " + 간트_df["용역명"]
            fig3 = px.timeline(
                간트_df,
                x_start="시작일",
                x_end="종료일",
                y="표시명",
                color="사업구분",
                color_discrete_map=사업구분_색상맵,
                hover_data=["사업구분", "구분", "담당자"],
                title="용역기간 간트차트",
            )
            fig3.update_yaxes(autorange="reversed")
            fig3.update_layout(height=max(400, len(간트_df) * 22))
            _차트_공통레이아웃(fig3, showlegend=True)
            st.plotly_chart(fig3, use_container_width=True)

    with 탭_데이터관리:
        st.subheader("사업현황 데이터 관리")
        st.caption("표를 엑셀처럼 직접 수정하세요. 행 끝의 빈 행에 새 데이터를 입력하거나, 행을 선택해 삭제할 수 있습니다.")

        st.download_button(
            "전체 데이터 엑셀로 내보내기 (.xlsx)",
            data=엑셀로_변환(전체_df),
            file_name=f"사업현황_전체_{_dt.date.today().isoformat()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        편집대상_df = 전체_df.copy()
        for 컬럼 in ["시작일", "종료일"]:
            편집대상_df[컬럼] = pd.to_datetime(편집대상_df[컬럼], errors="coerce")

        편집_df = st.data_editor(
            편집대상_df[편집_컬럼순서],
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="사업현황_editor",
            column_config={
                "id": st.column_config.NumberColumn("id", disabled=True),
                "담당자": st.column_config.TextColumn("담당자(PM)", help="이 사업을 담당하는 PM/실무자 이름"),
                "진행상태": st.column_config.SelectboxColumn(
                    "진행상태", options=진행상태_옵션,
                    help="RFP접수 → 제안서작성 → 제출 → 평가 → 수행 → 완료 (보류는 언제든 별도 지정 가능)",
                ),
                "진행률": st.column_config.NumberColumn("진행률(%)", min_value=0, max_value=100, step=5),
                "시작일": st.column_config.DateColumn("시작일", format="YYYY-MM-DD"),
                "종료일": st.column_config.DateColumn("종료일", format="YYYY-MM-DD"),
                "계약금액": st.column_config.NumberColumn("계약금액", step=1, format="%,d"),
                "기수입금액": st.column_config.NumberColumn("기수입금액", step=1, format="%,d"),
                "당해년도수입금액": st.column_config.NumberColumn("당해년도수입금액", step=1, format="%,d"),
            },
        )

        작성자_입력 = st.text_input("작성자 (이 변경을 기록할 이름)", key="데이터관리_작성자")
        if st.button("변경사항 저장", type="primary"):
            사업현황_저장(편집_df, 전체_df, 작성자_입력)
            st.success("저장했습니다.")
            st.rerun()

        st.divider()
        st.subheader("엑셀/CSV로 일괄 업로드")
        st.caption(
            f"필수 컬럼: {', '.join(업로드_필수_컬럼)} "
            "(담당자·진행상태·진행률은 없으면 빈값/RFP접수/0으로 채워집니다)"
        )
        업로드_파일 = st.file_uploader("파일 선택", type=["xlsx", "xls", "csv"], key="업로드_파일러")

        if 업로드_파일 is not None:
            try:
                업로드_df = 업로드_파일_읽기(업로드_파일)
            except ValueError as e:
                st.error(str(e))
            else:
                st.caption(f"{len(업로드_df)}건 인식됨 — 반영 전 미리보기")
                st.dataframe(업로드_df.drop(columns=["id"]), use_container_width=True, hide_index=True)

                업로드_모드 = st.radio(
                    "반영 방식",
                    ["기존 데이터에 추가", "전체 교체 (기존 데이터를 지우고 업로드 내용으로 교체)"],
                    key="업로드_모드",
                )
                전체_교체 = 업로드_모드.startswith("전체 교체")
                교체_확인 = True
                if 전체_교체:
                    교체_확인 = st.checkbox(
                        f"기존 {len(전체_df)}건을 전부 삭제하고 업로드한 {len(업로드_df)}건으로 교체하는 것에 동의합니다."
                    )

                업로드_작성자 = st.text_input("작성자 (이 업로드를 기록할 이름)", key="업로드_작성자")
                if st.button("업로드 반영", type="primary", disabled=전체_교체 and not 교체_확인):
                    if 전체_교체:
                        백업_경로 = DB_PATH.with_name(f"실적관리_{_dt.datetime.now():%Y%m%d%H%M%S}.bak")
                        shutil.copy(DB_PATH, 백업_경로)
                        반영대상_df = 업로드_df
                    else:
                        반영대상_df = pd.concat([전체_df, 업로드_df], ignore_index=True)
                    사업현황_저장(반영대상_df, 전체_df, 업로드_작성자)
                    st.success(f"{len(업로드_df)}건을 반영했습니다.")
                    st.rerun()

    with 탭_메모이력:
        st.subheader("사업별 메모 · 변경이력")

        if 전체_df.empty:
            st.info("등록된 사업이 없습니다.")
        else:
            선택옵션_df = 전체_df.sort_values("종료일")
            선택된_id = st.selectbox(
                "사업 선택",
                options=선택옵션_df["id"],
                format_func=lambda id_: (
                    lambda r: f"{r['업체명']} · {r['용역명']} (종료일 {r['종료일'] or '미정'})"
                )(선택옵션_df[선택옵션_df["id"] == id_].iloc[0]),
            )
            선택된_행 = 선택옵션_df[선택옵션_df["id"] == 선택된_id].iloc[0]
            선택된_사업명 = f"{선택된_행['업체명']} · {선택된_행['용역명']}"

            st.divider()
            기록들 = 이력_불러오기(선택된_id)
            if not 기록들:
                st.caption("아직 기록이 없습니다.")
            else:
                for 기록 in 기록들:
                    st.markdown(f"**{기록['작성일시']}** · {기록['작성자']} · `{기록['유형']}`")
                    st.write(기록["내용"])
                    st.divider()

            st.subheader("메모 추가")
            메모_작성자 = st.text_input("작성자", key="메모_작성자")
            메모_내용 = st.text_area("내용", key="메모_내용")
            if st.button("메모 추가"):
                if 메모_내용.strip():
                    이력_저장(선택된_id, "메모", 메모_내용.strip(), 메모_작성자, 선택된_사업명)
                    st.success("메모를 추가했습니다.")
                    st.rerun()
                else:
                    st.warning("내용을 입력하세요.")

with 채팅_영역:
    import ai_agent

    st.subheader("AI 채팅")
    if st.button("대화 초기화", key="채팅_초기화_버튼"):
        채팅기록_초기화()
        st.rerun()

    채팅_컨테이너 = st.container(height=560, border=True)
    이전_기록 = 채팅기록_불러오기()
    with 채팅_컨테이너:
        if not 이전_기록:
            st.caption("예: '산업AI팀 계약 중 이번달 종료되는 건은?' / '상생형 스마트공장 사업은 몇 건이야?'")
        for 메시지 in 이전_기록:
            st.chat_message(메시지["role"]).write(메시지["content"])

    질문 = st.chat_input("질문을 입력하세요")
    if 질문:
        with 채팅_컨테이너:
            st.chat_message("user").write(질문)
        채팅기록_저장("user", 질문)

        with 채팅_컨테이너:
            with st.chat_message("assistant"):
                with st.spinner("Claude가 SQLite를 조회하며 답변을 생성 중..."):
                    API용_기록 = [
                        {"role": m["role"], "content": m["content"]} for m in 이전_기록[-20:]
                    ]
                    답변 = ai_agent.질의하기(질문, history=API용_기록)
                st.write(답변)
        채팅기록_저장("assistant", 답변)
