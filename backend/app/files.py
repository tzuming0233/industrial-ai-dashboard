"""업로드 파일(CSV/XLSX/PDF/HWP) 파싱과 AI 매핑 결과 적용 — Streamlit import 없음."""

import io
from pathlib import Path

import pandas as pd

from backend.app.repository import 금액_컬럼들, 사업단계_옵션, 편집_컬럼순서


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
