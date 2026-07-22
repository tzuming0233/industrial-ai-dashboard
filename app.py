"""
산업AI팀 사업 통합관리 대시보드

산업AI팀 전용 실적관리 Streamlit 앱.
    - 대시보드(집계 차트) / 매출현황 표 / 간트차트
    - 데이터 관리: 사업현황을 엑셀처럼 직접 입력·수정
    - AI 채팅: 화면 우측에 항상 떠 있는 자연어 질의 패널 (Claude API tool-use, 대화 이력 DB 저장)

(README.md 참고)
"""

import base64
import datetime as _dt
import importlib.util
import io
import os
import re
import shutil
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v2 as st_components_v2
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db" / "실적관리.db"
ASSETS_DIR = BASE_DIR / "assets"
로고_경로 = ASSETS_DIR / "kpc_logo.png"

load_dotenv(BASE_DIR / ".env")


@st.cache_data
def _로고_data_uri() -> str | None:
    if not 로고_경로.exists():
        return None
    return "data:image/png;base64," + base64.b64encode(로고_경로.read_bytes()).decode("ascii")


def _최근_업로드_사진_경로() -> Path | None:
    """assets에 새 배경 사진을 올릴 때마다 코드를 다시 고치지 않도록, 로고류를 뺀 가장 최근 이미지를 고른다."""
    if not ASSETS_DIR.exists():
        return None
    제외_파일명 = {로고_경로.name}
    후보들 = [
        p for p in ASSETS_DIR.glob("*")
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg"} and p.name not in 제외_파일명
    ]
    if not 후보들:
        return None
    return max(후보들, key=lambda p: p.stat().st_mtime)


@st.cache_data
def _이미지_data_uri(경로_문자열: str, 최대_가로: int = 1600) -> str | None:
    """큰 원본 사진을 그대로 base64로 박아넣으면 페이지 CSS가 수 MB짜리 문자열이 되어 안 뜰 수 있다.
    배경으로 쓰기엔 과한 해상도이므로 적당히 축소·재압축해서 가볍게 만든다."""
    경로 = Path(경로_문자열)
    if not 경로.exists():
        return None
    try:
        from PIL import Image
        이미지 = Image.open(경로).convert("RGB")
        if 이미지.width > 최대_가로:
            비율 = 최대_가로 / 이미지.width
            이미지 = 이미지.resize((최대_가로, round(이미지.height * 비율)), Image.LANCZOS)
        버퍼 = io.BytesIO()
        이미지.save(버퍼, format="JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(버퍼.getvalue()).decode("ascii")
    except Exception:
        mime = "image/png" if 경로.suffix.lower() == ".png" else "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(경로.read_bytes()).decode("ascii")


def _로그인_필요() -> None:
    """세션이 인증되지 않았으면 배경 사진이 있는 로그인 화면만 그리고 나머지 앱 실행을 막는다."""
    if st.session_state.get("인증됨"):
        return

    배경_경로 = _최근_업로드_사진_경로()
    배경 = _이미지_data_uri(str(배경_경로)) if 배경_경로 else None
    로고 = _로고_data_uri()
    배경_이미지 = f"url('{배경}')" if 배경 else "none"

    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"] {{ background: #0a1428; }}
        [data-testid="stAppViewContainer"]::before {{
            content: ""; position: fixed; inset: -24px;
            background-image:
                linear-gradient(rgba(10, 20, 40, 0.42), rgba(10, 20, 40, 0.42)),
                {배경_이미지};
            background-size: cover;
            background-position: center;
            filter: blur(3px);
            transform: scale(1.02);
            z-index: 0;
        }}
        /* 배경 사진이 고정(fixed)이라 실제 콘텐츠보다 위에 그려질 수 있다 — 콘텐츠를 명시적으로 그 위로 띄운다 */
        [data-testid="stMain"] {{ position: relative; z-index: 1; }}
        [data-testid="stHeader"] {{ background: transparent; }}
        /* 로그인 카드는 사진이 밝든 어둡든 항상 또렷하게 보이도록 불투명한 흰 카드로 띄운다 */
        .st-key-login_card {{
            background: rgba(255, 255, 255, 0.95) !important;
            backdrop-filter: blur(6px);
            border-radius: 16px !important;
            box-shadow: 0 16px 48px rgba(0, 0, 0, 0.4) !important;
            border: none !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    _, 가운데, _ = st.columns([1, 1.1, 1])
    with 가운데:
        st.markdown("<div style='height:16vh'></div>", unsafe_allow_html=True)
        with st.container(border=True, key="login_card"):
            if 로고:
                st.markdown(
                    f"<div style='text-align:center; margin-bottom:8px;'>"
                    f"<img src='{로고}' style='height:48px;'/></div>",
                    unsafe_allow_html=True,
                )
            st.markdown(
                "<h3 style='text-align:center; margin-top:0; color:#1D2129;'>산업AI팀 사업 통합관리</h3>",
                unsafe_allow_html=True,
            )
            비밀번호_입력 = st.text_input("비밀번호", type="password", key="로그인_비밀번호_입력")
            if st.button("로그인", type="primary", use_container_width=True):
                설정된_비밀번호 = os.environ.get("APP_PASSWORD")
                if not 설정된_비밀번호:
                    try:
                        설정된_비밀번호 = st.secrets.get("APP_PASSWORD")
                    except Exception:
                        설정된_비밀번호 = None
                if not 설정된_비밀번호:
                    st.error("APP_PASSWORD가 설정되어 있지 않습니다. .env 파일을 확인하세요.")
                elif 비밀번호_입력 == 설정된_비밀번호:
                    st.session_state["인증됨"] = True
                    st.rerun()
                else:
                    st.error("비밀번호가 올바르지 않습니다.")
    st.stop()


금액_컬럼들 = ["계약금액", "기수입금액", "당해년도수입금액"]
편집_컬럼순서 = [
    "id", "구분", "업체명", "용역명", "사업구분", "담당자", "주관참여구분", "사업단계", "진행률",
    "시작일", "종료일", "계약금액", "기수입금액", "당해년도수입금액",
]
# 사업단계: 사업 발굴 -> 수주 계획 -> 제안 진행 -> 계약 체결 -> 사업 수행. '미분류'는 옛 진행상태에서
# 자동으로 매핑할 수 없어 남겨둔 임시값 — 담당자가 직접 재분류해야 한다.
사업단계_옵션 = ["미분류", "사업 발굴", "수주 계획", "제안 진행", "계약 체결", "사업 수행"]
주관참여구분_옵션 = ["", "주관", "참여"]


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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS 대화 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                제목 TEXT,
                생성일시 TEXT,
                마지막_활동일시 TEXT
            )
            """
        )
        기존_컬럼 = {row[1] for row in conn.execute("PRAGMA table_info(채팅기록)")}
        if "대화_id" not in 기존_컬럼:
            conn.execute("ALTER TABLE 채팅기록 ADD COLUMN 대화_id INTEGER")
            남은_행수 = conn.execute("SELECT COUNT(*) FROM 채팅기록 WHERE 대화_id IS NULL").fetchone()[0]
            if 남은_행수:
                지금 = _dt.datetime.now().isoformat(timespec="seconds")
                cur = conn.execute(
                    "INSERT INTO 대화 (제목, 생성일시, 마지막_활동일시) VALUES (?, ?, ?)",
                    ("이전 대화", 지금, 지금),
                )
                conn.execute("UPDATE 채팅기록 SET 대화_id = ? WHERE 대화_id IS NULL", (cur.lastrowid,))
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
        # 진행상태(7단계)를 사업단계(5단계+미분류)로 전면 교체한다. 기존 진행상태 값은 이 5단계 중
        # 어디에도 정확히 대응하지 않으므로(예: '완료'가 사업 수행 완료인지 계약 체결 완료인지 알 수
        # 없음) 억지로 자동 매핑하지 않고 '미분류'로 두어 담당자가 건별로 직접 재분류하게 한다.
        # 진행상태 컬럼 자체는 지우지 않고 남겨둔다(안전한 되돌리기용, 화면에서는 더 이상 안 씀).
        if "사업단계" not in 기존_컬럼:
            conn.execute("ALTER TABLE 사업현황 ADD COLUMN 사업단계 TEXT DEFAULT '미분류'")
        if "주관참여구분" not in 기존_컬럼:
            conn.execute("ALTER TABLE 사업현황 ADD COLUMN 주관참여구분 TEXT DEFAULT ''")
        conn.commit()
    finally:
        conn.close()


def 연간목표_DB_준비():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS 연간목표 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                연도 INTEGER UNIQUE,
                목표매출 INTEGER,
                목표손익 INTEGER
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


@st.cache_data
def 연간목표_불러오기() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql("SELECT * FROM 연간목표 ORDER BY 연도 DESC", conn)
    finally:
        conn.close()


def 연간목표_저장(연도: int, 목표매출: int, 목표손익: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO 연간목표 (연도, 목표매출, 목표손익) VALUES (?, ?, ?) "
            "ON CONFLICT(연도) DO UPDATE SET 목표매출 = excluded.목표매출, 목표손익 = excluded.목표손익",
            (int(연도), int(목표매출), int(목표손익)),
        )
        conn.commit()
    finally:
        conn.close()
    연간목표_불러오기.clear()


def 투입인력_DB_준비():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS 투입인력 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                사업_id INTEGER,
                이름 TEXT,
                역할 TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


@st.cache_data
def 투입인력_불러오기(사업_id: int) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql("SELECT * FROM 투입인력 WHERE 사업_id = ? ORDER BY id", conn, params=(int(사업_id),))
    finally:
        conn.close()


def 투입인력_저장(사업_id: int, 이름: str, 역할: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO 투입인력 (사업_id, 이름, 역할) VALUES (?, ?, ?)", (int(사업_id), 이름, 역할)
        )
        conn.commit()
    finally:
        conn.close()
    투입인력_불러오기.clear()


def 투입인력_삭제(인력_id: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM 투입인력 WHERE id = ?", (int(인력_id),))
        conn.commit()
    finally:
        conn.close()
    투입인력_불러오기.clear()


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


def 온톨로지_DB_준비():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS 온톨로지_노드 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                유형 TEXT NOT NULL,
                이름 TEXT NOT NULL,
                사업_id INTEGER,
                생성일시 TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS 온톨로지_관계 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                출발_노드_id INTEGER NOT NULL,
                도착_노드_id INTEGER NOT NULL,
                관계유형 TEXT NOT NULL,
                설명 TEXT,
                작성자 TEXT,
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
    편집_df["사업단계"] = 편집_df["사업단계"].fillna("미분류")
    편집_df["담당자"] = 편집_df["담당자"].fillna("")
    편집_df["주관참여구분"] = 편집_df["주관참여구분"].fillna("")
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
    전체_이력_불러오기.clear()


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


@st.cache_data
def 전체_이력_불러오기() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql("SELECT 사업_id, 유형, 내용, 작성일시 FROM 이력", conn)
    finally:
        conn.close()


def 이력_저장(사업_id: int, 유형: str, 내용: str, 작성자: str, 사업명: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        _이력_저장(conn, 사업_id, 사업명, 유형, 내용, 작성자)
        conn.commit()
    finally:
        conn.close()
    전체_이력_불러오기.clear()


def 대화_목록_불러오기() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, 제목, 생성일시, 마지막_활동일시 FROM 대화 ORDER BY 마지막_활동일시 DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def 대화_생성() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        지금 = _dt.datetime.now().isoformat(timespec="seconds")
        cur = conn.execute(
            "INSERT INTO 대화 (제목, 생성일시, 마지막_활동일시) VALUES (?, ?, ?)",
            (None, 지금, 지금),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def 대화_제목_설정(대화_id: int, 제목: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("UPDATE 대화 SET 제목 = ? WHERE id = ?", (제목, 대화_id))
        conn.commit()
    finally:
        conn.close()


def 대화_삭제(대화_id: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM 채팅기록 WHERE 대화_id = ?", (대화_id,))
        conn.execute("DELETE FROM 대화 WHERE id = ?", (대화_id,))
        conn.commit()
    finally:
        conn.close()


def 채팅기록_불러오기(대화_id: int) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT role, content FROM 채팅기록 WHERE 대화_id = ? ORDER BY id", (대화_id,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def 채팅기록_저장(대화_id: int, role: str, content: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        지금 = _dt.datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO 채팅기록 (role, content, 생성일시, 대화_id) VALUES (?, ?, ?, ?)",
            (role, content, 지금, 대화_id),
        )
        conn.execute("UPDATE 대화 SET 마지막_활동일시 = ? WHERE id = ?", (지금, 대화_id))
        if role == "user":
            row = conn.execute("SELECT 제목 FROM 대화 WHERE id = ?", (대화_id,)).fetchone()
            if row and not row[0]:
                제목 = content.strip().splitlines()[0][:30]
                conn.execute("UPDATE 대화 SET 제목 = ? WHERE id = ?", (제목, 대화_id))
        conn.commit()
    finally:
        conn.close()


@st.cache_data
def 온톨로지_노드_불러오기() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql("SELECT * FROM 온톨로지_노드", conn)
    finally:
        conn.close()


@st.cache_data
def 온톨로지_관계_불러오기() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql("SELECT * FROM 온톨로지_관계", conn)
    finally:
        conn.close()


def _온톨로지_노드_획득(conn: sqlite3.Connection, 노드: dict, 전체_df: pd.DataFrame) -> int:
    """노드 설명(유형/이름/사업_id)에 해당하는 온톨로지 노드를 찾고, 없으면 새로 만든다."""
    유형 = (노드.get("유형") or "개념").strip()
    사업_id = 노드.get("사업_id")
    이름 = (노드.get("이름") or "").strip()

    if 사업_id:
        row = conn.execute("SELECT id FROM 온톨로지_노드 WHERE 사업_id = ?", (int(사업_id),)).fetchone()
        if row:
            return row[0]
        if not 이름:
            사업행 = 전체_df[전체_df["id"] == int(사업_id)]
            이름 = 사업행.iloc[0]["용역명"] if not 사업행.empty else f"사업#{사업_id}"
        cur = conn.execute(
            "INSERT INTO 온톨로지_노드 (유형, 이름, 사업_id, 생성일시) VALUES (?, ?, ?, ?)",
            ("사업", 이름, int(사업_id), _dt.datetime.now().isoformat(timespec="seconds")),
        )
        return cur.lastrowid

    row = conn.execute(
        "SELECT id FROM 온톨로지_노드 WHERE 유형 = ? AND 이름 = ? AND 사업_id IS NULL", (유형, 이름)
    ).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO 온톨로지_노드 (유형, 이름, 사업_id, 생성일시) VALUES (?, ?, ?, ?)",
        (유형, 이름, None, _dt.datetime.now().isoformat(timespec="seconds")),
    )
    return cur.lastrowid


def 온톨로지_관계_추가(관계목록: list[dict], 전체_df: pd.DataFrame, 작성자: str = "AI채팅") -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        for 관계 in 관계목록:
            노드1_id = _온톨로지_노드_획득(
                conn,
                {"유형": 관계.get("노드1_유형"), "이름": 관계.get("노드1_이름"), "사업_id": 관계.get("노드1_사업_id")},
                전체_df,
            )
            노드2_id = _온톨로지_노드_획득(
                conn,
                {"유형": 관계.get("노드2_유형"), "이름": 관계.get("노드2_이름"), "사업_id": 관계.get("노드2_사업_id")},
                전체_df,
            )
            conn.execute(
                "INSERT INTO 온톨로지_관계 (출발_노드_id, 도착_노드_id, 관계유형, 설명, 작성자, 생성일시) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    노드1_id, 노드2_id, 관계.get("관계유형", ""), 관계.get("설명", ""),
                    작성자, _dt.datetime.now().isoformat(timespec="seconds"),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    온톨로지_노드_불러오기.clear()
    온톨로지_관계_불러오기.clear()


def _온톨로지_고아노드_정리(conn: sqlite3.Connection) -> None:
    """어떤 관계에도 더 이상 연결되지 않은 노드를 정리한다."""
    conn.execute(
        """
        DELETE FROM 온톨로지_노드
        WHERE id NOT IN (SELECT 출발_노드_id FROM 온톨로지_관계)
          AND id NOT IN (SELECT 도착_노드_id FROM 온톨로지_관계)
        """
    )


def 온톨로지_관계_삭제(관계_id: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM 온톨로지_관계 WHERE id = ?", (int(관계_id),))
        _온톨로지_고아노드_정리(conn)
        conn.commit()
    finally:
        conn.close()
    온톨로지_노드_불러오기.clear()
    온톨로지_관계_불러오기.clear()


def 온톨로지_초기화() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM 온톨로지_관계")
        conn.execute("DELETE FROM 온톨로지_노드")
        conn.commit()
    finally:
        conn.close()
    온톨로지_노드_불러오기.clear()
    온톨로지_관계_불러오기.clear()


def 온톨로지_관계_직접추가(노드1_id: int, 노드2_id: int, 관계유형: str, 설명: str, 작성자: str) -> None:
    """그래프에서 이미 존재하는 두 노드를 클릭으로 골라 바로 관계를 잇는다(신규 노드 생성 없음)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO 온톨로지_관계 (출발_노드_id, 도착_노드_id, 관계유형, 설명, 작성자, 생성일시) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (int(노드1_id), int(노드2_id), 관계유형, 설명, 작성자, _dt.datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()
    온톨로지_노드_불러오기.clear()
    온톨로지_관계_불러오기.clear()


def 온톨로지_검색(검색어: str | None = None) -> list[dict]:
    """노드/관계유형/설명에서 검색어로 관계를 찾는다. 검색어가 없으면 전체를 반환한다."""
    노드_df = 온톨로지_노드_불러오기()
    관계_df = 온톨로지_관계_불러오기()
    if 노드_df.empty or 관계_df.empty:
        return []

    노드_이름표 = 노드_df[["id", "이름", "유형"]]
    표시용_df = (
        관계_df.merge(
            노드_이름표.rename(columns={"id": "출발_노드_id", "이름": "출발", "유형": "출발유형"}),
            on="출발_노드_id", how="left",
        ).merge(
            노드_이름표.rename(columns={"id": "도착_노드_id", "이름": "도착", "유형": "도착유형"}),
            on="도착_노드_id", how="left",
        )
    )

    if 검색어:
        조건 = (
            표시용_df["출발"].str.contains(검색어, case=False, na=False)
            | 표시용_df["도착"].str.contains(검색어, case=False, na=False)
            | 표시용_df["관계유형"].str.contains(검색어, case=False, na=False)
            | 표시용_df["설명"].fillna("").str.contains(검색어, case=False, na=False)
        )
        표시용_df = 표시용_df[조건]

    return 표시용_df[["id", "출발", "관계유형", "도착", "설명", "작성자", "생성일시"]].to_dict("records")


def 엑셀로_변환(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, sheet_name="사업현황")
    return buffer.getvalue()


def _업로드_원본_읽기(업로드_파일) -> pd.DataFrame:
    """형식(컬럼명·순서)을 가리지 않고 업로드된 엑셀/CSV를 그대로 읽는다.

    컬럼 매핑은 여기서 강제하지 않고 AI(ai_agent.업로드_매핑_추론)가 추론하도록 넘긴다.
    """
    파일명 = 업로드_파일.name.lower()
    if 파일명.endswith(".csv"):
        df = pd.read_csv(업로드_파일)
    else:
        df = pd.read_excel(업로드_파일)
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
    df.columns = [str(c).strip() for c in df.columns]
    return df.reset_index(drop=True)


def _pdf_텍스트_추출(업로드_파일, 최대글자수: int = 15000) -> str:
    from pypdf import PdfReader

    reader = PdfReader(업로드_파일)
    조각들 = [(페이지.extract_text() or "") for 페이지 in reader.pages]
    전체 = "\n".join(조각들).strip()
    if len(전체) > 최대글자수:
        전체 = 전체[:최대글자수] + "\n...(이하 생략)"
    return 전체


def _hwp_텍스트_추출(업로드_파일, 최대글자수: int = 15000) -> str:
    import io
    import tempfile
    from contextlib import closing

    from hwp5.hwp5txt import TextTransform
    from hwp5.xmlmodel import Hwp5File

    with tempfile.NamedTemporaryFile(suffix=".hwp", delete=False) as tmp:
        tmp.write(업로드_파일.getvalue())
        임시경로 = tmp.name
    try:
        출력 = io.BytesIO()
        transform = TextTransform().transform_hwp5_to_text
        with closing(Hwp5File(임시경로)) as hwp파일:
            transform(hwp파일, 출력)
        전체 = 출력.getvalue().decode("utf-8", errors="ignore").strip()
    finally:
        Path(임시경로).unlink(missing_ok=True)
    if len(전체) > 최대글자수:
        전체 = 전체[:최대글자수] + "\n...(이하 생략)"
    return 전체


def _LLM_매핑_적용(원본_df: pd.DataFrame, 매핑결과: dict) -> tuple[pd.DataFrame, list[str]]:
    """AI가 추론한 컬럼/값 매핑을 실제 데이터프레임에 적용한다.

    금액·날짜 등 실제 값 자체는 AI가 다시 받아쓰게 하지 않고(수치 오기 위험) 원본 셀 값을
    그대로 가져와 코드로만 정리한다 — AI는 "어느 컬럼이 무엇인지"만 판단한다.
    """
    경고: list[str] = []
    매핑 = (매핑결과 or {}).get("매핑") or {}
    사업단계_값매핑 = (매핑결과 or {}).get("사업단계_값매핑") or {}

    기본값 = {
        "구분": "", "업체명": "", "용역명": "", "사업구분": "", "담당자": "", "주관참여구분": "",
        "사업단계": "미분류", "진행률": 0, "시작일": None, "종료일": None,
        "계약금액": 0, "기수입금액": 0, "당해년도수입금액": 0,
    }

    결과 = pd.DataFrame(index=원본_df.index)
    for 필드 in [c for c in 편집_컬럼순서 if c != "id"]:
        원본컬럼 = 매핑.get(필드)
        if 원본컬럼 and 원본컬럼 in 원본_df.columns:
            결과[필드] = 원본_df[원본컬럼]
        else:
            결과[필드] = 기본값[필드]
            경고.append(f"'{필드}'에 해당하는 컬럼을 찾지 못해 기본값으로 채웠습니다.")

    for 컬럼 in 금액_컬럼들:
        정리값 = (
            결과[컬럼].astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("원", "", regex=False)
            .str.strip()
        )
        결과[컬럼] = pd.to_numeric(정리값, errors="coerce").fillna(0)

    진행률_정리 = 결과["진행률"].astype(str).str.replace("%", "", regex=False).str.strip()
    결과["진행률"] = pd.to_numeric(진행률_정리, errors="coerce").fillna(0)

    if 사업단계_값매핑:
        결과["사업단계"] = 결과["사업단계"].astype(str).str.strip().replace(사업단계_값매핑)
    미표준_단계 = sorted(set(결과["사업단계"].astype(str)) - set(사업단계_옵션))
    if 미표준_단계:
        경고.append(f"'사업단계' 값 중 인식하지 못한 표현({', '.join(미표준_단계)})은 미분류로 대체했습니다.")
        결과["사업단계"] = 결과["사업단계"].where(결과["사업단계"].isin(사업단계_옵션), "미분류")

    for 컬럼 in ["시작일", "종료일"]:
        결과[컬럼] = pd.to_datetime(결과[컬럼], errors="coerce").dt.strftime("%Y-%m-%d")

    결과["id"] = pd.NA
    return 결과[편집_컬럼순서], 경고


_제안_기본값 = {
    "구분": "", "업체명": "", "용역명": "", "사업구분": "", "담당자": "", "주관참여구분": "",
    "사업단계": "미분류", "진행률": 0, "시작일": None, "종료일": None,
    "계약금액": 0, "기수입금액": 0, "당해년도수입금액": 0,
}


def _제안_추가행들(사업목록: list[dict]) -> pd.DataFrame:
    행들 = [{필드: 항목.get(필드, 기본값) for 필드, 기본값 in _제안_기본값.items()} for 항목 in 사업목록]
    df = pd.DataFrame(행들, columns=list(_제안_기본값.keys()))
    df["id"] = pd.NA
    return df[편집_컬럼순서]


def _제안_미리보기_표시(제안: dict, 전체_df: pd.DataFrame) -> None:
    """AI가 제안한 변경사항(추가/수정/삭제/업로드)을 채팅에 미리보기로 보여준다."""
    유형 = 제안.get("유형")
    인자 = 제안.get("인자", {})

    if 유형 == "업로드":
        경고_목록 = 제안.get("경고") or []
        if 경고_목록:
            st.warning("\n".join(f"- {w}" for w in 경고_목록))
        st.caption(f"{len(제안['결과_df'])}건을 추가합니다.")
        st.dataframe(제안["결과_df"].drop(columns=["id"]), use_container_width=True, hide_index=True)
    elif 유형 == "propose_add_business":
        st.caption(f"{len(인자.get('사업목록', []))}건을 추가합니다.")
        st.dataframe(_제안_추가행들(인자.get("사업목록", [])).drop(columns=["id"]), use_container_width=True, hide_index=True)
    elif 유형 == "propose_update_business":
        대상id = 인자.get("id")
        변경필드 = 인자.get("변경필드", {})
        기존행 = 전체_df[전체_df["id"] == 대상id]
        if 기존행.empty:
            st.error(f"id={대상id} 건을 찾을 수 없습니다.")
        else:
            기존 = 기존행.iloc[0]
            st.caption(f"{기존['업체명']} · {기존['용역명']} (id={대상id})")
            for 필드, 새값 in 변경필드.items():
                이전값 = 기존[필드] if 필드 in 기존 else "-"
                st.write(f"**{필드}**: {이전값} → {새값}")
    elif 유형 == "propose_delete_business":
        ids = 인자.get("ids", [])
        삭제대상_df = 전체_df[전체_df["id"].isin(ids)]
        st.warning(f"{len(삭제대상_df)}건이 삭제됩니다.")
        st.dataframe(삭제대상_df.drop(columns=["id"]), use_container_width=True, hide_index=True)
    elif 유형 == "propose_add_relations":
        st.caption(f"{len(인자.get('관계목록', []))}개 관계를 온톨로지에 추가합니다.")
        for 관계 in 인자.get("관계목록", []):
            노드1_표시 = 관계.get("노드1_이름") or (
                f"사업#{관계.get('노드1_사업_id')}" if 관계.get("노드1_사업_id") else "?"
            )
            노드2_표시 = 관계.get("노드2_이름") or (
                f"사업#{관계.get('노드2_사업_id')}" if 관계.get("노드2_사업_id") else "?"
            )
            st.write(f"**{노드1_표시}** —[{관계.get('관계유형', '')}]→ **{노드2_표시}**")
            if 관계.get("설명"):
                st.caption(관계["설명"])
    elif 유형 == "propose_delete_relations":
        관계_id_목록 = 인자.get("관계_id_목록", [])
        노드_df = 온톨로지_노드_불러오기()
        관계_df = 온톨로지_관계_불러오기()
        대상_df = 관계_df[관계_df["id"].isin(관계_id_목록)]
        if 대상_df.empty:
            st.error("삭제할 관계를 찾을 수 없습니다.")
        else:
            노드_이름표 = 노드_df[["id", "이름"]]
            표시용_df = (
                대상_df.merge(
                    노드_이름표.rename(columns={"id": "출발_노드_id", "이름": "출발"}), on="출발_노드_id", how="left",
                ).merge(
                    노드_이름표.rename(columns={"id": "도착_노드_id", "이름": "도착"}), on="도착_노드_id", how="left",
                )
            )
            st.warning(f"{len(표시용_df)}개 관계가 삭제됩니다.")
            for _, 행 in 표시용_df.iterrows():
                st.write(f"**{행['출발']}** —[{행['관계유형']}]→ **{행['도착']}**")


def _제안_반영(제안: dict, 전체_df: pd.DataFrame, 작성자: str = "AI채팅") -> None:
    """확인된 제안(추가/수정/삭제/업로드)을 실제로 DB에 반영한다."""
    유형 = 제안.get("유형")
    인자 = 제안.get("인자", {})

    if 유형 == "업로드":
        반영대상_df = pd.concat([전체_df, 제안["결과_df"]], ignore_index=True)
        사업현황_저장(반영대상_df, 전체_df, 작성자)
    elif 유형 == "propose_add_business":
        추가_df = _제안_추가행들(인자.get("사업목록", []))
        반영대상_df = pd.concat([전체_df, 추가_df], ignore_index=True)
        사업현황_저장(반영대상_df, 전체_df, 작성자)
    elif 유형 == "propose_update_business":
        대상id = 인자.get("id")
        변경필드 = 인자.get("변경필드", {})
        편집_df = 전체_df.copy()
        마스크 = 편집_df["id"] == 대상id
        for 필드, 새값 in 변경필드.items():
            if 필드 in 편집_df.columns:
                편집_df.loc[마스크, 필드] = 새값
        사업현황_저장(편집_df, 전체_df, 작성자)
    elif 유형 == "propose_delete_business":
        ids = 인자.get("ids", [])
        편집_df = 전체_df[~전체_df["id"].isin(ids)]
        사업현황_저장(편집_df, 전체_df, 작성자)
    elif 유형 == "propose_add_relations":
        온톨로지_관계_추가(인자.get("관계목록", []), 전체_df, 작성자)
    elif 유형 == "propose_delete_relations":
        for 관계_id in 인자.get("관계_id_목록", []):
            온톨로지_관계_삭제(관계_id)


def _테마_토큰() -> dict:
    """KPC(한국생산성본부) 실제 사내 그룹웨어(ep.kpc.or.kr) 컴파일된 CSS에서 색상 빈도를 분석해
    추출한 라이트 전용 팔레트. 다크 모드는 쓰지 않기로 해서 별도 다크 팔레트는 두지 않는다."""
    return dict(
        남색="#1C90FB", 남색_진하게="#1478D6", 남색_연하게="#EFF7FF",
        배경색="#F5F5F5", 테두리색="#E6E6E6", 본문색="#1D2129", 보조텍스트색="#8C8C8C",
        카드_배경="#FFFFFF", 인셋_배경="#FFFFFF",
        전기블루="#1C90FB", 엠버코랄="#FC5356", 차트리즈="#20C997",
        코랄_그라디언트="linear-gradient(135deg, #1C90FB 0%, #1478D6 100%)",
        알파인_그라디언트="linear-gradient(180deg, #46A3F0 0%, #1478D6 100%)",
        버튼_그림자="rgba(28, 144, 251, 0.25)",
        버튼_그림자_hover="rgba(28, 144, 251, 0.35)",
        히어로_그림자="rgba(20, 120, 214, 0.25)",
        카드_그림자="0 1px 4px rgba(0, 0, 0, 0.06)",
        차트_격자색="#E6E6E6",
        카테고리_팔레트=["#1C90FB", "#5F65FF", "#20C997", "#F0C325", "#F8A457", "#FC5356", "#39B0D2", "#8C8C8C"],
        상태_배지_색상={
            "미분류": ("#F5F5F5", "#8C8C8C"),
            "사업 발굴": ("#F0F0F0", "#5B6B82"),
            "수주 계획": ("#FFF1D6", "#B7791F"),
            "제안 진행": ("#EFF7FF", "#1C90FB"),
            "계약 체결": ("#E6F9F0", "#20C997"),
            "사업 수행": ("#F1EEFF", "#5F65FF"),
        },
        상태_차트_색상={
            "미분류": "#C4C4C4", "사업 발굴": "#8C8C8C", "수주 계획": "#F0C325",
            "제안 진행": "#1C90FB", "계약 체결": "#20C997", "사업 수행": "#5F65FF",
        },
    )


def _진행상태_배지(값: str) -> str:
    bg, fg = 상태_배지_색상.get(값, ("#1a1c26", 보조텍스트색))
    return f"background-color: {bg}; color: {fg}; font-weight: 600; border-radius: 4px;"


def _줄무늬_행(행: pd.Series) -> list[str]:
    """리스트형 표에 한 줄씩 번갈아 배경색을 넣어(zebra stripe) 정보 밀도가 높아도 읽기 쉽게 한다."""
    색 = 배경색 if int(행.name) % 2 == 1 else "transparent"
    return [f"background-color: {색};"] * len(행)


def _고정_색상맵(고유값들) -> dict:
    return {값: 카테고리_팔레트[i % len(카테고리_팔레트)] for i, 값 in enumerate(sorted(고유값들))}


def _단조_색상맵(고유값들) -> dict:
    """카테고리를 여러 색으로 흩뿌리지 않고, 남색 한 가지 색조의 명암 단계로만 구분한다."""
    고유값들 = sorted(고유값들)
    연한 = (0xEF, 0xF7, 0xFF)
    진한 = (0x14, 0x78, 0xD6)
    n = max(len(고유값들) - 1, 1)
    결과 = {}
    for i, 값 in enumerate(고유값들):
        t = i / n
        rgb = tuple(round(연한[c] + (진한[c] - 연한[c]) * t) for c in range(3))
        결과[값] = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    return 결과


def _온톨로지_노드_표시라벨(이름: str, 유형: str, 최대길이: int = 16) -> str:
    # 사업 노드는 용역명 기준으로 표시한다(업체명은 여러 사업에서 겹칠 수 있어 구분이 안 됨).
    # 예전에 "업체명 · 용역명" 형태로 저장된 노드는 뒷부분(용역명)만 취한다.
    표시 = 이름.split(" · ", 1)[-1] if 유형 == "사업" and " · " in 이름 else 이름
    return 표시 if len(표시) <= 최대길이 else 표시[:최대길이] + "…"


def _온톨로지_그래프_데이터(
    노드_df: pd.DataFrame, 관계_df: pd.DataFrame, 팔레트: dict, 강조_id_집합: set, 높이: int = 460,
) -> dict:
    """vis-network(물리 시뮬레이션·드래그 지원)에 그대로 먹일 수 있는 노드/엣지/옵션 JSON을 만든다."""
    노드_목록 = []
    for _, 행 in 노드_df.iterrows():
        nid = int(행["id"])
        유형 = 행["유형"]
        강조 = nid in 강조_id_집합
        노드_목록.append({
            "id": nid,
            "label": _온톨로지_노드_표시라벨(str(행["이름"]), 유형),
            "title": f"{유형}: {행['이름']}",
            "color": 팔레트.get(유형, 보조텍스트색),
            "shape": "box" if 유형 == "사업" else "dot",
            "size": 34 if 강조 else 22,
            "borderWidth": 3 if 강조 else 1,
        })

    엣지_목록 = []
    for _, 행 in 관계_df.iterrows():
        엣지_목록.append({
            "id": int(행["id"]),
            "from": int(행["출발_노드_id"]),
            "to": int(행["도착_노드_id"]),
            "label": str(행["관계유형"]),
            "title": str(행.get("설명") or ""),
            "color": {"color": 엠버코랄, "highlight": 엠버코랄},
            "width": 2,
            "arrows": "to",
        })

    옵션 = {
        "height": f"{높이}px",
        "interaction": {"hover": True, "navigationButtons": True, "keyboard": True},
        "nodes": {"font": {"size": 20, "face": "Malgun Gothic, Pretendard, sans-serif", "color": 본문색}},
        "edges": {
            "font": {"size": 13, "align": "top", "face": "Malgun Gothic, Pretendard, sans-serif",
                     "background": 카드_배경, "strokeWidth": 0, "color": 본문색},
            "smooth": {"type": "continuous"},
        },
        "physics": {
            "solver": "repulsion",
            "repulsion": {"nodeDistance": 200, "centralGravity": 0.15,
                           "springLength": 200, "springStrength": 0.03, "damping": 0.9},
            "stabilization": {"enabled": True, "iterations": 300, "fit": True},
        },
    }

    return {"nodes": 노드_목록, "edges": 엣지_목록, "options": 옵션, "bgcolor": 카드_배경}


def _온톨로지_그래프_컴포넌트():
    return st_components_v2.component(
        "ontology_graph",
        css="""
        .ont-graph-container { border-radius: 8px; overflow: hidden; }
        """,
        js="""
        export default function(component) {
            const { data, setTriggerValue, parentElement } = component;

            function init() {
                parentElement.innerHTML = '';
                const container = document.createElement('div');
                container.className = 'ont-graph-container';
                container.style.height = (data.options.height || '620px');
                container.style.background = data.bgcolor || '#ffffff';
                parentElement.appendChild(container);

                const nodes = new vis.DataSet(data.nodes);
                const edges = new vis.DataSet(data.edges);
                const network = new vis.Network(container, { nodes, edges }, data.options);

                network.on('click', (params) => {
                    if (params.nodes && params.nodes.length > 0) {
                        setTriggerValue('node_click', params.nodes[0]);
                    } else if (params.edges && params.edges.length > 0) {
                        setTriggerValue('edge_click', params.edges[0]);
                    }
                });
            }

            if (window.vis && window.vis.Network) {
                init();
            } else {
                const script = document.createElement('script');
                script.src = 'https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js';
                script.onload = init;
                document.head.appendChild(script);
            }
        }
        """,
    )


def _차트_공통레이아웃(fig, showlegend: bool = False, height: int = 300) -> None:
    """모든 차트에 공통 크롬(폰트·배경·격자)을 적용해 대시보드 톤과 통일한다."""
    fig.update_layout(
        showlegend=showlegend,
        legend=dict(font=dict(color=본문색)),
        plot_bgcolor=인셋_배경,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Malgun Gothic, Apple SD Gothic Neo, sans-serif", size=11, color=보조텍스트색),
        title_font=dict(size=13, color=본문색),
        margin=dict(l=10, r=10, t=36, b=10),
        height=height,
    )
    fig.update_xaxes(gridcolor=차트_격자색, zeroline=False, linecolor=테두리색)
    fig.update_yaxes(gridcolor=차트_격자색, zeroline=False, linecolor=테두리색)


def _스타일_적용() -> None:
    st.markdown(
        f"""
        <style>
        .stApp, [data-testid="stAppViewContainer"] {{
            background: {배경색};
            color: {본문색};
            font-family: 'Inter', 'Inter Tight', -apple-system, BlinkMacSystemFont, 'Segoe UI',
                'Malgun Gothic', 'Apple SD Gothic Neo', 'Noto Sans KR', Helvetica, Arial, sans-serif;
        }}
        [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3 {{
            color: {본문색};
            font-weight: 600;
            letter-spacing: 0.006em;
        }}
        [data-testid="stCaptionContainer"], .stCaption {{
            color: {보조텍스트색} !important;
        }}

        /* 사이드바를 없앤 만큼 위쪽 공백을 줄였지만, 스트림릿 자체 상단 툴바(높이 약 3.75rem)보다
           작게 잡으면 우리 로고바가 그 밑에 깔려 잘려 보인다 — 툴바 높이만큼은 확보한다. */
        [data-testid="stAppViewContainer"] .block-container {{
            padding-top: 4rem;
            max-width: 100%;
        }}

        /* 지표 -> 화이트 카드 + 옅은 그림자 (KPC 그룹웨어 콘텐츠 카드 톤) */
        [data-testid="stMetric"] {{
            background: {카드_배경};
            border: 1px solid {테두리색};
            border-radius: 8px;
            padding: 14px 16px;
            box-shadow: {카드_그림자};
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
            font-variant-numeric: tabular-nums;
        }}

        /* 탭 대신 쓰는 메뉴 팝오버 버튼 — 내용 크기만큼만 차지, 공간 낭비 최소화 */
        .st-key-현재_탭_선택 [role="radiogroup"] {{ gap: 2px; }}

        /* 검색창/입력창 -> 알약 모양 (KPC 그룹웨어 검색 인풋 톤) */
        [data-baseweb="input"] > div, [data-baseweb="base-input"] {{
            border-radius: 20px !important;
        }}
        [data-baseweb="input"] input {{
            border-radius: 20px !important;
        }}

        /* 버튼: 프라이머리 = 코랄 그라디언트 pill (화면당 1개 원칙), 나머지는 ghost pill */
        button[kind="primary"] {{
            background: {코랄_그라디언트};
            color: #ffffff;
            border-radius: 30px;
            border: none;
            box-shadow: 0 4px 20px {버튼_그림자};
            transition: transform 0.12s ease, box-shadow 0.12s ease;
        }}
        button[kind="primary"]:hover {{
            transform: translateY(-1px);
            box-shadow: 0 6px 24px {버튼_그림자_hover};
        }}
        button[kind="secondary"] {{
            background: transparent;
            border-radius: 30px;
            border-color: {테두리색};
            color: {보조텍스트색};
            transition: border-color 0.12s ease, color 0.12s ease;
        }}
        button[kind="secondary"]:hover {{
            border-color: {남색};
            color: {본문색};
        }}

        /* 표 / 차트 컨테이너: 옅은 테두리 + 카드 그림자 */
        [data-testid="stDataFrame"], [data-testid="stDataFrameResizable"],
        [data-testid="stPlotlyChart"] {{
            border: 1px solid {테두리색};
            border-radius: 8px;
            box-shadow: {카드_그림자};
        }}

        /* 지표/표/차트 카드 전반의 여백을 데스크톱에서도 조금 더 촘촘하게 */
        [data-testid="stMetric"] {{ padding: 12px 14px; }}
        [data-testid="stMetricValue"] {{ font-size: 1.5rem !important; }}

        /* 모바일 화면: 전체적으로 더 촘촘하게 — Claude 모바일 앱 정도의 여백/크기 밀도를 목표로 함 */
        @media (max-width: 640px) {{
            .dc-topbar {{ padding: 14px 16px !important; }}
            .dc-topbar img {{ height: 34px !important; }}
            .dc-topbar-divider {{ display: none; }}
            .dc-topbar-sub {{ display: none; }}

            [data-testid="stAppViewContainer"] .block-container {{
                padding-top: 3rem !important;
                padding-left: 0.6rem !important;
                padding-right: 0.6rem !important;
            }}
            [data-testid="stMarkdownContainer"] h2 {{ font-size: 1.05rem !important; }}
            [data-testid="stMarkdownContainer"] h3 {{ font-size: 0.95rem !important; }}

            /* 지표 카드: 패딩/글자 크기 축소 */
            [data-testid="stMetric"] {{ padding: 8px 10px; }}
            [data-testid="stMetricLabel"] {{ font-size: 10px !important; }}
            [data-testid="stMetricValue"] {{ font-size: 1.05rem !important; }}

            /* 버튼 패딩/글자 축소 */
            button[kind="primary"], button[kind="secondary"] {{
                font-size: 12.5px !important;
                padding: 0.3rem 0.8rem !important;
            }}

            /* 표/차트 카드 모서리·여백도 살짝 축소 */
            [data-testid="stDataFrame"], [data-testid="stDataFrameResizable"],
            [data-testid="stPlotlyChart"] {{
                border-radius: 6px;
            }}

            /* 온톨로지 그래프: 데스크톱용 고정 높이는 모바일엔 과함 (JS가 준 inline height를 !important로 덮어씀) */
            .ont-graph-container {{ height: 300px !important; }}

            /* AI 채팅창도 화면 높이에 맞게 축소 */
            .st-key-채팅_상자 {{ height: 380px !important; }}
            .st-key-채팅_상자 > div {{ height: 380px !important; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="산업AI팀 사업 통합관리(시범판)", layout="wide")

_로그인_필요()

_토큰 = _테마_토큰()
남색 = _토큰["남색"]
남색_진하게 = _토큰["남색_진하게"]
남색_연하게 = _토큰["남색_연하게"]
배경색 = _토큰["배경색"]
테두리색 = _토큰["테두리색"]
본문색 = _토큰["본문색"]
보조텍스트색 = _토큰["보조텍스트색"]
카드_배경 = _토큰["카드_배경"]
인셋_배경 = _토큰["인셋_배경"]
전기블루 = _토큰["전기블루"]
엠버코랄 = _토큰["엠버코랄"]
차트리즈 = _토큰["차트리즈"]
코랄_그라디언트 = _토큰["코랄_그라디언트"]
알파인_그라디언트 = _토큰["알파인_그라디언트"]
버튼_그림자 = _토큰["버튼_그림자"]
버튼_그림자_hover = _토큰["버튼_그림자_hover"]
히어로_그림자 = _토큰["히어로_그림자"]
카드_그림자 = _토큰["카드_그림자"]
차트_격자색 = _토큰["차트_격자색"]
카테고리_팔레트 = _토큰["카테고리_팔레트"]
상태_배지_색상 = _토큰["상태_배지_색상"]
상태_차트_색상 = _토큰["상태_차트_색상"]

_스타일_적용()

DB_준비()
사업현황_컬럼_보강()
채팅_DB_준비()
이력_DB_준비()
온톨로지_DB_준비()
연간목표_DB_준비()
투입인력_DB_준비()
사업현황_불러오기.clear()  # 스키마 변경 직후에는 캐시된 옛 결과가 남아있지 않도록 강제로 비운다
전체_df = 사업현황_불러오기()

로고_data_uri = _로고_data_uri()

if 로고_data_uri:
    st.markdown(
        f"""
        <div class="dc-topbar" style="background: {카드_배경}; border: 1px solid {테두리색}; border-radius: 8px;
                    box-shadow: {카드_그림자}; padding: 20px 28px; margin-bottom: 22px;
                    display: flex; align-items: center; justify-content: space-between;
                    flex-wrap: wrap; gap: 12px;">
            <div class="dc-topbar-brand" style="display: flex; align-items: center; gap: 20px; flex-wrap: wrap;">
                <img src="{로고_data_uri}" style="height: 48px;" alt="KPC 한국생산성본부" />
                <div class="dc-topbar-divider" style="width: 1px; height: 36px; background: {테두리색};"></div>
                <div style="font-size: 20px; font-weight: 700; color: {본문색};">
                    산업AI팀 사업 통합관리
                </div>
            </div>
            <div class="dc-topbar-sub" style="font-size: 13px; color: {보조텍스트색};">
                산업AI팀 전용 실적관리 대시보드 · {_dt.date.today().isoformat()}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

사업구분_옵션 = sorted(전체_df["사업구분"].dropna().unique())
구분_옵션 = sorted(전체_df["구분"].dropna().unique())
담당자_옵션 = sorted(전체_df["담당자"].fillna("").unique())
구분_색상맵 = _단조_색상맵(구분_옵션)

_탭_아이콘 = {
    "AI 채팅": "🤖", "대시보드": "📊", "매출현황 표": "📋", "마일스톤": "🗓️",
    "사업 온톨로지": "🕸️", "데이터 관리": "🛠️",
}
_저장된_탭 = st.session_state.get("현재_탭_선택", "AI 채팅")
with st.popover(f"{_탭_아이콘[_저장된_탭]} {_저장된_탭}  ▾", use_container_width=False):
    현재_탭_선택 = st.radio(
        "메뉴", list(_탭_아이콘.keys()), key="현재_탭_선택",
        format_func=lambda x: f"{_탭_아이콘[x]}  {x}", label_visibility="collapsed",
    )

# 모바일(640px 이하)에서는 대시보드류 화면과 AI 채팅을 동시에 쌓아 보여주지 않고
# 위 메뉴에서 고른 것 하나만 보여준다 — 로그인 후 기본값이 "AI 채팅"이라 이게 첫 화면이 된다.
# 데스크톱은 이 규칙이 적용되지 않아 항상 대시보드+채팅이 나란히 보인다.
_모바일_숨길_컬럼 = 1 if 현재_탭_선택 == "AI 채팅" else 2
st.markdown(
    f"""
    <style>
    @media (max-width: 640px) {{
        .st-key-본문_레이아웃 > div[data-testid="stHorizontalBlock"]
            > div[data-testid="stColumn"]:nth-of-type({_모바일_숨길_컬럼}) {{
            display: none !important;
        }}
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

본문_레이아웃 = st.container(key="본문_레이아웃")
메인_영역, 채팅_영역 = 본문_레이아웃.columns([7, 3], gap="medium")

with 메인_영역:
    if 현재_탭_선택 == "AI 채팅":
        st.caption("💬 오른쪽 AI 채팅에서 대화해보세요. (모바일에서는 위 메뉴로 다른 화면을 선택할 수 있어요)")
    elif 현재_탭_선택 == "대시보드":
        오늘 = _dt.date.today()
        임박_df = 전체_df.copy()
        임박_df["종료일_dt"] = pd.to_datetime(임박_df["종료일"], errors="coerce")
        임박_df["D-day"] = (임박_df["종료일_dt"] - pd.Timestamp(오늘)).dt.days
        임박_df = 임박_df[
            임박_df["종료일_dt"].notna()
            & (임박_df["D-day"] <= 30)
            & (pd.to_numeric(임박_df["진행률"], errors="coerce").fillna(0) < 100)
        ].sort_values("D-day")

        if 임박_df.empty:
            st.success("30일 이내 마감 임박 사업이 없습니다.")
        else:
            st.warning(f"마감 임박 {len(임박_df)}건 (진행률 100% 미달 사업 중 종료일 30일 이내 또는 기한 초과)")
            st.dataframe(
                임박_df[["업체명", "용역명", "종료일", "D-day", "사업단계"]]
                .reset_index(drop=True)
                .style.apply(_줄무늬_행, axis=1)
                .map(_진행상태_배지, subset=["사업단계"]),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "종료일": st.column_config.DateColumn("종료일", format="YYYY-MM-DD"),
                    "D-day": st.column_config.NumberColumn("D-day", help="음수는 이미 기한이 지난 건수입니다."),
                },
            )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("전체 건수", len(전체_df))
        col2.metric("사업구분 수", 전체_df["사업구분"].nunique())
        col3.metric("구분(신규/이월) 수", 전체_df["구분"].nunique())
        col4.metric("평균 진행률", f"{전체_df['진행률'].mean():.0f}%" if len(전체_df) else "0%")

        올해_목표_df = 연간목표_불러오기()
        올해_목표행 = 올해_목표_df[올해_목표_df["연도"] == 오늘.year]
        목표1, 목표2 = st.columns(2)
        if 올해_목표행.empty:
            목표1.metric("매출 달성률", "목표 미설정")
            목표2.metric("손익 달성률", "목표 미설정")
        else:
            목표매출 = 올해_목표행.iloc[0]["목표매출"]
            실적_매출 = 전체_df["당해년도수입금액"].sum()
            매출_달성률 = (실적_매출 / 목표매출 * 100) if 목표매출 else 0
            목표1.metric(
                f"{오늘.year}년 매출 달성률", f"{매출_달성률:.1f}%",
                help=f"실적 {실적_매출:,.0f}원 / 목표 {목표매출:,.0f}원 (진척도는 시간 안분 없이 단순 비율)",
            )
            # 손익(수입-비용)을 계산할 원가/비용 데이터가 사업현황에 없어 실제 값을 낼 수 없다.
            # 억지로 매출 등으로 대체하지 않고, 비용 데이터가 들어올 때까지 "데이터 없음"으로 둔다.
            목표2.metric(f"{오늘.year}년 손익 달성률", "데이터 없음", help="원가/비용 데이터가 아직 없어 계산할 수 없습니다.")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            사업구분별_건수 = 전체_df["사업구분"].value_counts().reset_index()
            사업구분별_건수.columns = ["사업구분", "건수"]
            사업구분별_건수 = 사업구분별_건수.sort_values("건수")
            fig1 = px.bar(
                사업구분별_건수, x="건수", y="사업구분", orientation="h",
                title="사업구분별 건수", text="건수",
            )
            fig1.update_traces(marker_color=전기블루, marker_line_width=0, textposition="outside")
            _차트_공통레이아웃(fig1)
            st.plotly_chart(fig1, use_container_width=True)

        with col_b:
            구분별_건수 = 전체_df["구분"].value_counts().reindex(구분_옵션).fillna(0).reset_index()
            구분별_건수.columns = ["구분", "건수"]
            fig2 = px.bar(
                구분별_건수, x="구분", y="건수", title="구분(신규/이월)별 건수",
                color="구분", color_discrete_map=구분_색상맵, text="건수",
            )
            fig2.update_traces(marker_line_width=0, textposition="outside")
            _차트_공통레이아웃(fig2, showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)

        with col_c:
            상태_순서 = 사업단계_옵션
            상태별_건수 = 전체_df["사업단계"].value_counts().reindex(상태_순서).fillna(0).reset_index()
            상태별_건수.columns = ["사업단계", "건수"]
            fig4 = px.bar(
                상태별_건수, x="사업단계", y="건수", title="사업단계별 건수",
                color="사업단계", color_discrete_map=상태_차트_색상, text="건수",
            )
            fig4.update_traces(marker_line_width=0, textposition="outside")
            fig4.update_xaxes(tickangle=-20)
            _차트_공통레이아웃(fig4, showlegend=False)
            st.plotly_chart(fig4, use_container_width=True)

        if 담당자_옵션 != [""]:
            담당자별_건수 = (
                전체_df.assign(담당자=전체_df["담당자"].replace("", "(미지정)"))["담당자"]
                .value_counts().reset_index()
            )
            담당자별_건수.columns = ["담당자", "건수"]
            담당자별_건수 = 담당자별_건수.sort_values("건수")
            fig5 = px.bar(
                담당자별_건수, x="건수", y="담당자", orientation="h",
                title="담당자(PM)별 투입 건수", text="건수",
            )
            fig5.update_traces(marker_color=전기블루, marker_line_width=0, textposition="outside")
            _차트_공통레이아웃(fig5)
            st.plotly_chart(fig5, use_container_width=True)

    elif 현재_탭_선택 == "매출현황 표":
        검색어 = st.text_input("업체명·용역명 검색", placeholder="예: 한국공대, 스마트공장")
        표시_df = 전체_df
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
                color_discrete_map={"기수입금액": 차트리즈, "미수금": 엠버코랄},
                title="사업구분별 수금 현황 (기수입 vs 미수금)",
            )
            _차트_공통레이아웃(fig_수금, showlegend=True)
            st.plotly_chart(fig_수금, use_container_width=True)

        st.caption(f"총 {len(표시_df)}건")
        st.dataframe(
            표시_df.reset_index(drop=True).style.apply(_줄무늬_행, axis=1).map(
                _진행상태_배지, subset=["사업단계"]
            ),
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

    elif 현재_탭_선택 == "마일스톤":
        st.subheader("마일스톤 타임라인")
        st.caption(
            "연한 막대는 전체 용역기간, 진한 막대는 진행률만큼 채워진 실제 진행 구간입니다. "
            "◆ 마커는 이력에 기록된 실제 단계 전환(사업단계 변경) 시점을 보여줍니다."
        )

        마일스톤_df = 전체_df.dropna(subset=["시작일", "종료일"]).copy()
        if 마일스톤_df.empty:
            st.info("선택된 조건에 시작일/종료일이 모두 있는 건이 없습니다.")
        else:
            오늘_dt = pd.Timestamp(_dt.date.today())
            마일스톤_df["진행률_숫자"] = pd.to_numeric(마일스톤_df["진행률"], errors="coerce").fillna(0)
            마일스톤_df["D-day_임시"] = (pd.to_datetime(마일스톤_df["종료일"]) - 오늘_dt).dt.days

            전체_건수 = len(마일스톤_df)
            지연_건수 = int(((마일스톤_df["D-day_임시"] < 0) & (마일스톤_df["진행률_숫자"] < 100)).sum())
            진행중_건수 = int(마일스톤_df["사업단계"].isin(["제안 진행", "계약 체결", "사업 수행"]).sum())
            평균_진행률 = 마일스톤_df["진행률_숫자"].mean()

            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("전체 마일스톤", f"{전체_건수}건")
            kpi2.metric("마감 초과(미완료)", f"{지연_건수}건")
            kpi3.metric("진행중", f"{진행중_건수}건")
            kpi4.metric("평균 진행률", f"{평균_진행률:.0f}%")

            그룹기준 = st.radio("그룹 기준", ["사업구분", "담당자"], horizontal=True, key="마일스톤_그룹기준")
            마일스톤_df[그룹기준] = 마일스톤_df[그룹기준].fillna("미지정").replace("", "미지정")
            그룹_색상맵 = _단조_색상맵(마일스톤_df[그룹기준].unique())

            마일스톤_df["표시명"] = 마일스톤_df["업체명"] + " · " + 마일스톤_df["용역명"]
            마일스톤_df = 마일스톤_df.sort_values("종료일")

            시작_dt = pd.to_datetime(마일스톤_df["시작일"])
            종료_dt = pd.to_datetime(마일스톤_df["종료일"])
            기간 = (종료_dt - 시작_dt).clip(lower=pd.Timedelta(days=1))
            진행률_비율 = 마일스톤_df["진행률_숫자"].clip(0, 100) / 100
            마일스톤_df["진행_종료일"] = 시작_dt + 기간 * 진행률_비율

            전체기간_fig = px.timeline(
                마일스톤_df, x_start="시작일", x_end="종료일", y="표시명",
                color=그룹기준, color_discrete_map=그룹_색상맵,
                hover_data=["사업구분", "구분", "담당자", "사업단계", "진행률"],
            )
            for tr in 전체기간_fig.data:
                tr.opacity = 0.32

            진행_fig = px.timeline(
                마일스톤_df, x_start="시작일", x_end="진행_종료일", y="표시명",
                color=그룹기준, color_discrete_map=그룹_색상맵,
            )
            for tr in 진행_fig.data:
                tr.showlegend = False
                tr.width = 0.4

            fig = go.Figure(data=list(전체기간_fig.data) + list(진행_fig.data))
            fig.add_trace(go.Scatter(
                x=마일스톤_df["진행_종료일"], y=마일스톤_df["표시명"], mode="text",
                text=[f"{v:.0f}%" for v in 마일스톤_df["진행률_숫자"]],
                textposition="middle right", textfont=dict(size=11, color=본문색),
                showlegend=False, hoverinfo="skip",
            ))
            fig.update_yaxes(autorange="reversed", categoryorder="array", categoryarray=마일스톤_df["표시명"].tolist())
            fig.update_layout(
                barmode="overlay", height=max(300, len(마일스톤_df) * 26),
                title=dict(text=f"마일스톤 타임라인 · {전체_건수}건", font=dict(size=13, color=본문색)),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                margin=dict(l=10, r=10, t=48, b=10),
            )

            fig.add_vline(x=오늘_dt, line_dash="dash", line_color=엠버코랄, annotation_text="오늘", annotation_position="top")

            전체_이력_df = 전체_이력_불러오기()
            if not 전체_이력_df.empty:
                패턴 = re.compile(r"사업단계:\s*(.+?)\s*→\s*([^;]+)")
                전환_행들 = []
                for _, 행 in 전체_이력_df[전체_이력_df["유형"] == "수정"].iterrows():
                    for _, 새단계 in 패턴.findall(행["내용"] or ""):
                        전환_행들.append({"사업_id": 행["사업_id"], "일시": 행["작성일시"], "새단계": 새단계.strip()})
                if 전환_행들:
                    전환_df = pd.DataFrame(전환_행들)
                    전환_df["일시"] = pd.to_datetime(전환_df["일시"], errors="coerce")
                    전환_df = 전환_df.merge(
                        마일스톤_df[["id", "표시명"]], left_on="사업_id", right_on="id", how="inner"
                    )
                    if not 전환_df.empty:
                        fig.add_trace(go.Scatter(
                            x=전환_df["일시"], y=전환_df["표시명"], mode="markers",
                            marker=dict(
                                symbol="diamond", size=11, line=dict(width=1, color=본문색),
                                color=[상태_차트_색상.get(s, 보조텍스트색) for s in 전환_df["새단계"]],
                            ),
                            customdata=전환_df["새단계"],
                            hovertemplate="%{y}<br>%{customdata} 전환: %{x|%Y-%m-%d}<extra></extra>",
                            showlegend=False,
                        ))

            _차트_공통레이아웃(fig, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)

            st.divider()
            st.caption("마일스톤 요약 (마감 임박·초과 순, 붉게 표시된 행은 완료되지 않은 채 기한을 넘긴 건입니다)")
            요약_df = 마일스톤_df.copy()
            요약_df["D-day"] = (pd.to_datetime(요약_df["종료일"]) - 오늘_dt).dt.days
            요약_df = 요약_df.sort_values("D-day")

            def _지연_강조_행(행: pd.Series) -> list[str]:
                if 행["D-day"] < 0 and 행["진행률"] < 100:
                    return [f"background-color: {엠버코랄}22;"] * len(행)
                return _줄무늬_행(행)

            st.dataframe(
                요약_df[["표시명", "담당자", "사업단계", "진행률", "종료일", "D-day"]]
                .reset_index(drop=True)
                .style.apply(_지연_강조_행, axis=1)
                .map(_진행상태_배지, subset=["사업단계"]),
                use_container_width=True, hide_index=True,
                column_config={
                    "진행률": st.column_config.ProgressColumn("진행률", min_value=0, max_value=100, format="%d%%"),
                    "D-day": st.column_config.NumberColumn("D-day", help="음수면 종료일을 이미 초과한 사업입니다"),
                },
            )

    elif 현재_탭_선택 == "데이터 관리":
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
                "담당자": st.column_config.TextColumn("담당자(PM)", help="이 사업을 담당하는 과제 책임자 1명"),
                "주관참여구분": st.column_config.SelectboxColumn(
                    "주관/참여", options=주관참여구분_옵션, help="이 사업에서 우리 팀이 주관인지 참여인지",
                ),
                "사업단계": st.column_config.SelectboxColumn(
                    "사업단계", options=사업단계_옵션,
                    help="사업 발굴 → 수주 계획 → 제안 진행 → 계약 체결 → 사업 수행. "
                         "'미분류'는 예전 진행상태에서 자동 이관되지 않은 건이니 직접 재분류해주세요.",
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

        st.caption("엑셀/CSV 업로드나 자연어로 데이터를 추가·수정하려면 오른쪽 AI 채팅에 파일을 첨부하거나 요청하세요.")

        st.divider()
        st.subheader("연간 목표 설정")
        st.caption("대시보드 상단의 매출/손익 달성률은 여기서 설정한 목표를 기준으로 계산됩니다(시간 안분 없는 단순 비율).")
        목표_df = 연간목표_불러오기()
        입력_연도 = st.number_input(
            "연도", min_value=2020, max_value=2100, value=_dt.date.today().year, step=1, key="목표_연도입력"
        )
        기존_목표행 = 목표_df[목표_df["연도"] == 입력_연도]
        기존_매출_억 = float(기존_목표행.iloc[0]["목표매출"]) / 1e8 if not 기존_목표행.empty else 0.0
        기존_손익_억 = float(기존_목표행.iloc[0]["목표손익"]) / 1e8 if not 기존_목표행.empty else 0.0
        목표매출_col, 목표손익_col = st.columns(2)
        목표매출_억 = 목표매출_col.number_input(
            "목표매출(억원)", min_value=0.0, value=기존_매출_억, step=0.1, key="목표매출_입력"
        )
        목표손익_억 = 목표손익_col.number_input(
            "목표손익(억원)", min_value=0.0, value=기존_손익_억, step=0.1, key="목표손익_입력",
            help="현재는 원가/비용 데이터가 없어 실적 손익 달성률은 계산되지 않습니다. 목표값만 기록해둡니다.",
        )
        if st.button("목표 저장", key="목표_저장_버튼"):
            연간목표_저장(int(입력_연도), round(목표매출_억 * 1e8), round(목표손익_억 * 1e8))
            st.success(f"{입력_연도}년 목표를 저장했습니다.")
            st.rerun()
        if not 목표_df.empty:
            st.caption("등록된 연간 목표")
            목표_표시_df = 목표_df.copy()
            목표_표시_df["목표매출(억원)"] = (목표_표시_df["목표매출"] / 1e8).round(1)
            목표_표시_df["목표손익(억원)"] = (목표_표시_df["목표손익"] / 1e8).round(1)
            st.dataframe(
                목표_표시_df[["연도", "목표매출(억원)", "목표손익(억원)"]],
                use_container_width=True, hide_index=True,
            )

        st.divider()
        st.subheader("투입 인력 관리")
        st.caption("사업 하나를 골라 참여 인력을 추가·삭제합니다 — 인원이 여러 명이라도 별도 표로 관리해 나중에 집계·필터가 가능합니다.")
        if 전체_df.empty:
            st.caption("등록된 사업이 없습니다.")
        else:
            인력_대상_옵션_df = 전체_df.sort_values("종료일")
            인력_대상_id = st.selectbox(
                "사업 선택",
                options=list(인력_대상_옵션_df["id"]),
                format_func=lambda i: (
                    lambda r: f"{r['업체명']} · {r['용역명']}"
                )(인력_대상_옵션_df[인력_대상_옵션_df["id"] == i].iloc[0]),
                key="투입인력_사업선택",
            )
            투입인력_df = 투입인력_불러오기(인력_대상_id)
            if 투입인력_df.empty:
                st.caption("등록된 투입 인력이 없습니다.")
            else:
                for _, 인력행 in 투입인력_df.iterrows():
                    col_이름, col_역할, col_삭제 = st.columns([3, 3, 1])
                    col_이름.write(인력행["이름"])
                    col_역할.write(인력행["역할"] or "-")
                    if col_삭제.button("삭제", key=f"투입인력_삭제_{int(인력행['id'])}"):
                        투입인력_삭제(int(인력행["id"]))
                        st.rerun()

            신규_col1, 신규_col2, 신규_col3 = st.columns([3, 3, 1])
            새_이름 = 신규_col1.text_input("이름", key="투입인력_새이름")
            새_역할 = 신규_col2.text_input("역할(선택)", key="투입인력_새역할", placeholder="예: PM, 실무자")
            if 신규_col3.button("추가", key="투입인력_추가_버튼"):
                if 새_이름.strip():
                    투입인력_저장(인력_대상_id, 새_이름.strip(), 새_역할.strip())
                    st.success("추가했습니다.")
                    st.rerun()
                else:
                    st.warning("이름을 입력하세요.")

    elif 현재_탭_선택 == "사업 온톨로지":
        st.subheader("사업 온톨로지")
        st.caption(
            "오른쪽 AI 채팅에서 '이 사업은 저 사업의 후속이야', '이 두 사업은 같은 고객사야', "
            "'이 사업은 OO기술을 재사용했어' 같은 식으로 이야기하면 여기에 관계가 쌓입니다. "
            "사업뿐 아니라 고객사·기술·담당자 등 자유로운 개념도 노드가 될 수 있습니다. "
            "그래프에서 **노드를 클릭하면 관계 추가**, **선을 클릭하면 관계 삭제**를 할 수 있습니다."
        )

        노드_df = 온톨로지_노드_불러오기()
        관계_df = 온톨로지_관계_불러오기()

        선택된_id_목록: list[int] = []
        선택옵션_df = 전체_df.sort_values("종료일") if not 전체_df.empty else 전체_df
        if not 전체_df.empty:
            선택된_id_목록 = st.multiselect(
                "사업 선택 (여러 개 선택 가능 — 선택한 사업들 중심으로 그래프를 좁혀서 보여줍니다. 비워두면 전체 표시)",
                options=list(선택옵션_df["id"]),
                format_func=lambda v: (
                    lambda r: f"{r['업체명']} · {r['용역명']} (종료일 {r['종료일'] or '미정'})"
                )(선택옵션_df[선택옵션_df["id"] == v].iloc[0]),
            )

        표시할_관계_df = 관계_df
        강조_노드id_집합: set = set()
        if 선택된_id_목록 and not 노드_df.empty:
            강조_노드id_집합 = set(노드_df[노드_df["사업_id"].isin(선택된_id_목록)]["id"].astype(int))
            if 강조_노드id_집합:
                표시할_관계_df = 관계_df[
                    관계_df["출발_노드_id"].isin(강조_노드id_집합) | 관계_df["도착_노드_id"].isin(강조_노드id_집합)
                ]
            else:
                표시할_관계_df = 관계_df.iloc[0:0]

        if 노드_df.empty or 표시할_관계_df.empty:
            if 선택된_id_목록:
                st.info("선택한 사업들에 대해 아직 쌓인 관계가 없습니다. AI 채팅에서 이야기해보세요.")
            else:
                st.info("아직 쌓인 온톨로지가 없습니다. AI 채팅에서 사업들 간의 관계를 이야기해보세요.")
        else:
            노드_유형_팔레트 = _고정_색상맵(sorted(노드_df["유형"].unique()))
            연결된_노드_id = set(표시할_관계_df["출발_노드_id"]) | set(표시할_관계_df["도착_노드_id"])
            표시할_노드_df = 노드_df[노드_df["id"].isin(연결된_노드_id)]

            그래프_데이터 = _온톨로지_그래프_데이터(표시할_노드_df, 표시할_관계_df, 노드_유형_팔레트, 강조_노드id_집합)
            그래프_컴포넌트 = _온톨로지_그래프_컴포넌트()
            그래프결과 = 그래프_컴포넌트(
                data=그래프_데이터, height=460, key="온톨로지_그래프",
                on_node_click_change=lambda: None, on_edge_click_change=lambda: None,
            )
            if 그래프결과.edge_click:
                st.session_state["온톨로지_클릭_엣지"] = int(그래프결과.edge_click)
                st.session_state.pop("온톨로지_클릭_노드", None)
            if 그래프결과.node_click:
                st.session_state["온톨로지_클릭_노드"] = int(그래프결과.node_click)
                st.session_state.pop("온톨로지_클릭_엣지", None)

            클릭된_엣지_id = st.session_state.get("온톨로지_클릭_엣지")
            if 클릭된_엣지_id is not None:
                대상_관계행 = 관계_df[관계_df["id"] == 클릭된_엣지_id]
                if 대상_관계행.empty:
                    st.session_state.pop("온톨로지_클릭_엣지", None)
                else:
                    행 = 대상_관계행.iloc[0]
                    노드_이름맵 = dict(zip(노드_df["id"], 노드_df["이름"]))
                    with st.container(border=True):
                        st.write(
                            f"선택한 관계: **{노드_이름맵.get(행['출발_노드_id'], '?')}** "
                            f"—[{행['관계유형']}]→ **{노드_이름맵.get(행['도착_노드_id'], '?')}**"
                        )
                        지움_col, 닫기_col = st.columns(2)
                        if 지움_col.button("이 관계 삭제", type="primary", key="그래프_엣지_삭제_버튼"):
                            온톨로지_관계_삭제(클릭된_엣지_id)
                            st.session_state.pop("온톨로지_클릭_엣지", None)
                            st.success("삭제했습니다.")
                            st.rerun()
                        if 닫기_col.button("닫기", key="그래프_엣지_닫기_버튼"):
                            st.session_state.pop("온톨로지_클릭_엣지", None)
                            st.rerun()

            클릭된_노드_id = st.session_state.get("온톨로지_클릭_노드")
            if 클릭된_노드_id is not None:
                대상_노드행 = 노드_df[노드_df["id"] == 클릭된_노드_id]
                if 대상_노드행.empty:
                    st.session_state.pop("온톨로지_클릭_노드", None)
                else:
                    행 = 대상_노드행.iloc[0]
                    with st.container(border=True):
                        st.write(f"선택한 노드: **{행['이름']}** ({행['유형']}) — 다른 노드와 연결해보세요.")
                        다른_노드_옵션 = [i for i in 노드_df["id"] if i != 클릭된_노드_id]
                        if not 다른_노드_옵션:
                            st.caption("연결할 다른 노드가 없습니다.")
                        else:
                            대상_노드id = st.selectbox(
                                "연결할 대상",
                                options=다른_노드_옵션,
                                format_func=lambda i: (
                                    lambda r: f"{r['이름']} ({r['유형']})"
                                )(노드_df[노드_df["id"] == i].iloc[0]),
                                key="그래프_연결대상",
                            )
                            관계유형_입력 = st.text_input(
                                "관계유형", placeholder="예: 후속사업, 동일고객, 유사기술", key="그래프_관계유형입력"
                            )
                            if st.button(
                                "관계 추가", type="primary", key="그래프_관계추가_버튼",
                                disabled=not 관계유형_입력.strip(),
                            ):
                                온톨로지_관계_직접추가(
                                    클릭된_노드_id, 대상_노드id, 관계유형_입력.strip(), "", "그래프클릭"
                                )
                                st.session_state.pop("온톨로지_클릭_노드", None)
                                st.success("관계를 추가했습니다.")
                                st.rerun()
                        if st.button("닫기", key="그래프_노드_닫기_버튼"):
                            st.session_state.pop("온톨로지_클릭_노드", None)
                            st.rerun()

            st.divider()
            노드_이름표 = 노드_df[["id", "이름", "유형"]]
            표시용_관계_df = (
                표시할_관계_df.merge(
                    노드_이름표.rename(columns={"id": "출발_노드_id", "이름": "출발", "유형": "출발유형"}),
                    on="출발_노드_id", how="left",
                ).merge(
                    노드_이름표.rename(columns={"id": "도착_노드_id", "이름": "도착", "유형": "도착유형"}),
                    on="도착_노드_id", how="left",
                )
            )
            st.caption(f"관계 {len(표시용_관계_df)}건")
            st.dataframe(
                표시용_관계_df[["출발", "관계유형", "도착", "설명", "작성자", "생성일시"]]
                .sort_values("생성일시", ascending=False),
                use_container_width=True, hide_index=True,
            )

        if not 노드_df.empty:
            with st.expander("⚠️ 온톨로지 전체 초기화"):
                st.warning("모든 사업/개념 노드와 관계가 삭제됩니다. 되돌릴 수 없습니다.")
                초기화_확인 = st.checkbox("전체 초기화에 동의합니다.", key="온톨로지_초기화_확인")
                if st.button("온톨로지 전체 초기화", type="primary", disabled=not 초기화_확인, key="온톨로지_초기화_버튼"):
                    온톨로지_초기화()
                    st.success("온톨로지를 초기화했습니다.")
                    st.rerun()

        if len(선택된_id_목록) == 1:
            선택된_id = 선택된_id_목록[0]
            선택된_행 = 선택옵션_df[선택옵션_df["id"] == 선택된_id].iloc[0]
            선택된_사업명 = f"{선택된_행['업체명']} · {선택된_행['용역명']}"

            st.divider()
            st.subheader(f"'{선택된_사업명}' 메모 · 변경이력")
            기록들 = 이력_불러오기(선택된_id)
            if not 기록들:
                st.caption("아직 기록이 없습니다.")
            else:
                for 기록 in 기록들:
                    st.markdown(f"**{기록['작성일시']}** · {기록['작성자']} · `{기록['유형']}`")
                    st.write(기록["내용"])
                    st.divider()

            st.subheader("메모 · 이벤트 · 특이사항 추가")
            메모_유형 = st.radio(
                "유형", ["메모", "이벤트", "특이사항"], horizontal=True, key="메모_유형선택",
                help="완료 보고, 제안단계 관리 등 눈에 띄는 사건은 '이벤트'나 '특이사항'으로 남겨보세요.",
            )
            메모_작성자 = st.text_input("작성자", key="메모_작성자")
            메모_내용 = st.text_area("내용", key="메모_내용")
            if st.button("추가", key="메모_추가_버튼"):
                if 메모_내용.strip():
                    이력_저장(선택된_id, 메모_유형, 메모_내용.strip(), 메모_작성자, 선택된_사업명)
                    st.success(f"{메모_유형}을 추가했습니다.")
                    st.rerun()
                else:
                    st.warning("내용을 입력하세요.")
        elif len(선택된_id_목록) > 1:
            st.caption("메모·이력은 사업을 하나만 선택했을 때 표시됩니다.")

with 채팅_영역:
    import ai_agent

    st.subheader("AI 에이전트")

    대화_목록 = 대화_목록_불러오기()
    if not 대화_목록:
        대화_생성()
        대화_목록 = 대화_목록_불러오기()
    대화_id_리스트 = [d["id"] for d in 대화_목록]
    대화_제목_맵 = {d["id"]: (d["제목"] or f"새 대화 ({d['생성일시'][:16]})") for d in 대화_목록}

    # "현재_대화_id"는 selectbox 위젯이 소유한 session_state 키라 위젯이 이미 그려진 뒤에는
    # 직접 대입할 수 없다 — 전환 요청은 별도 키에 잠시 담아뒀다가, 위젯이 그려지기 전인
    # 다음 런 시작 시점에 반영한다.
    if "대화_전환_요청" in st.session_state:
        st.session_state["현재_대화_id"] = st.session_state.pop("대화_전환_요청")

    대화선택_col, 새대화_col, 삭제_col = st.columns([3, 1, 1])
    with 대화선택_col:
        현재_대화_id = st.selectbox(
            "대화 선택", options=대화_id_리스트,
            format_func=lambda id_: 대화_제목_맵.get(id_, str(id_)),
            label_visibility="collapsed", key="현재_대화_id",
        )
    with 새대화_col:
        if st.button("＋ 새 대화", use_container_width=True):
            새_id = 대화_생성()
            st.session_state["대화_전환_요청"] = 새_id
            st.session_state.pop("대기중_제안", None)
            st.session_state.pop("삭제확인_대화id", None)
            st.rerun()
    with 삭제_col:
        if st.button("🗑", use_container_width=True, help="이 대화 삭제"):
            st.session_state["삭제확인_대화id"] = 현재_대화_id
            st.rerun()

    if st.session_state.get("삭제확인_대화id") == 현재_대화_id:
        st.warning(f"'{대화_제목_맵.get(현재_대화_id, '')}' 대화를 삭제할까요? 되돌릴 수 없습니다.")
        확인_col1, 확인_col2 = st.columns(2)
        if 확인_col1.button("삭제", type="primary", key="대화삭제_확인버튼"):
            대화_삭제(현재_대화_id)
            st.session_state.pop("삭제확인_대화id", None)
            st.session_state.pop("현재_대화_id", None)
            st.session_state.pop("대기중_제안", None)
            st.rerun()
        if 확인_col2.button("취소", key="대화삭제_취소버튼"):
            st.session_state.pop("삭제확인_대화id", None)
            st.rerun()

    채팅_컨테이너 = st.container(height=480, border=True, key="채팅_상자")
    이전_기록 = 채팅기록_불러오기(현재_대화_id)
    with 채팅_컨테이너:
        if not 이전_기록:
            st.caption(
                "예: '이번달 종료되는 사업은?' / '가나전자 사업을 완료 상태로 바꿔줘' — "
                "엑셀·CSV·PDF·HWP 파일을 첨부(📎)하면 무조건 데이터로 반영하지 않고, "
                "검토·상의가 필요한지 반영이 필요한지 먼저 판단합니다."
            )
        for 메시지 in 이전_기록:
            st.chat_message(메시지["role"]).write(메시지["content"])

        대기중_제안 = st.session_state.get("대기중_제안")
        if 대기중_제안:
            with st.chat_message("assistant"):
                _제안_미리보기_표시(대기중_제안, 전체_df)
                제안_col1, 제안_col2 = st.columns(2)
                if 제안_col1.button("적용", type="primary", key="제안_적용_버튼"):
                    if 대기중_제안.get("유형") in ("업로드",):
                        백업_경로 = DB_PATH.with_name(f"실적관리_{_dt.datetime.now():%Y%m%d%H%M%S}.bak")
                        shutil.copy(DB_PATH, 백업_경로)
                    _제안_반영(대기중_제안, 전체_df)
                    st.session_state.pop("대기중_제안", None)
                    채팅기록_저장(현재_대화_id, "assistant", "반영했습니다.")
                    st.rerun()
                if 제안_col2.button("취소", key="제안_취소_버튼"):
                    st.session_state.pop("대기중_제안", None)
                    채팅기록_저장(현재_대화_id, "assistant", "제안을 취소했습니다.")
                    st.rerun()

    입력 = st.chat_input(
        "질문을 입력하거나 파일을 첨부하세요",
        accept_file=True,
        file_type=["csv", "xlsx", "xls", "pdf", "hwp"],
    )

    if 입력:
        질문 = (입력.text or "").strip()
        첨부파일들 = list(입력.files) if 입력.files else []

        표시_메시지 = 질문
        if 첨부파일들:
            표시_메시지 = (표시_메시지 + f"\n\n📎 {첨부파일들[0].name}").strip()
        if 표시_메시지:
            첫_메시지_여부 = not 이전_기록
            with 채팅_컨테이너:
                st.chat_message("user").write(표시_메시지)
            채팅기록_저장(현재_대화_id, "user", 표시_메시지)
            if 첫_메시지_여부:
                대화_제목_설정(현재_대화_id, ai_agent.대화_제목_생성(표시_메시지))

        첨부_파일명 = 첨부파일들[0].name.lower() if 첨부파일들 else ""
        표_파일 = 첨부_파일명.endswith((".csv", ".xlsx", ".xls"))
        문서_파일 = 첨부_파일명.endswith((".pdf", ".hwp"))

        if 표_파일:
            with 채팅_컨테이너:
                with st.chat_message("assistant"):
                    with st.spinner("AI가 파일을 살펴보는 중..."):
                        원본_df = _업로드_원본_읽기(첨부파일들[0])
                        if 원본_df.empty:
                            답변 = "첨부된 파일에서 데이터를 찾지 못했습니다."
                        else:
                            미리보기_행수 = min(8, len(원본_df))
                            합쳐진_질문 = (
                                f"[첨부 파일 '{첨부파일들[0].name}' 미리보기 — 총 {len(원본_df)}행, "
                                f"컬럼: {list(원본_df.columns)}]\n"
                                f"{원본_df.head(미리보기_행수).to_csv(index=False)}"
                                + (f"...(이하 {len(원본_df) - 미리보기_행수}행 생략)\n" if len(원본_df) > 미리보기_행수 else "")
                                + f"\n[사용자 메시지]\n{질문 or '이 파일을 검토해줘.'}"
                            )
                            API용_기록 = [
                                {"role": m["role"], "content": m["content"]} for m in 이전_기록[-20:]
                            ]
                            결과 = ai_agent.질의하기(합쳐진_질문, history=API용_기록)
                            답변 = 결과["text"]
                            제안 = 결과.get("pending_action")
                            if 제안 and 제안.get("유형") == "import_uploaded_file_as_data":
                                with st.spinner("AI가 사업현황 필드에 맞게 정리하는 중..."):
                                    매핑결과 = ai_agent.업로드_매핑_추론(
                                        list(원본_df.columns), 원본_df.head(5).to_dict("records")
                                    )
                                if "오류" in 매핑결과:
                                    답변 += f"\n\n(반영 중 오류가 있었습니다: {매핑결과['오류']})"
                                else:
                                    결과_df, 경고_목록 = _LLM_매핑_적용(원본_df, 매핑결과)
                                    st.session_state["대기중_제안"] = {
                                        "유형": "업로드", "결과_df": 결과_df, "경고": 경고_목록,
                                    }
                            elif 제안:
                                st.session_state["대기중_제안"] = 제안
                    st.write(답변)
            채팅기록_저장(현재_대화_id, "assistant", 답변)
            st.rerun()
        elif 문서_파일:
            with 채팅_컨테이너:
                with st.chat_message("assistant"):
                    with st.spinner("AI가 문서를 읽는 중..."):
                        try:
                            if 첨부_파일명.endswith(".pdf"):
                                문서_텍스트 = _pdf_텍스트_추출(첨부파일들[0])
                            else:
                                문서_텍스트 = _hwp_텍스트_추출(첨부파일들[0])
                        except Exception as e:
                            문서_텍스트 = None
                            답변 = f"'{첨부파일들[0].name}' 문서를 읽지 못했습니다: {e}"

                        if 문서_텍스트 is not None:
                            if not 문서_텍스트.strip():
                                답변 = f"'{첨부파일들[0].name}'에서 텍스트를 추출하지 못했습니다(스캔 이미지 PDF일 수 있습니다)."
                            else:
                                합쳐진_질문 = (
                                    f"[첨부 문서 '{첨부파일들[0].name}' 내용]\n{문서_텍스트}\n\n"
                                    f"[사용자 질문]\n{질문 or '이 문서 내용을 요약해줘.'}"
                                )
                                API용_기록 = [
                                    {"role": m["role"], "content": m["content"]} for m in 이전_기록[-20:]
                                ]
                                결과 = ai_agent.질의하기(합쳐진_질문, history=API용_기록)
                                답변 = 결과["text"]
                                if 결과.get("pending_action"):
                                    st.session_state["대기중_제안"] = 결과["pending_action"]
                    st.write(답변)
            채팅기록_저장(현재_대화_id, "assistant", 답변)
            st.rerun()
        elif 질문:
            with 채팅_컨테이너:
                with st.chat_message("assistant"):
                    with st.spinner("AI가 SQLite를 조회/제안하며 답변을 생성 중..."):
                        API용_기록 = [
                            {"role": m["role"], "content": m["content"]} for m in 이전_기록[-20:]
                        ]
                        결과 = ai_agent.질의하기(질문, history=API용_기록)
                    st.write(결과["text"])
            채팅기록_저장(현재_대화_id, "assistant", 결과["text"])
            if 결과.get("pending_action"):
                st.session_state["대기중_제안"] = 결과["pending_action"]
            st.rerun()
