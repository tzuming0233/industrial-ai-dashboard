"""테스트 공용 fixture — 이 세션에서 계속 써온 임시 DB 패턴을 pytest로 옮긴 것.

각 테스트는 격리된 임시 sqlite 파일을 쓴다. repository.py의 DB_PATH를 monkeypatch하면
backend.app의 다른 모듈들(chat.py, notes.py, ontology.py, data_management.py)도 같은
repo 모듈 객체를 공유 import하므로 전부 같은 임시 DB를 보게 된다.
"""

import os
import sqlite3
import sys
from pathlib import Path

import pytest

os.environ.setdefault("AUTH_SECRET_KEY", "test-secret-key-for-pytest-only")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app import auth, chat, repository as repo  # noqa: E402


def _사업현황_테이블_생성(db_path: Path) -> None:
    """repository.py엔 사업현황 CREATE TABLE이 없다(엑셀 이관 스크립트가 만듦) —
    테스트에서는 실제 컬럼 구성 그대로 직접 만든다."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE 사업현황 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                구분 TEXT, 업체명 TEXT, 용역명 TEXT, 사업구분 TEXT, 담당자 TEXT,
                주관참여구분 TEXT, 사업단계 TEXT, 진행률 INTEGER, 시작일 TEXT, 종료일 TEXT,
                계약금액 INTEGER, 기수입금액 INTEGER, 당해년도수입금액 INTEGER
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    _사업현황_테이블_생성(db_path)
    monkeypatch.setattr(repo, "DB_PATH", db_path)

    repo.DB_준비()
    repo.계정_DB_준비()
    repo.채팅_DB_준비()
    repo.이력_DB_준비()
    repo.온톨로지_DB_준비()
    repo.연간목표_DB_준비()
    repo.투입인력_DB_준비()
    repo.노트_DB_준비()
    repo.생성파일_DB_준비()
    repo.사업현황_컬럼_보강()
    return db_path


@pytest.fixture()
def client(temp_db):
    from fastapi.testclient import TestClient
    from backend.app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _모듈_전역_상태_초기화():
    """auth._로그인_시도/chat._대기중_제안은 모듈 레벨 dict라 테스트 간에 그대로 남는다 —
    매 테스트 전후로 비워서 서로 오염시키지 않게 한다."""
    auth._로그인_시도.clear()
    chat._대기중_제안.clear()
    yield
    auth._로그인_시도.clear()
    chat._대기중_제안.clear()
