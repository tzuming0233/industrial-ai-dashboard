"""
실적분석양식(CSV/Excel) -> SQLite 이관 스크립트

사용법:
    python scripts/01_엑셀_SQLite_이관.py

data/실적데이터.csv (또는 data/실적데이터.xlsx) 파일을 읽어
db/실적관리.db 안에 사업현황 테이블로 적재한다.
기존 실적분석양식.xlsx 를 그대로 쓰고 싶다면 이 스크립트와 같은 폴더
구조로 파일을 data/ 밑에 두고 SOURCE_FILE 값만 바꾸면 된다.
"""

import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_CSV = BASE_DIR / "data" / "실적데이터.csv"
DATA_XLSX = BASE_DIR / "data" / "실적데이터.xlsx"
DB_PATH = BASE_DIR / "db" / "실적관리.db"

COLUMNS = [
    "구분", "업체명", "용역명", "사업구분", "진행상태", "진행률",
    "시작일", "종료일", "계약금액", "기수입금액", "당해년도수입금액",
]


def 원본_데이터_읽기() -> pd.DataFrame:
    if DATA_XLSX.exists():
        df = pd.read_excel(DATA_XLSX)
    elif DATA_CSV.exists():
        df = pd.read_csv(DATA_CSV)
    else:
        raise FileNotFoundError(
            f"data 폴더에 실적데이터.csv 또는 실적데이터.xlsx 파일이 없습니다: {BASE_DIR / 'data'}"
        )

    누락_컬럼 = [c for c in COLUMNS if c not in df.columns]
    if 누락_컬럼:
        raise ValueError(f"필수 컬럼이 없습니다: {누락_컬럼}")

    for 금액컬럼 in ["계약금액", "기수입금액", "당해년도수입금액"]:
        df[금액컬럼] = pd.to_numeric(df[금액컬럼], errors="coerce").fillna(0).astype(int)
    df["진행률"] = pd.to_numeric(df["진행률"], errors="coerce").fillna(0).clip(0, 100).astype(int)
    df["진행상태"] = df["진행상태"].fillna("진행중")

    return df[COLUMNS]


def SQLite로_적재(df: pd.DataFrame) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DROP TABLE IF EXISTS 사업현황")
        conn.execute(
            """
            CREATE TABLE 사업현황 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                구분 TEXT,
                업체명 TEXT,
                용역명 TEXT,
                사업구분 TEXT,
                진행상태 TEXT DEFAULT '진행중',
                진행률 INTEGER DEFAULT 0,
                시작일 TEXT,
                종료일 TEXT,
                계약금액 INTEGER DEFAULT 0,
                기수입금액 INTEGER DEFAULT 0,
                당해년도수입금액 INTEGER DEFAULT 0
            )
            """
        )
        df.to_sql("사업현황", conn, if_exists="append", index=False)
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    df = 원본_데이터_읽기()
    SQLite로_적재(df)
    print(f"이관 완료: {len(df)}건 -> {DB_PATH}")


if __name__ == "__main__":
    main()
