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
