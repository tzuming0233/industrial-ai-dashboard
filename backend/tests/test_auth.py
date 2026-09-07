import time

import pytest
from fastapi import HTTPException

from backend.app import auth


def test_비밀번호_해시_검증_왕복():
    해시 = auth.비밀번호_해시("올바른비밀번호1")
    assert auth.비밀번호_검증("올바른비밀번호1", 해시)


def test_비밀번호_검증_틀린값_거부():
    해시 = auth.비밀번호_해시("올바른비밀번호1")
    assert not auth.비밀번호_검증("틀린비밀번호", 해시)


def test_비밀번호_검증_잘못된_형식_거부():
    assert not auth.비밀번호_검증("아무거나", "형식이_이상한_해시_문자열")


def test_세션_토큰_발급_검증_왕복():
    토큰 = auth.세션_토큰_발급(42, "홍길동")
    assert auth.세션_토큰_검증(토큰)
    페이로드 = auth._토큰_페이로드(토큰)
    assert 페이로드["사용자_id"] == 42
    assert 페이로드["이름"] == "홍길동"


def test_세션_토큰_만료_거부(monkeypatch):
    monkeypatch.setattr(auth, "SESSION_MAX_AGE_SECONDS", 1)
    토큰 = auth.세션_토큰_발급(1, "테스트")
    assert auth.세션_토큰_검증(토큰)
    time.sleep(2.5)  # itsdangerous가 초 단위로 반올림하므로 1초보다 여유를 둔다.
    assert not auth.세션_토큰_검증(토큰)


def test_로그인_시도_제한_초과시_429():
    for _ in range(5):
        auth.로그인_시도_확인("1.2.3.4")
        auth.로그인_시도_기록("1.2.3.4")
    with pytest.raises(HTTPException) as exc_info:
        auth.로그인_시도_확인("1.2.3.4")
    assert exc_info.value.status_code == 429


def test_로그인_시도_제한_성공시_초기화():
    for _ in range(4):
        auth.로그인_시도_확인("5.6.7.8")
        auth.로그인_시도_기록("5.6.7.8")
    auth.로그인_성공_초기화("5.6.7.8")
    # 초기화됐으니 다시 5번 시도해도 안 막혀야 한다.
    for _ in range(5):
        auth.로그인_시도_확인("5.6.7.8")
        auth.로그인_시도_기록("5.6.7.8")


def test_로그인_시도_제한_키가_다르면_서로_안_섞임():
    for _ in range(5):
        auth.로그인_시도_확인("9.9.9.9")
        auth.로그인_시도_기록("9.9.9.9")
    # 다른 키(IP)는 영향 없어야 한다.
    auth.로그인_시도_확인("10.10.10.10")
