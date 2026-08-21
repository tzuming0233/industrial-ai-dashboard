"""FastAPI 뼈대 — Phase 0: 로그인 쿠키 인증 + 읽기전용 API 2개.

app.py(Streamlit)와 완전히 같은 backend.app.repository를 사용하므로,
DB 스키마/쿼리 로직은 이 파일에서 새로 만들지 않는다.
"""

import os
from pathlib import Path
from urllib.parse import quote

import pandas as pd
from dotenv import load_dotenv
from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.app import auth, repository as repo
from backend.app.files import 엑셀로_변환

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
    repo.노트_DB_준비()
    repo.생성파일_DB_준비()


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
    # astype(object) 없이 그냥 .where(notna, None)만 쓰면 NULL 섞인 정수 컬럼(float64로
    # 읽힘)에서 대입한 None이 다시 NaN으로 되돌아가 json.dumps가 500을 낸다.
    # (backend/app/ontology.py의 같은 이름 함수에서 실제로 겪은 버그 — 참고)
    return df.astype(object).where(df.notna(), None)


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

    오늘 = pd.Timestamp.today().normalize()
    임박_df = df.copy()
    마감임박: list[dict] = []
    if not 임박_df.empty:
        임박_df["종료일_dt"] = pd.to_datetime(임박_df["종료일"], errors="coerce")
        임박_df["D-day"] = (임박_df["종료일_dt"] - 오늘).dt.days
        임박_df = 임박_df[
            임박_df["종료일_dt"].notna()
            & (임박_df["D-day"] <= 30)
            & (pd.to_numeric(임박_df["진행률"], errors="coerce").fillna(0) < 100)
        ].sort_values("D-day")
        마감임박 = _NaN_정리(임박_df[["업체명", "용역명", "종료일", "D-day", "사업단계"]]).to_dict("records")

    담당자별_건수: list[dict] = []
    if not df.empty:
        담당자_시리즈 = df["담당자"].replace("", "(미지정)").fillna("(미지정)")
        집계 = 담당자_시리즈.value_counts().reset_index()
        집계.columns = ["담당자", "건수"]
        담당자별_건수 = 집계.to_dict("records")

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
        "담당자별_건수": 담당자별_건수,
        "마감임박": 마감임박,
    }


@app.get("/api/history")
def 전체_이력(_인증: None = Depends(_인증_확인)):
    df = repo.전체_이력_불러오기()
    return _NaN_정리(df).to_dict("records")


class _내보내기_요청(BaseModel):
    행: list[dict]


@app.post("/api/export/xlsx")
def xlsx_내보내기(요청: _내보내기_요청, _인증: None = Depends(_인증_확인)):
    df = pd.DataFrame(요청.행)
    데이터 = 엑셀로_변환(df)
    return Response(
        content=데이터,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=export.xlsx"},
    )


_미리보기_가능_mime타입 = {"text/html", "image/svg+xml"}


@app.get("/api/files/{file_id}")
def 생성파일_다운로드(file_id: int, _인증: None = Depends(_인증_확인)):
    파일 = repo.생성파일_불러오기(file_id)
    if not 파일:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    # 파일명이 한글일 수 있어 RFC 5987(filename*=UTF-8''...)로 인코딩 — 그냥 filename=만 쓰면
    # 브라우저/프록시에 따라 비ASCII 문자가 깨질 수 있다.
    인코딩된_파일명 = quote(파일["파일명"])
    # HTML/SVG처럼 브라우저가 직접 렌더링할 수 있는 형식은 강제 다운로드(attachment) 대신
    # inline으로 내려서 새 탭에서 바로 보이게 한다(Claude.ai 아티팩트 미리보기와 같은 경험).
    처분방식 = "inline" if 파일["mime타입"] in _미리보기_가능_mime타입 else "attachment"
    return Response(
        content=파일["내용"],
        media_type=파일["mime타입"] or "application/octet-stream",
        headers={"Content-Disposition": f"{처분방식}; filename*=UTF-8''{인코딩된_파일명}"},
    )


from backend.app.chat import router as _채팅_라우터  # noqa: E402 (순환 임포트 방지 위해 하단 배치)
from backend.app.ontology import router as _온톨로지_라우터  # noqa: E402
from backend.app.notes import router as _노트_라우터  # noqa: E402

app.include_router(_채팅_라우터)
app.include_router(_온톨로지_라우터)
app.include_router(_노트_라우터)
