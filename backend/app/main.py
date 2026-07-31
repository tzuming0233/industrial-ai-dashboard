"""FastAPI 뼈대 — Phase 0: 로그인 쿠키 인증 + 읽기전용 API 2개.

app.py(Streamlit)와 완전히 같은 backend.app.repository를 사용하므로,
DB 스키마/쿼리 로직은 이 파일에서 새로 만들지 않는다.
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.app import auth, repository as repo

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

app = FastAPI(title="산업AI팀 사업 통합관리 API")

_기본_허용_출처 = "http://localhost:5173,http://127.0.0.1:5173"
_허용_출처 = [o.strip() for o in os.environ.get("FRONTEND_ORIGIN", _기본_허용_출처).split(",") if o.strip()]
_쿠키_보안 = os.environ.get("COOKIE_SECURE", "true").lower() != "false"
_쿠키_도메인 = os.environ.get("COOKIE_DOMAIN") or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=_허용_출처,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _시작시_DB_준비():
    repo.DB_준비()
    repo.사업현황_컬럼_보강()
    repo.채팅_DB_준비()
    repo.이력_DB_준비()
    repo.온톨로지_DB_준비()
    repo.연간목표_DB_준비()
    repo.투입인력_DB_준비()


class 로그인_요청(BaseModel):
    password: str


_인증_확인 = auth.인증_확인


@app.post("/api/login")
def 로그인(요청: 로그인_요청, response: Response):
    if not auth.비밀번호_확인(요청.password):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")
    토큰 = auth.세션_토큰_발급()
    response.set_cookie(
        key=auth.COOKIE_NAME,
        value=토큰,
        max_age=auth.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=_쿠키_보안,
        samesite="lax",
        domain=_쿠키_도메인,
    )
    return {"ok": True}


@app.post("/api/logout")
def 로그아웃(response: Response):
    response.delete_cookie(key=auth.COOKIE_NAME, domain=_쿠키_도메인)
    return {"ok": True}


@app.get("/api/me")
def 내_세션(kpc_session: str | None = Cookie(default=None)):
    return {"인증됨": auth.세션_토큰_검증(kpc_session)}


def _NaN_정리(df: pd.DataFrame) -> pd.DataFrame:
    return df.where(pd.notna(df), None)


@app.get("/api/business")
def 사업현황(_인증: None = Depends(_인증_확인)):
    df = repo.사업현황_불러오기()
    return _NaN_정리(df).to_dict("records")


@app.get("/api/dashboard-summary")
def 대시보드_요약(_인증: None = Depends(_인증_확인)):
    df = repo.사업현황_불러오기()

    def _건수_목록(컬럼: str) -> list[dict]:
        if df.empty:
            return []
        집계 = df[컬럼].value_counts().reset_index()
        집계.columns = [컬럼, "건수"]
        return 집계.to_dict("records")

    올해 = pd.Timestamp.today().year
    목표_df = repo.연간목표_불러오기()
    올해_목표행 = 목표_df[목표_df["연도"] == 올해] if not 목표_df.empty else 목표_df
    목표매출 = int(올해_목표행.iloc[0]["목표매출"]) if not 올해_목표행.empty else None
    실적_매출 = int(df["당해년도수입금액"].sum()) if not df.empty else 0

    return {
        "전체_건수": int(len(df)),
        "사업구분_수": int(df["사업구분"].nunique()) if not df.empty else 0,
        "구분_수": int(df["구분"].nunique()) if not df.empty else 0,
        "평균_진행률": round(float(df["진행률"].mean()), 1) if not df.empty else 0.0,
        "올해_목표": {
            "연도": 올해,
            "목표매출": 목표매출,
            "실적_매출": 실적_매출,
            "매출_달성률": round(실적_매출 / 목표매출 * 100, 1) if 목표매출 else None,
        },
        "사업구분별_건수": _건수_목록("사업구분"),
        "구분별_건수": _건수_목록("구분"),
        "사업단계별_건수": _건수_목록("사업단계"),
    }


from backend.app.chat import router as _채팅_라우터  # noqa: E402 (순환 임포트 방지 위해 하단 배치)

app.include_router(_채팅_라우터)
