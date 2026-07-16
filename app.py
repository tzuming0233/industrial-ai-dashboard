"""
산업AI팀 사업 통합관리 대시보드

산업AI팀 전용 실적관리 Streamlit 앱.
    - 대시보드(집계 차트) / 매출현황 표 / 간트차트
    - 데이터 관리: 사업현황을 엑셀처럼 직접 입력·수정
    - AI 채팅: 자연어 질의 (Claude API tool-use, 대화 이력 DB 저장)

(README.md 참고)
"""

import datetime as _dt
import importlib.util
import io
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db" / "실적관리.db"

금액_컬럼들 = ["계약금액", "기수입금액", "당해년도수입금액"]
편집_컬럼순서 = [
    "id", "구분", "업체명", "용역명", "사업구분",
    "시작일", "종료일", "계약금액", "기수입금액", "당해년도수입금액",
]


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


def 사업현황_저장(편집_df: pd.DataFrame, 원본_df: pd.DataFrame) -> None:
    """데이터 관리 탭에서 편집한 결과를 원본과 비교해 SQLite에 반영한다."""
    편집_df = 편집_df.dropna(subset=["업체명", "용역명"], how="all").copy()
    for 컬럼 in 금액_컬럼들:
        편집_df[컬럼] = pd.to_numeric(편집_df[컬럼], errors="coerce").fillna(0).astype(int)
    for 컬럼 in ["시작일", "종료일"]:
        편집_df[컬럼] = pd.to_datetime(편집_df[컬럼], errors="coerce").dt.strftime("%Y-%m-%d")

    원본_id_집합 = set(원본_df["id"].dropna().astype(int))
    편집_id_집합 = set(편집_df["id"].dropna().astype(int))

    conn = sqlite3.connect(DB_PATH)
    try:
        삭제할_id = 원본_id_집합 - 편집_id_집합
        for id_ in 삭제할_id:
            conn.execute("DELETE FROM 사업현황 WHERE id = ?", (int(id_),))

        나머지_컬럼 = [c for c in 편집_컬럼순서 if c != "id"]
        for _, row in 편집_df.iterrows():
            값들 = [_sqlite호환값(row[c]) for c in 나머지_컬럼]
            if pd.isna(row["id"]):
                conn.execute(
                    f"INSERT INTO 사업현황 ({', '.join(나머지_컬럼)}) VALUES ({', '.join(['?'] * len(나머지_컬럼))})",
                    값들,
                )
            else:
                set절 = ", ".join(f"{c} = ?" for c in 나머지_컬럼)
                conn.execute(
                    f"UPDATE 사업현황 SET {set절} WHERE id = ?",
                    값들 + [int(row["id"])],
                )
        conn.commit()
    finally:
        conn.close()
    사업현황_불러오기.clear()


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


def 채팅기록_초기화() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM 채팅기록")
        conn.commit()
    finally:
        conn.close()


st.set_page_config(page_title="산업AI팀 사업 통합관리(시범판)", layout="wide")

DB_준비()
채팅_DB_준비()
전체_df = 사업현황_불러오기()

st.title("산업AI팀 사업 통합관리")
st.caption("산업AI팀 전용 실적관리 대시보드")

with st.sidebar:
    st.header("필터")
    사업구분_옵션 = sorted(전체_df["사업구분"].dropna().unique())
    구분_옵션 = sorted(전체_df["구분"].dropna().unique())

    선택_사업구분 = st.multiselect("사업구분", 사업구분_옵션, default=사업구분_옵션)
    선택_구분 = st.multiselect("구분(신규/이월)", 구분_옵션, default=구분_옵션)

필터_df = 전체_df[
    전체_df["사업구분"].isin(선택_사업구분)
    & 전체_df["구분"].isin(선택_구분)
]

탭_대시보드, 탭_표, 탭_간트, 탭_데이터관리, 탭_AI = st.tabs(
    ["대시보드", "매출현황 표", "간트차트", "데이터 관리", "AI 채팅"]
)

with 탭_대시보드:
    col1, col2, col3 = st.columns(3)
    col1.metric("전체 건수", len(필터_df))
    col2.metric("사업구분 수", 필터_df["사업구분"].nunique())
    col3.metric("구분(신규/이월) 수", 필터_df["구분"].nunique())

    col_a, col_b = st.columns(2)
    with col_a:
        사업구분별_건수 = 필터_df["사업구분"].value_counts().reset_index()
        사업구분별_건수.columns = ["사업구분", "건수"]
        fig1 = px.bar(사업구분별_건수, x="사업구분", y="건수", title="사업구분별 건수")
        fig1.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig1, use_container_width=True)

    with col_b:
        구분별_건수 = 필터_df["구분"].value_counts().reset_index()
        구분별_건수.columns = ["구분", "건수"]
        fig2 = px.bar(구분별_건수, x="구분", y="건수", title="구분(신규/이월)별 건수", color="구분")
        st.plotly_chart(fig2, use_container_width=True)

with 탭_표:
    st.dataframe(필터_df, use_container_width=True, hide_index=True)
    버튼_col1, 버튼_col2 = st.columns(2)
    with 버튼_col1:
        st.download_button(
            "엑셀로 내보내기 (.xlsx)",
            data=엑셀로_변환(필터_df),
            file_name="사업현황_필터결과.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with 버튼_col2:
        st.download_button(
            "CSV로 내보내기",
            data=필터_df.to_csv(index=False).encode("utf-8-sig"),
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
            hover_data=["사업구분", "구분"],
            title="용역기간 간트차트",
        )
        fig3.update_yaxes(autorange="reversed")
        fig3.update_layout(height=max(400, len(간트_df) * 22))
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
            "시작일": st.column_config.DateColumn("시작일", format="YYYY-MM-DD"),
            "종료일": st.column_config.DateColumn("종료일", format="YYYY-MM-DD"),
            "계약금액": st.column_config.NumberColumn("계약금액", step=1),
            "기수입금액": st.column_config.NumberColumn("기수입금액", step=1),
            "당해년도수입금액": st.column_config.NumberColumn("당해년도수입금액", step=1),
        },
    )

    if st.button("변경사항 저장", type="primary"):
        사업현황_저장(편집_df, 전체_df)
        st.success("저장했습니다.")
        st.rerun()

with 탭_AI:
    import ai_agent

    st.subheader("AI 채팅")
    st.caption("예: '산업AI팀 계약 중 이번달 종료되는 건은?' / '상생형 스마트공장 사업은 몇 건이야?'")

    if st.button("대화 초기화"):
        채팅기록_초기화()
        st.rerun()

    이전_기록 = 채팅기록_불러오기()
    for 메시지 in 이전_기록:
        st.chat_message(메시지["role"]).write(메시지["content"])

    질문 = st.chat_input("질문을 입력하세요")
    if 질문:
        st.chat_message("user").write(질문)
        채팅기록_저장("user", 질문)

        with st.chat_message("assistant"):
            with st.spinner("Claude가 SQLite를 조회하며 답변을 생성 중..."):
                API용_기록 = [
                    {"role": m["role"], "content": m["content"]} for m in 이전_기록[-20:]
                ]
                답변 = ai_agent.질의하기(질문, history=API용_기록)
            st.write(답변)
        채팅기록_저장("assistant", 답변)
