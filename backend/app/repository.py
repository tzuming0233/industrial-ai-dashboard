"""사업현황/대화/채팅기록/온톨로지/이력/투입인력/연간목표 DB 접근 계층.

Streamlit import가 전혀 없다 — app.py(Streamlit)와 backend(FastAPI)가 이 모듈을
동시에 import해서 쓴다. 두 스택이 따로 도는 동안 DB 스키마·쿼리 로직이
어긋나지 않게 하는 것이 이 모듈을 분리한 유일한 목적이므로, 함수를 옮길 때
로직을 절대 바꾸지 않는다(한글 이름도 그대로 유지).
"""

import datetime as _dt
import importlib.util
import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "db" / "실적관리.db"

금액_컬럼들 = ["계약금액", "기수입금액", "당해년도수입금액"]
편집_컬럼순서 = [
    "id", "구분", "업체명", "용역명", "사업구분", "담당자", "주관참여구분", "사업단계", "진행률",
    "시작일", "종료일", "계약금액", "기수입금액", "당해년도수입금액",
]
# 사업단계: 사업 발굴 -> 수주 계획 -> 제안 진행 -> 계약 체결 -> 사업 수행. '미분류'는 옛 진행상태에서
# 자동으로 매핑할 수 없어 남겨둔 임시값 — 담당자가 직접 재분류해야 한다.
사업단계_옵션 = ["미분류", "사업 발굴", "수주 계획", "제안 진행", "계약 체결", "사업 수행"]
주관참여구분_옵션 = ["", "주관", "참여"]


def _캐시(func):
    """st.cache_data 대체용 최소 캐시 — 같은 .clear() API를 유지해 호출부를 안 바꿔도 되게 한다.

    st.cache_data처럼 DataFrame을 반환하기 전에 복사본을 내줘서, 호출한 쪽에서
    반환값을 그대로 변형해도 캐시된 원본이 오염되지 않게 한다.
    """
    저장소: dict = {}

    def wrapper(*args, **kwargs):
        키 = (args, tuple(sorted(kwargs.items())))
        if 키 not in 저장소:
            저장소[키] = func(*args, **kwargs)
        값 = 저장소[키]
        return 값.copy() if hasattr(값, "copy") else 값

    def clear():
        저장소.clear()

    wrapper.clear = clear
    return wrapper


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
        # Claude 프로젝트처럼, 대화를 사업현황의 특정 사업과 1:1로 묶을 수 있게 하는 연결 컬럼.
        # NULL이면 특정 사업과 무관한 일반 대화.
        기존_대화_컬럼 = {row[1] for row in conn.execute("PRAGMA table_info(대화)")}
        if "사업_id" not in 기존_대화_컬럼:
            conn.execute("ALTER TABLE 대화 ADD COLUMN 사업_id INTEGER")
        # 긴 대화에서 API에 매번 보내는 최근 20개 밖의 오래된 부분을 담아두는 요약.
        # 요약_메시지수는 지금까지 이 요약에 반영된 메시지가 몇 개인지 — 다음번에 새로
        # "오래된" 취급을 받게 된 메시지만 델타로 요약에 덧붙이기 위한 커서 역할을 한다.
        if "요약" not in 기존_대화_컬럼:
            conn.execute("ALTER TABLE 대화 ADD COLUMN 요약 TEXT")
        if "요약_메시지수" not in 기존_대화_컬럼:
            conn.execute("ALTER TABLE 대화 ADD COLUMN 요약_메시지수 INTEGER DEFAULT 0")
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


@_캐시
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


@_캐시
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


@_캐시
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


@_캐시
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
            "SELECT id, 제목, 생성일시, 마지막_활동일시, 사업_id FROM 대화 ORDER BY 마지막_활동일시 DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def 대화_생성(사업_id: int | None = None) -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        지금 = _dt.datetime.now().isoformat(timespec="seconds")
        cur = conn.execute(
            "INSERT INTO 대화 (제목, 생성일시, 마지막_활동일시, 사업_id) VALUES (?, ?, ?, ?)",
            (None, 지금, 지금, 사업_id),
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


def 대화_요약_불러오기(대화_id: int) -> tuple[str | None, int]:
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT 요약, 요약_메시지수 FROM 대화 WHERE id = ?", (대화_id,)).fetchone()
        if not row:
            return None, 0
        return row[0], row[1] or 0
    finally:
        conn.close()


def 대화_요약_저장(대화_id: int, 요약: str, 메시지수: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE 대화 SET 요약 = ?, 요약_메시지수 = ? WHERE id = ?", (요약, 메시지수, 대화_id)
        )
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


@_캐시
def 온톨로지_노드_불러오기() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql("SELECT * FROM 온톨로지_노드", conn)
    finally:
        conn.close()


@_캐시
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


def 노트_DB_준비():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS 노트 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                제목 TEXT NOT NULL,
                내용 TEXT,
                위키_내용 TEXT,
                태그 TEXT,
                생성일시 TEXT,
                수정일시 TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


@_캐시
def 노트_목록_불러오기() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, 제목, 태그, 생성일시, 수정일시 FROM 노트 ORDER BY 수정일시 DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def 노트_불러오기(노트_id: int) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM 노트 WHERE id = ?", (int(노트_id),)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def 노트_생성(제목: str, 내용: str = "", 태그: str = "") -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        지금 = _dt.datetime.now().isoformat(timespec="seconds")
        cur = conn.execute(
            "INSERT INTO 노트 (제목, 내용, 위키_내용, 태그, 생성일시, 수정일시) VALUES (?, ?, NULL, ?, ?, ?)",
            (제목, 내용, 태그, 지금, 지금),
        )
        conn.commit()
        새_id = cur.lastrowid
    finally:
        conn.close()
    노트_목록_불러오기.clear()
    return 새_id


def 노트_수정(노트_id: int, 변경필드: dict) -> None:
    허용_필드 = {"제목", "내용", "위키_내용", "태그"}
    반영할_필드 = {k: v for k, v in 변경필드.items() if k in 허용_필드}
    if not 반영할_필드:
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        반영할_필드["수정일시"] = _dt.datetime.now().isoformat(timespec="seconds")
        set절 = ", ".join(f"{c} = ?" for c in 반영할_필드)
        conn.execute(f"UPDATE 노트 SET {set절} WHERE id = ?", [*반영할_필드.values(), int(노트_id)])
        conn.commit()
    finally:
        conn.close()
    노트_목록_불러오기.clear()


def 노트_삭제(노트_id: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM 노트 WHERE id = ?", (int(노트_id),))
        conn.commit()
    finally:
        conn.close()
    노트_목록_불러오기.clear()


def 노트_검색(검색어: str | None = None) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        if 검색어:
            rows = conn.execute(
                "SELECT id, 제목, 태그, 생성일시, 수정일시 FROM 노트 "
                "WHERE 제목 LIKE ? OR 내용 LIKE ? OR 태그 LIKE ? ORDER BY 수정일시 DESC",
                (f"%{검색어}%", f"%{검색어}%", f"%{검색어}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, 제목, 태그, 생성일시, 수정일시 FROM 노트 ORDER BY 수정일시 DESC"
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def 생성파일_DB_준비():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS 생성파일 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                대화_id INTEGER,
                파일명 TEXT,
                mime타입 TEXT,
                내용 BLOB,
                생성일시 TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def 생성파일_저장(대화_id: int | None, 파일명: str, mime타입: str, 내용: bytes) -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        지금 = _dt.datetime.now().isoformat(timespec="seconds")
        cur = conn.execute(
            "INSERT INTO 생성파일 (대화_id, 파일명, mime타입, 내용, 생성일시) VALUES (?, ?, ?, ?, ?)",
            (대화_id, 파일명, mime타입, 내용, 지금),
        )
        conn.commit()
        새_id = cur.lastrowid
    finally:
        conn.close()
    return 새_id


def 생성파일_불러오기(파일_id: int) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, 파일명, mime타입, 내용 FROM 생성파일 WHERE id = ?", (int(파일_id),)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
