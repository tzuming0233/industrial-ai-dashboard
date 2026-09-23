import sqlite3

from backend.tests.test_conversations import _회원가입


def _txt(이름: str, 내용: str):
    return {"file": (이름, 내용.encode("utf-8"), "text/plain")}


def test_프로젝트_생성_목록_상세(client):
    _회원가입(client, "프로젝트A")
    r = client.post("/api/projects", json={"이름": "  AI 바우처  ", "설명": "설명", "지침": "존댓말로"})
    assert r.status_code == 200
    프로젝트_id = r.json()["id"]

    목록 = client.get("/api/projects").json()
    assert [p["이름"] for p in 목록] == ["AI 바우처"]
    assert 목록[0]["대화수"] == 0 and 목록[0]["지식수"] == 0

    상세 = client.get(f"/api/projects/{프로젝트_id}").json()
    assert 상세["지침"] == "존댓말로"
    assert 상세["지식"] == []
    assert 상세["지식_한도"] > 0


def test_프로젝트_빈_이름은_400(client):
    _회원가입(client, "프로젝트B")
    assert client.post("/api/projects", json={"이름": "   "}).status_code == 400


def test_프로젝트_수정과_사업연결_해제(client):
    _회원가입(client, "프로젝트C")
    프로젝트_id = client.post("/api/projects", json={"이름": "원래", "사업_id": 7}).json()["id"]

    assert client.patch(f"/api/projects/{프로젝트_id}", json={"이름": "바뀜", "지침": "지침"}).status_code == 200
    상세 = client.get(f"/api/projects/{프로젝트_id}").json()
    assert (상세["이름"], 상세["지침"], 상세["사업_id"]) == ("바뀜", "지침", 7)

    # 이름만 보낸 수정은 사업 연결을 건드리지 않고, 명시적 null만 해제한다.
    client.patch(f"/api/projects/{프로젝트_id}", json={"설명": "설명만"})
    assert client.get(f"/api/projects/{프로젝트_id}").json()["사업_id"] == 7
    client.patch(f"/api/projects/{프로젝트_id}", json={"사업_id": None})
    assert client.get(f"/api/projects/{프로젝트_id}").json()["사업_id"] is None


def test_다른_계정_프로젝트는_403(temp_db):
    from fastapi.testclient import TestClient
    from backend.app.main import app

    with TestClient(app) as a, TestClient(app) as b:
        _회원가입(a, "주인")
        프로젝트_id = a.post("/api/projects", json={"이름": "비공개"}).json()["id"]
        _회원가입(b, "남")
        assert b.get(f"/api/projects/{프로젝트_id}").status_code == 403
        assert b.patch(f"/api/projects/{프로젝트_id}", json={"이름": "탈취"}).status_code == 403
        assert b.delete(f"/api/projects/{프로젝트_id}").status_code == 403
        assert b.post(f"/api/projects/{프로젝트_id}/knowledge", files=_txt("a.txt", "x")).status_code == 403
        assert b.post("/api/conversations", json={"프로젝트_id": 프로젝트_id}).status_code == 403
        assert b.get("/api/projects").json() == []


def test_지식_파일_추가_삭제(client):
    _회원가입(client, "지식A")
    프로젝트_id = client.post("/api/projects", json={"이름": "P"}).json()["id"]

    r = client.post(f"/api/projects/{프로젝트_id}/knowledge", files=_txt("규정.txt", "출장비는 실비 정산한다."))
    assert r.status_code == 200
    지식_id = r.json()["id"]

    상세 = client.get(f"/api/projects/{프로젝트_id}").json()
    assert [k["파일명"] for k in 상세["지식"]] == ["규정.txt"]
    assert 상세["지식_글자수"] == len("출장비는 실비 정산한다.")

    assert client.delete(f"/api/projects/{프로젝트_id}/knowledge/{지식_id}").status_code == 200
    assert client.get(f"/api/projects/{프로젝트_id}").json()["지식"] == []
    assert client.delete(f"/api/projects/{프로젝트_id}/knowledge/{지식_id}").status_code == 404


def test_지식_지원하지_않는_형식과_빈_파일은_400(client):
    _회원가입(client, "지식B")
    프로젝트_id = client.post("/api/projects", json={"이름": "P"}).json()["id"]
    assert client.post(f"/api/projects/{프로젝트_id}/knowledge", files=_txt("a.exe", "x")).status_code == 400
    assert client.post(f"/api/projects/{프로젝트_id}/knowledge", files=_txt("빈.txt", "   ")).status_code == 400


def test_지식_용량_초과는_400(client, monkeypatch):
    from backend.app import projects

    monkeypatch.setattr(projects, "지식_프로젝트당_최대_글자수", 30)
    _회원가입(client, "지식C")
    프로젝트_id = client.post("/api/projects", json={"이름": "P"}).json()["id"]
    assert client.post(f"/api/projects/{프로젝트_id}/knowledge", files=_txt("a.txt", "가" * 20)).status_code == 200
    r = client.post(f"/api/projects/{프로젝트_id}/knowledge", files=_txt("b.txt", "나" * 20))
    assert r.status_code == 400
    assert "용량" in r.json()["detail"]


def test_프로젝트_삭제해도_대화는_남는다(client):
    _회원가입(client, "삭제A")
    프로젝트_id = client.post("/api/projects", json={"이름": "P"}).json()["id"]
    client.post(f"/api/projects/{프로젝트_id}/knowledge", files=_txt("a.txt", "내용"))
    대화_id = client.post("/api/conversations", json={"프로젝트_id": 프로젝트_id}).json()["id"]
    assert client.get(f"/api/projects/{프로젝트_id}").json()["대화"][0]["id"] == 대화_id

    assert client.delete(f"/api/projects/{프로젝트_id}").status_code == 200
    assert client.get(f"/api/projects/{프로젝트_id}").status_code == 404
    남은 = next(c for c in client.get("/api/conversations").json() if c["id"] == 대화_id)
    assert 남은["프로젝트_id"] is None


def test_대화_메시지_응답에_프로젝트_정보(client):
    _회원가입(client, "메시지A")
    프로젝트_id = client.post("/api/projects", json={"이름": "내 프로젝트"}).json()["id"]
    대화_id = client.post("/api/conversations", json={"프로젝트_id": 프로젝트_id}).json()["id"]
    assert client.get(f"/api/conversations/{대화_id}/messages").json()["프로젝트"] == {
        "id": 프로젝트_id, "이름": "내 프로젝트",
    }
    일반_id = client.post("/api/conversations", json={}).json()["id"]
    assert client.get(f"/api/conversations/{일반_id}/messages").json()["프로젝트"] is None


def test_프로젝트_시스템_텍스트에_지침과_지식이_들어간다(client, temp_db):
    from backend.app import projects, repository as repo
    import ai_agent

    _회원가입(client, "시스템A")
    프로젝트_id = client.post("/api/projects", json={"이름": "정산", "지침": "항상 표로 답하라"}).json()["id"]
    client.post(f"/api/projects/{프로젝트_id}/knowledge", files=_txt("규정.txt", "출장비는 실비 정산"))

    텍스트 = projects.프로젝트_시스템_텍스트(repo.프로젝트_조회(프로젝트_id))
    assert "항상 표로 답하라" in 텍스트
    assert "규정.txt" in 텍스트 and "출장비는 실비 정산" in 텍스트
    assert projects.프로젝트_시스템_텍스트(None) == ""

    # 시스템 프롬프트 블록으로 붙고, 큰 지식이 매 턴 캐시되도록 cache_control이 걸린다.
    블록들 = ai_agent._시스템_프롬프트_구성(텍스트)
    assert 블록들[-1]["text"] == 텍스트
    assert 블록들[-1]["cache_control"] == {"type": "ephemeral"}
    assert ai_agent._시스템_프롬프트_구성("")[-1]["text"] != 텍스트


def test_기존_사업연결_대화는_프로젝트로_이관된다(temp_db):
    conn = sqlite3.connect(temp_db)
    conn.execute("INSERT INTO 사업현황 (id, 업체명, 용역명) VALUES (5, '가나전자', 'AI 도입')")
    conn.execute("INSERT INTO 대화 (제목, 사업_id, 사용자_id) VALUES ('a', 5, NULL)")
    conn.execute("INSERT INTO 대화 (제목, 사업_id, 사용자_id) VALUES ('b', 5, NULL)")
    conn.execute("INSERT INTO 대화 (제목, 사업_id, 사용자_id) VALUES ('c', NULL, NULL)")
    # 프로젝트 도입 이전 스키마로 되돌려 마이그레이션이 다시 돌게 한다.
    conn.execute("DROP TABLE 프로젝트")
    conn.execute("DROP TABLE 프로젝트_지식")
    conn.execute("DROP INDEX idx_대화_프로젝트_id")
    conn.execute("ALTER TABLE 대화 DROP COLUMN 프로젝트_id")
    conn.commit()
    conn.close()

    from backend.app import repository as repo

    repo.채팅_DB_준비()
    repo.채팅_DB_준비()  # 두 번 돌려도 중복 이관되지 않아야 한다.

    conn = sqlite3.connect(temp_db)
    프로젝트들 = conn.execute("SELECT id, 이름, 사업_id, 사용자_id FROM 프로젝트").fetchall()
    assert len(프로젝트들) == 1
    assert 프로젝트들[0][1:] == ("가나전자 · AI 도입", 5, None)
    묶인 = conn.execute("SELECT 제목 FROM 대화 WHERE 프로젝트_id = ? ORDER BY 제목", (프로젝트들[0][0],)).fetchall()
    assert [r[0] for r in 묶인] == ["a", "b"]
    assert conn.execute("SELECT 프로젝트_id FROM 대화 WHERE 제목 = 'c'").fetchone()[0] is None
    conn.close()
