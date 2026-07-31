"""공용 비밀번호 하나만 쓰는 간단한 서명 쿠키 인증.

내부 팀 전용 도구라 사용자 계정/DB 테이블 없이, 로그인 성공 시 서명된
httpOnly 쿠키 하나만 내려준다. 프론트(app.*)와 백엔드(api.*)가 같은
루트 도메인의 서브도메인이라 Domain=.kpc-industrialai.com 쿠키를
그대로 공유할 수 있다.
"""

import os

from fastapi import Cookie, HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

COOKIE_NAME = "kpc_session"
SESSION_MAX_AGE_SECONDS = 30 * 24 * 60 * 60  # 30일 로그인 유지


def _secret_key() -> str:
    key = os.environ.get("AUTH_SECRET_KEY")
    if not key:
        raise RuntimeError(
            "AUTH_SECRET_KEY가 설정되어 있지 않습니다. .env 파일에 임의의 긴 문자열을 넣어주세요."
        )
    return key


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret_key(), salt="kpc-industrialai-auth")


def 비밀번호_확인(입력값: str) -> bool:
    설정된_비밀번호 = os.environ.get("APP_PASSWORD")
    return bool(설정된_비밀번호) and 입력값 == 설정된_비밀번호


def 세션_토큰_발급() -> str:
    return _serializer().dumps({"인증됨": True})


def 세션_토큰_검증(토큰: str | None) -> bool:
    if not 토큰:
        return False
    try:
        _serializer().loads(토큰, max_age=SESSION_MAX_AGE_SECONDS)
        return True
    except (BadSignature, SignatureExpired):
        return False


def 인증_확인(kpc_session: str | None = Cookie(default=None)) -> None:
    """FastAPI Depends()로 라우트에 붙이는 공용 인증 게이트. main.py/chat.py가 공유한다."""
    if not 세션_토큰_검증(kpc_session):
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
