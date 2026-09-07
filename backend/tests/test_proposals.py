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
