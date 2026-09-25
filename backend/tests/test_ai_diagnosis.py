from backend.app import repository as repo
from backend.app.ai_diagnosis import _전체단계_계산
from backend.tests.test_conversations import _회원가입


def test_레이어_시드_및_CRUD(temp_db):
    시드됨 = repo.제조AI진단_레이어_목록()
    assert len(시드됨) == 9
    assert {l["코드"] for l in 시드됨} == {f"L{n}" for n in range(1, 10)}
    assert 시드됨[0]["코드"] == "L1"  # 순서 보존

    repo.제조AI진단_레이어_추가(
        "L10", "확장 레이어", "테스트용", ["AI 기능 A"],
        [{"수준": 1, "이름": "P1", "설명": "기준1"}],
    )
    목록 = repo.제조AI진단_레이어_목록()
    assert len(목록) == 10
    assert 목록[-1]["코드"] == "L10"
    assert repo.제조AI진단_레이어_조회("L10")["이름"] == "확장 레이어"

    repo.제조AI진단_레이어_수정("L10", {"이름": "수정된 이름"})
    assert repo.제조AI진단_레이어_조회("L10")["이름"] == "수정된 이름"

    repo.제조AI진단_레이어_삭제("L10")
    assert repo.제조AI진단_레이어_조회("L10") is None
    assert len(repo.제조AI진단_레이어_목록()) == 9


def test_레이어_수정시_버전_스냅샷(temp_db):
    repo.제조AI진단_레이어_수정("L1", {"설명": "첫 수정"}, 작성자="테스트")
    repo.제조AI진단_레이어_수정("L1", {"설명": "두번째 수정"}, 작성자="테스트2")

    버전들 = repo.제조AI진단_레이어_버전_목록("L1")
    assert len(버전들) == 2
    assert 버전들[0]["작성자"] == "테스트2"  # 최신순
    최초_버전 = repo.제조AI진단_레이어_버전_조회(버전들[-1]["id"])
    assert 최초_버전["설명"] != "첫 수정"  # 스냅샷은 '수정 직전' 상태(원래 시드 설명)

    두번째_버전 = repo.제조AI진단_레이어_버전_조회(버전들[0]["id"])
    assert 두번째_버전["설명"] == "첫 수정"  # 두번째 수정 직전 상태


def test_에이전트_종합단계_계산이_라우터와_같은_결과(temp_db):
    """ai_agent.py는 repository.py/ai_diagnosis.py를 import하지 않는 관례상 5단계 밴드 계산을
    복제했다 — 두 구현이 같은 입력에 항상 같은 결론을 내는지 회귀로 고정해둔다."""
    import ai_agent

    샘플들 = [
        {},
        {"L8": 2, "L9": 3},
        {"L8": 2, "L9": 2, "L7": 1},
        {f"L{n}": 3 for n in range(1, 10)},
        {"L4": 2, "L5": 2},
    ]
    for 레이어_수준 in 샘플들:
        라우터_단계 = _전체단계_계산(레이어_수준)["단계"]
        에이전트_결과 = ai_agent._진단_종합단계_계산(레이어_수준)
        assert 에이전트_결과.startswith(f"{라우터_단계}단계"), (레이어_수준, 라우터_단계, 에이전트_결과)


def test_전체단계_계산_경계값():
    assert _전체단계_계산({})["단계"] == 0
    # L8·L9만 P2 이상 → 1단계(Connected Foundation)까지만 도달
    assert _전체단계_계산({"L8": 2, "L9": 3})["단계"] == 1
    # 1단계 요건은 채웠지만 2단계 요건(L7·L3)은 아직
    assert _전체단계_계산({"L8": 2, "L9": 2, "L7": 1})["단계"] == 1
    # 전 레이어 P2 이상 → 5단계(Full-Stack AI Factory)
    전체_만점 = {f"L{n}": 3 for n in range(1, 10)}
    결과 = _전체단계_계산(전체_만점)
    assert 결과["단계"] == 5
    assert 결과["이름"] == "Full-Stack AI Factory"


def test_레이어_정의_9개(client):
    _회원가입(client, "진단A")
    r = client.get("/api/ai-diagnosis/layers")
    assert r.status_code == 200
    레이어들 = r.json()
    assert len(레이어들) == 9
    assert {레이어["코드"] for 레이어 in 레이어들} == {f"L{n}" for n in range(1, 10)}
    assert all(len(레이어["수준들"]) == 3 for 레이어 in 레이어들)


def test_세션_생성_응답저장_조회(client):
    _회원가입(client, "진단B")
    세션_id = client.post("/api/ai-diagnosis/sessions", json={"대상명": "테스트제조㈜"}).json()["id"]

    상세 = client.get(f"/api/ai-diagnosis/sessions/{세션_id}").json()
    assert 상세["대상명"] == "테스트제조㈜"
    assert 상세["응답"] == []
    assert 상세["종합단계"]["단계"] == 0

    응답 = [{"레이어코드": "L8", "수준": 3, "메모": "센서 계장 완료"}, {"레이어코드": "L9", "수준": 2}]
    r = client.put(f"/api/ai-diagnosis/sessions/{세션_id}/responses", json={"응답": 응답})
    assert r.status_code == 200
    저장됨 = r.json()
    assert {row["레이어코드"]: row["수준"] for row in 저장됨["응답"]} == {"L8": 3, "L9": 2}
    assert 저장됨["종합단계"]["단계"] == 1

    # 같은 레이어를 다시 저장하면 덮어쓴다(개수가 늘지 않음)
    client.put(
        f"/api/ai-diagnosis/sessions/{세션_id}/responses",
        json={"응답": [{"레이어코드": "L8", "수준": 1}]},
    )
    재조회 = client.get(f"/api/ai-diagnosis/sessions/{세션_id}").json()
    assert len(재조회["응답"]) == 2
    assert next(r["수준"] for r in 재조회["응답"] if r["레이어코드"] == "L8") == 1


def test_세션_목록_수정_삭제(client):
    _회원가입(client, "진단C")
    세션_id = client.post("/api/ai-diagnosis/sessions", json={"대상명": "원래이름"}).json()["id"]

    목록 = client.get("/api/ai-diagnosis/sessions").json()
    assert len(목록) == 1 and 목록[0]["대상명"] == "원래이름"

    assert client.put(f"/api/ai-diagnosis/sessions/{세션_id}", json={"대상명": "바뀐이름"}).status_code == 200
    assert client.get(f"/api/ai-diagnosis/sessions/{세션_id}").json()["대상명"] == "바뀐이름"

    assert client.delete(f"/api/ai-diagnosis/sessions/{세션_id}").status_code == 200
    assert client.get("/api/ai-diagnosis/sessions").json() == []
    assert client.get(f"/api/ai-diagnosis/sessions/{세션_id}").status_code == 404


def test_세션_빈_대상명은_400(client):
    _회원가입(client, "진단D")
    assert client.post("/api/ai-diagnosis/sessions", json={"대상명": "   "}).status_code == 400


def test_잘못된_레이어코드_수준은_400(client):
    _회원가입(client, "진단E")
    세션_id = client.post("/api/ai-diagnosis/sessions", json={"대상명": "대상"}).json()["id"]

    r1 = client.put(
        f"/api/ai-diagnosis/sessions/{세션_id}/responses",
        json={"응답": [{"레이어코드": "L99", "수준": 1}]},
    )
    assert r1.status_code == 400

    r2 = client.put(
        f"/api/ai-diagnosis/sessions/{세션_id}/responses",
        json={"응답": [{"레이어코드": "L1", "수준": 9}]},
    )
    assert r2.status_code == 400


def test_존재하지_않는_세션은_404(client):
    _회원가입(client, "진단F")
    assert client.get("/api/ai-diagnosis/sessions/999999").status_code == 404
    assert client.put("/api/ai-diagnosis/sessions/999999", json={"대상명": "x"}).status_code == 404
    assert (
        client.put(
            "/api/ai-diagnosis/sessions/999999/responses",
            json={"응답": [{"레이어코드": "L1", "수준": 1}]},
        ).status_code
        == 404
    )


def test_로그인_없이는_401(client):
    assert client.get("/api/ai-diagnosis/layers").status_code == 401
    assert client.get("/api/ai-diagnosis/sessions").status_code == 401
