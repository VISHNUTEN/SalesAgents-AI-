"""Step 7: API integration tests (TestClient, no LLM/voice)."""

from fastapi.testclient import TestClient

from app.api.dependencies import CALL_SESSIONS
from app.main import app

client = TestClient(app)


def _new_call(name="Rahul"):
    CALL_SESSIONS.clear()
    r = client.post("/api/calls", json={"customer_name": name})
    assert r.status_code == 201, r.text
    call_id = r.json()["call_id"]
    s = client.post(f"/api/calls/{call_id}/start")
    assert s.status_code == 200, s.text
    return call_id


def _msg(call_id, message, extracted=None):
    payload = {"message": message}
    if extracted is not None:
        payload["extracted"] = extracted
    return client.post(f"/api/calls/{call_id}/message", json=payload)


def test_create_call():
    CALL_SESSIONS.clear()
    r = client.post("/api/calls", json={"customer_name": "Rahul"})
    assert r.status_code == 201
    body = r.json()
    assert body["call_id"] and body["status"] == "initiated"


def test_start_call():
    call_id = _new_call()
    detail = client.get(f"/api/calls/{call_id}").json()
    assert detail["status"] == "in_progress"
    assert len(detail["conversation_history"]) == 1


def test_customer_verify_response():
    call_id = _new_call()
    r = _msg(call_id, "Yes, this is Rahul.")
    assert r.status_code == 200
    assert r.json()["stage"] == "offer"
    detail = client.get(f"/api/calls/{call_id}").json()
    assert len(detail["conversation_history"]) == 3  # greet + user + assistant


def test_unknown_call_404():
    assert client.get("/api/calls/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.post("/api/calls/00000000-0000-0000-0000-000000000000/message", json={"message": "hi"}).status_code == 404


def test_completed_call_rejected():
    call_id = _new_call()
    _msg(call_id, "No, wrong number.")
    r = _msg(call_id, "Hello again?")
    assert r.status_code == 409


def test_qualification_state_endpoint():
    call_id = _new_call()
    _msg(call_id, "Yes, this is Rahul.")
    _msg(call_id, "Yes, tell me more.", {"property_type": "residential"})
    q = client.get(f"/api/calls/{call_id}/qualification")
    assert q.status_code == 200
    assert q.json()["property_type"] == "residential"
    assert q.json()["tenure"] is None


def test_agent_config():
    r = client.get("/api/agent/config")
    assert r.status_code == 200
    body = r.json()
    assert body["agent_name"] and body["company_name"]


def _to_qualification(call_id):
    _msg(call_id, "Yes, this is Rahul.")
    _msg(call_id, "Yes, tell me more.")
    steps = [
        ("Residential building.", {"property_type": "residential"}),
        ("Jointly owned.", {"ownership_status": "joint"}),
        ("Originals available.", {"documents_available": True}),
        ("50 lakhs.", {"loan_amount": 5000000}),
        ("Salaried, bank.", {"occupation": "salaried", "income_mode": "bank"}),
        ("One crore.", {"market_value": 10000000}),
        ("Ten years.", {"tenure": 10}),
    ]
    last = None
    for text, ext in steps:
        last = _msg(call_id, text, ext)
        assert last.status_code == 200, last.text
    return last


def test_happy_path_qualified():
    call_id = _new_call()
    last = _to_qualification(call_id)
    assert last.json()["action"] == "qualify"
    assert last.json()["end_call"] is True
    detail = client.get(f"/api/calls/{call_id}").json()
    assert detail["status"] == "completed"


def test_agricultural_disqualified():
    call_id = _new_call()
    _msg(call_id, "Yes, this is Rahul.")
    _msg(call_id, "Yes.")
    r = _msg(call_id, "Agricultural land.", {"property_type": "agricultural"})
    assert r.json()["action"] == "disqualify"


def test_cash_income_disqualified():
    call_id = _new_call()
    _msg(call_id, "Yes, this is Rahul.")
    _msg(call_id, "Yes.")
    r = _msg(call_id, "Cash income.", {"income_mode": "cash"})
    assert r.json()["action"] == "disqualify"


def test_missing_docs_disqualified():
    call_id = _new_call()
    _msg(call_id, "Yes, this is Rahul.")
    _msg(call_id, "Yes.")
    r = _msg(call_id, "Only photocopies.", {"documents_available": False})
    assert r.json()["action"] == "disqualify"


def test_invalid_tenure_disqualified():
    call_id = _new_call()
    _msg(call_id, "Yes, this is Rahul.")
    _msg(call_id, "Yes.")
    r = _msg(call_id, "2 years.", {"tenure": 2})
    assert r.json()["action"] == "disqualify"


def test_existing_loan_transferred():
    call_id = _new_call()
    _msg(call_id, "Yes, this is Rahul.")
    _msg(call_id, "Yes.")
    r = _msg(call_id, "I already have a property loan on this.")
    assert r.json()["action"] == "transfer"
    assert r.json()["transfer_required"] is True


def test_emi_reduction_transferred():
    call_id = _new_call()
    _msg(call_id, "Yes, this is Rahul.")
    _msg(call_id, "Yes.")
    r = _msg(call_id, "I want to reduce my existing EMI.")
    assert r.json()["action"] == "transfer"


def test_loan_above_max_accept_and_reject():
    call_id = _new_call()
    _msg(call_id, "Yes, this is Rahul.")
    _msg(call_id, "Yes.")
    asked = _msg(call_id, "I need 90 lakhs.", {"loan_amount": 9000000})
    assert "75" in asked.json()["message"]
    accepted = _msg(call_id, "Yes, 75 is fine.")
    assert accepted.json()["action"] == "ask_question"

    call_id2 = _new_call()
    _msg(call_id2, "Yes, this is Rahul.")
    _msg(call_id2, "Yes.")
    _msg(call_id2, "I need 90 lakhs.", {"loan_amount": 9000000})
    rejected = _msg(call_id2, "No, I need 90 only.")
    assert rejected.json()["end_call"] is True
