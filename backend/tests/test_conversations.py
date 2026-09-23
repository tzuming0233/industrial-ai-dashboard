import sqlite3


def _회원가입(client, 이름: str, 비밀번호: str = "충분히긴비밀번호1"):
    r = client.post("/api/signup", json={"이름": 이름, "비밀번호": 비밀번호})
    assert r.status_code == 200, r.text
    return client


def test_회원가입_비밀번호_8자_미만_거부(client):
    r = client.post("/api/signup", json={"이름": "누구", "비밀번호": "짧음"})
    assert r.status_code == 400


def test_로그인_잘못된_비밀번호_401(client):
    _회원가입(client, "사용자A")
    client.cookies.clear()
    r = client.post("/api/login", json={"이름": "사용자A", "비밀번호": "틀린비밀번호"})
    assert r.status_code == 401


def test_소유권_확인_다른_계정_대화_403(temp_db):
    from fastapi.testclient import TestClient
    from backend.app.main import app

    with TestClient(app) as client_a, TestClient(app) as client_b:
        _회원가입(client_a, "계정A")
        r = client_a.post("/api/conversations", json={})
        대화_id = r.json()["id"]

        _회원가입(client_b, "계정B")
        r = client_b.get(f"/api/conversations/{대화_id}/messages")
        assert r.status_code == 403


def test_레거시_null_소유_대화는_모두에게_보임(temp_db):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app import repository as repo

    # 계정 도입 이전처럼 사용자_id가 NULL인 대화를 직접 만든다.
    레거시_대화_id = repo.대화_생성(사업_id=None, 사용자_id=None)

    with TestClient(app) as client_a:
        _회원가입(client_a, "계정C")
        r = client_a.get(f"/api/conversations/{레거시_대화_id}/messages")
        assert r.status_code == 200


def test_대화_삭제_본인_소유만_가능(client):
    _회원가입(client, "사용자D")
    r = client.post("/api/conversations", json={})
    대화_id = r.json()["id"]
    r = client.delete(f"/api/conversations/{대화_id}")
    assert r.status_code == 200
    r = client.get(f"/api/conversations/{대화_id}/messages")
    assert r.status_code == 404


def test_메시지_중단_시_부분_텍스트가_저장됨(client):
    _회원가입(client, "사용자E")
    r = client.post("/api/conversations", json={})
    대화_id = r.json()["id"]

    r = client.post(f"/api/conversations/{대화_id}/messages/stop", json={"텍스트": "생성 중이던 부분 답변"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    r = client.get(f"/api/conversations/{대화_id}/messages")
    메시지들 = r.json()["메시지"]
    assert any(m["role"] == "assistant" and m["content"] == "생성 중이던 부분 답변" for m in 메시지들)


def test_메시지_중단_빈_텍스트는_저장_안_함(client):
    _회원가입(client, "사용자F")
    r = client.post("/api/conversations", json={})
    대화_id = r.json()["id"]

    r = client.post(f"/api/conversations/{대화_id}/messages/stop", json={"텍스트": "   "})
    assert r.status_code == 200

    r = client.get(f"/api/conversations/{대화_id}/messages")
    assert r.json()["메시지"] == []


def test_메시지_중단_다른_계정_대화는_403(temp_db):
    from fastapi.testclient import TestClient
    from backend.app.main import app

    with TestClient(app) as client_a, TestClient(app) as client_b:
        _회원가입(client_a, "계정G")
        r = client_a.post("/api/conversations", json={})
        대화_id = r.json()["id"]

        _회원가입(client_b, "계정H")
        r = client_b.post(f"/api/conversations/{대화_id}/messages/stop", json={"텍스트": "몰래 저장 시도"})
        assert r.status_code == 403


def test_메시지_재생성_기록이_비어있으면_400(client):
    _회원가입(client, "사용자I")
    r = client.post("/api/conversations", json={})
    대화_id = r.json()["id"]

    r = client.post(f"/api/conversations/{대화_id}/messages/retry", data={"model": "기본"})
    assert r.status_code == 400


def test_메시지_재생성_마지막이_user면_400(client, temp_db):
    from backend.app import repository as repo

    _회원가입(client, "사용자J")
    r = client.post("/api/conversations", json={})
    대화_id = r.json()["id"]
    repo.채팅기록_저장(대화_id, "user", "질문만 있고 아직 답변 없음")

    r = client.post(f"/api/conversations/{대화_id}/messages/retry", data={"model": "기본"})
    assert r.status_code == 400
    # 검증 실패 시 기존 메시지는 그대로 남아있어야 한다.
    메시지들 = client.get(f"/api/conversations/{대화_id}/messages").json()["메시지"]
    assert len(메시지들) == 1


def test_메시지_재생성_다른_계정_대화는_403(temp_db):
    from fastapi.testclient import TestClient
    from backend.app.main import app

    with TestClient(app) as client_a, TestClient(app) as client_b:
        _회원가입(client_a, "계정K")
        r = client_a.post("/api/conversations", json={})
        대화_id = r.json()["id"]

        _회원가입(client_b, "계정L")
        r = client_b.post(f"/api/conversations/{대화_id}/messages/retry", data={"model": "기본"})
        assert r.status_code == 403


def test_대화_이름_변경(client):
    _회원가입(client, "사용자M")
    대화_id = client.post("/api/conversations", json={}).json()["id"]

    r = client.patch(f"/api/conversations/{대화_id}", json={"제목": "  새 이름  "})
    assert r.status_code == 200
    목록 = client.get("/api/conversations").json()
    assert next(c for c in 목록 if c["id"] == 대화_id)["제목"] == "새 이름"


def test_대화_이름_변경_빈_제목은_400(client):
    _회원가입(client, "사용자N")
    대화_id = client.post("/api/conversations", json={}).json()["id"]
    r = client.patch(f"/api/conversations/{대화_id}", json={"제목": "   "})
    assert r.status_code == 400


def test_대화_이름_변경_다른_계정은_403(temp_db):
    from fastapi.testclient import TestClient
    from backend.app.main import app

    with TestClient(app) as a, TestClient(app) as b:
        _회원가입(a, "계정P")
        대화_id = a.post("/api/conversations", json={}).json()["id"]
        _회원가입(b, "계정Q")
        assert b.patch(f"/api/conversations/{대화_id}", json={"제목": "탈취"}).status_code == 403


def test_메시지_편집_이후_대화를_버리고_새로_이어간다(client, temp_db):
    from backend.app import repository as repo

    _회원가입(client, "편집A")
    대화_id = client.post("/api/conversations", json={}).json()["id"]
    repo.채팅기록_저장(대화_id, "user", "원래 질문")
    repo.채팅기록_저장(대화_id, "assistant", "원래 답변")
    repo.채팅기록_저장(대화_id, "user", "후속 질문")
    repo.채팅기록_저장(대화_id, "assistant", "후속 답변")

    with client.stream(
        "POST", f"/api/conversations/{대화_id}/messages/edit",
        data={"index": "0", "message": "고친 질문", "model": "기본"},
    ) as resp:
        assert resp.status_code == 200
        본문 = "".join(resp.iter_text())
    assert "event: done" in 본문 or "event: error" in 본문

    메시지들 = client.get(f"/api/conversations/{대화_id}/messages").json()["메시지"]
    assert (메시지들[0]["role"], 메시지들[0]["content"]) == ("user", "고친 질문")
    assert len(메시지들) == 2
    assert 메시지들[1]["role"] == "assistant"


def test_메시지_편집_빈_텍스트는_400(client, temp_db):
    from backend.app import repository as repo

    _회원가입(client, "편집B")
    대화_id = client.post("/api/conversations", json={}).json()["id"]
    repo.채팅기록_저장(대화_id, "user", "질문")
    r = client.post(
        f"/api/conversations/{대화_id}/messages/edit",
        data={"index": "0", "message": "   ", "model": "기본"},
    )
    assert r.status_code == 400


def test_메시지_편집_존재하지_않거나_assistant_인덱스는_400(client, temp_db):
    from backend.app import repository as repo

    _회원가입(client, "편집C")
    대화_id = client.post("/api/conversations", json={}).json()["id"]
    repo.채팅기록_저장(대화_id, "user", "질문")
    repo.채팅기록_저장(대화_id, "assistant", "답변")

    r = client.post(
        f"/api/conversations/{대화_id}/messages/edit",
        data={"index": "1", "message": "고친 답변?", "model": "기본"},
    )
    assert r.status_code == 400

    r = client.post(
        f"/api/conversations/{대화_id}/messages/edit",
        data={"index": "5", "message": "없는 인덱스", "model": "기본"},
    )
    assert r.status_code == 400


def test_메시지_편집_다른_계정_대화는_403(temp_db):
    from fastapi.testclient import TestClient
    from backend.app.main import app

    with TestClient(app) as a, TestClient(app) as b:
        _회원가입(a, "편집D")
        대화_id = a.post("/api/conversations", json={}).json()["id"]
        _회원가입(b, "편집E")
        r = b.post(
            f"/api/conversations/{대화_id}/messages/edit",
            data={"index": "0", "message": "탈취 시도", "model": "기본"},
        )
        assert r.status_code == 403


def test_대화_검색_내용과_제목_모두_찾는다(client, temp_db):
    from backend.app import repository as repo

    _회원가입(client, "검색A")
    대화1 = client.post("/api/conversations", json={}).json()["id"]
    repo.채팅기록_저장(대화1, "user", "가나전자 출장비 정산 문의")
    repo.채팅기록_저장(대화1, "assistant", "출장비는 실비 정산입니다.")
    대화2 = client.post("/api/conversations", json={}).json()["id"]
    repo.대화_제목_설정(대화2, "가나전자 계약 검토")
    대화3 = client.post("/api/conversations", json={}).json()["id"]
    repo.채팅기록_저장(대화3, "user", "전혀 관련 없는 질문")

    r = client.get("/api/conversations/search", params={"q": "가나전자"})
    assert r.status_code == 200
    결과 = r.json()
    대화_id들 = {row["대화_id"] for row in 결과}
    assert 대화_id들 == {대화1, 대화2}
    본문매치 = next(row for row in 결과 if row["대화_id"] == 대화1)
    assert "가나전자" in 본문매치["미리보기"]


def test_대화_검색_짧은_검색어는_빈_목록(client):
    _회원가입(client, "검색B")
    assert client.get("/api/conversations/search", params={"q": "가"}).json() == []
    assert client.get("/api/conversations/search", params={"q": ""}).json() == []


def test_대화_검색_다른_계정_대화는_안_보임(temp_db):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app import repository as repo

    with TestClient(app) as a, TestClient(app) as b:
        _회원가입(a, "검색C")
        대화_id = a.post("/api/conversations", json={}).json()["id"]
        repo.채팅기록_저장(대화_id, "user", "비공개 키워드입니다")
        _회원가입(b, "검색D")
        assert b.get("/api/conversations/search", params={"q": "비공개"}).json() == []


def test_메시지_피드백_저장_수정_취소(client, temp_db):
    from backend.app import repository as repo

    _회원가입(client, "피드백A")
    대화_id = client.post("/api/conversations", json={}).json()["id"]
    repo.채팅기록_저장(대화_id, "user", "질문")
    repo.채팅기록_저장(대화_id, "assistant", "답변")
    메시지_id = client.get(f"/api/conversations/{대화_id}/messages").json()["메시지"][1]["id"]

    r = client.post(f"/api/conversations/{대화_id}/messages/{메시지_id}/feedback", json={"rating": "up"})
    assert r.status_code == 200
    메시지들 = client.get(f"/api/conversations/{대화_id}/messages").json()["메시지"]
    assert 메시지들[1]["rating"] == "up"

    client.post(f"/api/conversations/{대화_id}/messages/{메시지_id}/feedback", json={"rating": "down"})
    메시지들 = client.get(f"/api/conversations/{대화_id}/messages").json()["메시지"]
    assert 메시지들[1]["rating"] == "down"

    client.post(f"/api/conversations/{대화_id}/messages/{메시지_id}/feedback", json={"rating": None})
    메시지들 = client.get(f"/api/conversations/{대화_id}/messages").json()["메시지"]
    assert 메시지들[1]["rating"] is None


def test_메시지_피드백_user_메시지는_400(client, temp_db):
    from backend.app import repository as repo

    _회원가입(client, "피드백B")
    대화_id = client.post("/api/conversations", json={}).json()["id"]
    repo.채팅기록_저장(대화_id, "user", "질문")
    메시지_id = client.get(f"/api/conversations/{대화_id}/messages").json()["메시지"][0]["id"]
    r = client.post(f"/api/conversations/{대화_id}/messages/{메시지_id}/feedback", json={"rating": "up"})
    assert r.status_code == 400


def test_메시지_피드백_잘못된_값은_400(client, temp_db):
    from backend.app import repository as repo

    _회원가입(client, "피드백C")
    대화_id = client.post("/api/conversations", json={}).json()["id"]
    repo.채팅기록_저장(대화_id, "assistant", "답변")
    메시지_id = client.get(f"/api/conversations/{대화_id}/messages").json()["메시지"][0]["id"]
    r = client.post(f"/api/conversations/{대화_id}/messages/{메시지_id}/feedback", json={"rating": "별로"})
    assert r.status_code == 400


def test_메시지_피드백_존재하지_않는_메시지는_404(client):
    _회원가입(client, "피드백D")
    대화_id = client.post("/api/conversations", json={}).json()["id"]
    r = client.post(f"/api/conversations/{대화_id}/messages/9999/feedback", json={"rating": "up"})
    assert r.status_code == 404


def test_메시지_피드백_다른_계정_대화는_403(temp_db):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app import repository as repo

    with TestClient(app) as a, TestClient(app) as b:
        _회원가입(a, "피드백E")
        대화_id = a.post("/api/conversations", json={}).json()["id"]
        repo.채팅기록_저장(대화_id, "assistant", "답변")
        메시지_id = a.get(f"/api/conversations/{대화_id}/messages").json()["메시지"][0]["id"]
        _회원가입(b, "피드백F")
        r = b.post(f"/api/conversations/{대화_id}/messages/{메시지_id}/feedback", json={"rating": "up"})
        assert r.status_code == 403


def test_메시지_편집으로_지워진_메시지의_피드백도_함께_지워진다(client, temp_db):
    from backend.app import repository as repo

    _회원가입(client, "피드백G")
    대화_id = client.post("/api/conversations", json={}).json()["id"]
    repo.채팅기록_저장(대화_id, "user", "질문")
    repo.채팅기록_저장(대화_id, "assistant", "답변")
    메시지_id = client.get(f"/api/conversations/{대화_id}/messages").json()["메시지"][1]["id"]
    client.post(f"/api/conversations/{대화_id}/messages/{메시지_id}/feedback", json={"rating": "up"})

    with client.stream(
        "POST", f"/api/conversations/{대화_id}/messages/edit",
        data={"index": "0", "message": "고친 질문", "model": "기본"},
    ) as resp:
        "".join(resp.iter_text())

    conn = sqlite3.connect(temp_db)
    남은_피드백 = conn.execute("SELECT COUNT(*) FROM 메시지_피드백 WHERE 메시지_id = ?", (메시지_id,)).fetchone()[0]
    conn.close()
    assert 남은_피드백 == 0
