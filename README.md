# 산업AI팀 사업 통합관리 대시보드

산업AI팀 전용 실적관리 Streamlit 앱입니다. 실적 데이터를 SQLite에 담아
대시보드/표/간트차트로 보여주고, 대시보드 화면에서 직접 데이터를 입력·수정하며,
자연어로 AI에게 질의(채팅)할 수 있습니다.

## 폴더 구조

```
industrial_ai_dashboard/
├─ app.py                              # Streamlit 메인 앱 (대시보드/표/간트차트/데이터 관리/AI 채팅)
├─ ai_agent.py                         # Anthropic API tool-use 자연어 질의
├─ requirements.txt                    # 필요 패키지 목록
├─ .env.example                        # 환경변수 예시 (ANTHROPIC_API_KEY)
├─ data/
│  └─ 실적데이터.csv                    # 예시 데이터 (가상 데이터, DB가 없을 때 초기 시드용)
├─ scripts/
│  └─ 01_excel_SQLite_transport.py     # data/ 원본 -> db/실적관리.db 이관 스크립트
└─ db/
   └─ 실적관리.db                       # 최초 실행 시 자동 생성됨 (git에 커밋하지 않음, .gitignore 처리)
```

## 기능

- 대시보드: 사업구분별/구분(신규·이월)별 건수 차트
- 매출현황 표: 사업구분·구분 필터 + CSV 내보내기
- 간트차트: 용역기간(시작일~종료일) 타임라인
- 데이터 관리: 사업현황을 엑셀처럼 표에서 직접 추가·수정·삭제 후 저장
- AI 채팅: 자연어 질문 → SQLite 조회 도구를 호출해 AI가 답변, 대화 이력은 DB에 영구 저장

## 준비 사항

1. Python 3.10 이상
2. 패키지 설치
   ```
   pip install -r requirements.txt
   ```
3. (AI 채팅 탭을 쓰려면) `.env.example` 을 복사해 `.env` 로 저장하고 `ANTHROPIC_API_KEY` 값을 채워 넣기
   (`.env` 는 git에 올리지 않습니다 — `.gitignore` 참고)

## 실행 방법

```
streamlit run app.py
```

최초 실행 시 `db/실적관리.db` 가 없으면 `data/실적데이터.csv` 를 자동으로 읽어 SQLite에 적재합니다.
데이터를 다시 갈아엎고 싶으면 `db/실적관리.db` 파일을 지우고 앱을 다시 실행하거나,
아래처럼 이관 스크립트를 직접 실행하면 됩니다.

```
python scripts/01_excel_SQLite_transport.py
```

이후 실제 데이터는 앱의 "데이터 관리" 탭에서 직접 입력·수정하면 됩니다 (엑셀 재업로드 불필요).

## 데이터 스키마

`구분, 업체명, 용역명, 사업구분, 시작일, 종료일, 계약금액, 기수입금액, 당해년도수입금액`

`data/실적데이터.csv` 에는 실제 거래처·계약 정보 대신 가상의 예시 데이터만 들어있습니다.
실제 운영 데이터는 로컬 `db/실적관리.db` 에만 쌓이며 이 파일은 git에 커밋되지 않습니다.

## GitHub 배포 관련 참고

- `.env`(API 키), `db/*.db`(실제 실적 데이터), `myenv/`(가상환경) 는 `.gitignore` 로 제외되어 있습니다.
- 저장소를 공개/공유하기 전에 `db/` 밑에 실제 데이터가 담긴 `.db` 파일이 남아있지 않은지 확인하세요.
