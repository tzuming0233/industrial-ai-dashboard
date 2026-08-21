"""계정별 서명 쿠키 인증.

로그인 성공 시 사용자_id/이름을 담은 서명된 httpOnly 쿠키 하나만 내려준다(계정
테이블 자체는 repository.py의 `계정` 테이블). 프론트(app.*)와 백엔드(api.*)가
같은 루트 도메인의 서브도메인이라 Domain=.kpc-industrialai.com 쿠키를 그대로
공유할 수 있다.
"""

import hashlib
import os
import secrets

from fastapi import Cookie, Depends, HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

COOKIE_NAME = "kpc_session"
SESSION_MAX_AGE_SECONDS = 30 * 24 * 60 * 60  # 30일 로그인 유지
_PBKDF2_반복수 = 200_000


def _secret_key() -> str:
    key = os.environ.get("AUTH_SECRET_KEY")
    if not key:
        raise RuntimeError(
            "AUTH_SECRET_KEY가 설정되어 있지 않습니다. .env 파일에 임의의 긴 문자열을 넣어주세요."
        )
    return key


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret_key(), salt="kpc-industrialai-auth")


def 비밀번호_해시(평문: str) -> str:
    salt = secrets.token_hex(16)
    해시 = hashlib.pbkdf2_hmac("sha256", 평문.encode(), bytes.fromhex(salt), _PBKDF2_반복수)
    return f"{salt}${해시.hex()}"


def 비밀번호_검증(평문: str, 저장된_해시: str) -> bool:
    try:
        salt, 기대값 = 저장된_해시.split("$", 1)
    except ValueError:
        return False
    해시 = hashlib.pbkdf2_hmac("sha256", 평문.encode(), bytes.fromhex(salt), _PBKDF2_반복수)
    return secrets.compare_digest(해시.hex(), 기대값)


def 세션_토큰_발급(사용자_id: int, 이름: str) -> str:
    return _serializer().dumps({"사용자_id": 사용자_id, "이름": 이름})


def _토큰_페이로드(토큰: str | None) -> dict | None:
    if not 토큰:
        return None
    try:
        return _serializer().loads(토큰, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None


def 세션_토큰_검증(토큰: str | None) -> bool:
    페이로드 = _토큰_페이로드(토큰)
    return bool(페이로드 and 페이로드.get("사용자_id") is not None)


def 세션_정보(토큰: str | None) -> dict | None:
    """/api/me처럼 401 대신 "로그인 안 됨"을 그냥 값으로 돌려받고 싶은 곳에서 쓴다."""
    페이로드 = _토큰_페이로드(토큰)
    if not 페이로드 or 페이로드.get("사용자_id") is None:
        return None
    return {"id": 페이로드["사용자_id"], "이름": 페이로드.get("이름")}


def 현재_사용자(kpc_session: str | None = Cookie(default=None)) -> dict:
    """FastAPI Depends()로 라우트에 붙이는, 로그인한 계정 정보를 돌려주는 의존성.

    예전 형식(`{"인증됨": true}`만 담긴) 쿠키는 사용자_id가 없으므로 그대로
    401 처리된다 — 계정 도입 이전 세션은 이 배포 이후 전부 재로그인이 필요하다.
    """
    페이로드 = _토큰_페이로드(kpc_session)
    if not 페이로드 or 페이로드.get("사용자_id") is None:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return {"id": 페이로드["사용자_id"], "이름": 페이로드.get("이름")}


def 인증_확인(사용자: dict = Depends(현재_사용자)) -> None:
    """FastAPI Depends()로 라우트에 붙이는 공용 인증 게이트. main.py/chat.py/notes.py가
    공유한다 — 사용자 식별이 필요 없는 라우트는 그대로 이 함수만 쓰면 된다."""
    return None
