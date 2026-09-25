from backend.app import chat, repository as repo


def test_제안_요약_propose_add_business(temp_db):
    전체_df = repo.사업현황_불러오기()
    제안 = {
        "유형": "propose_add_business",
        "인자": {"사업목록": [{"업체명": "테스트기업", "용역명": "테스트용역"}]},
    }
    요약 = chat._제안_요약(제안, 전체_df)
    assert 요약["유형"] == "propose_add_business"
    assert len(요약["행"]) == 1
    assert 요약["행"][0]["업체명"] == "테스트기업"


def test_제안_반영_propose_add_business_실제_반영(temp_db):
    전체_df = repo.사업현황_불러오기()
    제안 = {
        "유형": "propose_add_business",
        "인자": {"사업목록": [{"업체명": "신규기업", "용역명": "신규용역", "계약금액": 5000000}]},
    }
    chat._제안_반영(제안, 전체_df, 작성자="테스트")

    반영후_df = repo.사업현황_불러오기()
    assert len(반영후_df) == 1
    assert 반영후_df.iloc[0]["업체명"] == "신규기업"
    assert int(반영후_df.iloc[0]["계약금액"]) == 5000000

    이력 = repo.전체_이력_불러오기()
    assert (이력["유형"] == "추가").any()


def test_제안_반영_propose_update_business(temp_db):
    새_id = repo.사업현황_행_추가({"업체명": "수정대상", "용역명": "용역", "진행률": 0}, 작성자="테스트")
    전체_df = repo.사업현황_불러오기()
    제안 = {"유형": "propose_update_business", "인자": {"id": 새_id, "변경필드": {"진행률": 80}}}
    chat._제안_반영(제안, 전체_df, 작성자="테스트")
    반영후_df = repo.사업현황_불러오기()
    assert int(반영후_df[반영후_df["id"] == 새_id].iloc[0]["진행률"]) == 80


def test_제안_반영_propose_delete_business(temp_db):
    새_id = repo.사업현황_행_추가({"업체명": "삭제대상", "용역명": "용역"}, 작성자="테스트")
    전체_df = repo.사업현황_불러오기()
    제안 = {"유형": "propose_delete_business", "인자": {"ids": [새_id]}}
    chat._제안_반영(제안, 전체_df, 작성자="테스트")
    반영후_df = repo.사업현황_불러오기()
    assert 새_id not in set(반영후_df["id"])


def test_제안_요약_propose_delete_note_없는_노트(temp_db):
    제안 = {"유형": "propose_delete_note", "인자": {"노트_id_목록": [9999]}}
    요약 = chat._제안_요약(제안, repo.사업현황_불러오기())
    assert "오류" in 요약


def test_제안_반영_propose_delete_note(temp_db):
    노트_id = repo.노트_생성("삭제될 노트", "내용")
    제안 = {"유형": "propose_delete_note", "인자": {"노트_id_목록": [노트_id]}}
    chat._제안_반영(제안, repo.사업현황_불러오기(), 작성자="테스트")
    assert repo.노트_불러오기(노트_id) is None


def test_제안_반영_propose_add_staffing(temp_db):
    사업_id = repo.사업현황_행_추가({"업체명": "인력테스트", "용역명": "용역"}, 작성자="테스트")
    제안 = {
        "유형": "propose_add_staffing",
        "인자": {"사업_id": 사업_id, "인력목록": [{"이름": "김철수", "역할": "PM"}]},
    }
    요약 = chat._제안_요약(제안, repo.사업현황_불러오기())
    assert 요약["변경"][0] == {"필드": "김철수", "이전값": None, "새값": "PM"}

    chat._제안_반영(제안, repo.사업현황_불러오기(), 작성자="테스트")
    인력 = repo.투입인력_불러오기(사업_id)
    assert len(인력) == 1 and 인력.iloc[0]["이름"] == "김철수"


def test_제안_반영_propose_delete_staffing(temp_db):
    사업_id = repo.사업현황_행_추가({"업체명": "인력삭제", "용역명": "용역"}, 작성자="테스트")
    repo.투입인력_저장(사업_id, "이영희", "개발자")
    인력_id = int(repo.투입인력_불러오기(사업_id).iloc[0]["id"])

    제안 = {"유형": "propose_delete_staffing", "인자": {"인력_id_목록": [인력_id]}}
    요약 = chat._제안_요약(제안, repo.사업현황_불러오기())
    assert 요약["행"] == [{"이름": "이영희", "역할": "개발자"}]

    chat._제안_반영(제안, repo.사업현황_불러오기(), 작성자="테스트")
    assert repo.투입인력_불러오기(사업_id).empty


def test_제안_요약_propose_delete_staffing_없는_인력(temp_db):
    제안 = {"유형": "propose_delete_staffing", "인자": {"인력_id_목록": [9999]}}
    요약 = chat._제안_요약(제안, repo.사업현황_불러오기())
    assert "오류" in 요약


def test_제안_반영_propose_set_target_신규_및_수정(temp_db):
    제안 = {"유형": "propose_set_target", "인자": {"연도": 2026, "목표매출": 1000, "목표손익": 100}}
    요약 = chat._제안_요약(제안, repo.사업현황_불러오기())
    assert 요약["변경"][0]["이전값"] is None

    chat._제안_반영(제안, repo.사업현황_불러오기(), 작성자="테스트")
    목표 = repo.연간목표_불러오기()
    assert int(목표[목표["연도"] == 2026].iloc[0]["목표매출"]) == 1000

    제안2 = {"유형": "propose_set_target", "인자": {"연도": 2026, "목표매출": 2000, "목표손익": 200}}
    요약2 = chat._제안_요약(제안2, repo.사업현황_불러오기())
    assert 요약2["변경"][0] == {"필드": "목표매출", "이전값": 1000, "새값": 2000}


def test_제안_반영_propose_add_diagnosis(temp_db):
    제안 = {
        "유형": "propose_add_diagnosis",
        "인자": {
            "대상명": "테스트제조㈜",
            "평가목록": [{"레이어코드": "L8", "수준": 2}, {"레이어코드": "L9", "수준": 3}],
        },
    }
    요약 = chat._제안_요약(제안, repo.사업현황_불러오기())
    assert 요약["제목"] == "새 진단: 테스트제조㈜"
    assert 요약["변경"][0]["새값"] == "P2 추상화"

    chat._제안_반영(제안, repo.사업현황_불러오기(), 작성자="테스트")
    세션들 = repo.제조AI진단_세션_목록()
    assert len(세션들) == 1 and 세션들[0]["대상명"] == "테스트제조㈜"
    상세 = repo.제조AI진단_세션_조회(세션들[0]["id"])
    assert {r["레이어코드"]: r["수준"] for r in 상세["응답"]} == {"L8": 2, "L9": 3}


def test_제안_반영_propose_update_diagnosis(temp_db):
    세션_id = repo.제조AI진단_세션_생성("수정대상", "테스트")
    repo.제조AI진단_응답_일괄저장(세션_id, [{"레이어코드": "L1", "수준": 1, "메모": ""}])

    제안 = {
        "유형": "propose_update_diagnosis",
        "인자": {"세션_id": 세션_id, "평가목록": [{"레이어코드": "L1", "수준": 3}]},
    }
    요약 = chat._제안_요약(제안, repo.사업현황_불러오기())
    assert 요약["변경"][0]["이전값"] == "P1 통합"
    assert 요약["변경"][0]["새값"] == "P3 디커플링"

    chat._제안_반영(제안, repo.사업현황_불러오기(), 작성자="테스트")
    상세 = repo.제조AI진단_세션_조회(세션_id)
    assert 상세["응답"][0]["수준"] == 3


def test_제안_요약_propose_update_diagnosis_없는_세션(temp_db):
    제안 = {"유형": "propose_update_diagnosis", "인자": {"세션_id": 9999, "평가목록": []}}
    요약 = chat._제안_요약(제안, repo.사업현황_불러오기())
    assert "오류" in 요약


def test_제안_반영_propose_add_diagnosis_layer(temp_db):
    제안 = {
        "유형": "propose_add_diagnosis_layer",
        "인자": {
            "코드": "L10", "이름": "확장", "설명": "테스트",
            "ai개입지점": ["A"], "수준들": [{"수준": 1, "이름": "P1", "설명": "기준"}],
        },
    }
    요약 = chat._제안_요약(제안, repo.사업현황_불러오기())
    assert 요약["제목"] == "새 레이어: L10 확장"

    chat._제안_반영(제안, repo.사업현황_불러오기(), 작성자="테스트")
    assert repo.제조AI진단_레이어_조회("L10")["이름"] == "확장"


def test_제안_반영_propose_update_diagnosis_layer(temp_db):
    제안 = {"유형": "propose_update_diagnosis_layer", "인자": {"코드": "L1", "변경필드": {"설명": "새 설명"}}}
    요약 = chat._제안_요약(제안, repo.사업현황_불러오기())
    assert 요약["변경"][0]["필드"] == "설명"

    chat._제안_반영(제안, repo.사업현황_불러오기(), 작성자="테스트")
    assert repo.제조AI진단_레이어_조회("L1")["설명"] == "새 설명"


def test_제안_반영_propose_delete_diagnosis_layer(temp_db):
    제안 = {"유형": "propose_delete_diagnosis_layer", "인자": {"코드": "L9"}}
    요약 = chat._제안_요약(제안, repo.사업현황_불러오기())
    assert 요약["행"] == [{"코드": "L9", "이름": "물리 실행"}]

    chat._제안_반영(제안, repo.사업현황_불러오기(), 작성자="테스트")
    assert repo.제조AI진단_레이어_조회("L9") is None
