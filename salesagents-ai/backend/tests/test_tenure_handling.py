"""Tenure extraction + invalid-tenure disqualification tests (no LLM)."""

from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.dependencies import CALL_SESSIONS
from app.main import app
from app.models.qualification import QualificationState
from app.services import eligibility_service, response_extractor
from app.services.eligibility_service import EligibilityStatus

extract = response_extractor.extract


def test_valid_tenure_variants():
    for text, expected in [
        ("3", 3), ("3 years", 3), ("10", 10), ("10 years", 10),
        ("10 year", 10), ("10 yrs", 10), ("10 yr", 10),
        ("I want 10 years", 10), ("I'd prefer 10 years", 10),
        ("around 10 years", 10), ("10 years would be fine", 10),
        ("I want a 10 year tenure", 10), ("5", 5), ("7", 7),
        ("8", 8), ("12", 12), ("15", 15), ("15 years", 15),
    ]:
        assert extract(text, prefer="tenure").get("tenure") == expected, text


def test_word_number_tenure():
    assert extract("ten years", prefer="tenure")["tenure"] == 10
    assert extract("ten", prefer="tenure")["tenure"] == 10
    assert extract("three years", prefer="tenure")["tenure"] == 3
    assert extract("fifteen years", prefer="tenure")["tenure"] == 15


def test_invalid_tenure_disqualifies():
    for text, expected in [
        ("1", 1), ("2", 2), ("2 years", 2), ("16", 16),
        ("16 years", 16), ("19", 19), ("19 years", 19),
        ("20 years", 20), ("17", 17),
    ]:
        out = extract(text, prefer="tenure")
        assert out.get("tenure") == expected, text
        result = eligibility_service.evaluate(QualificationState(**out))
        assert result.status == EligibilityStatus.DISQUALIFIED, text
        assert result.disqualified is True


def test_boundary_tenure_valid():
    for text in ["3", "3 years", "15", "15 years"]:
        out = extract(text, prefer="tenure")
        assert out.get("tenure") in (3, 15), text
        result = eligibility_service.evaluate(
            QualificationState(
                property_type="residential", ownership_status="sole",
                documents_available=True, loan_amount=Decimal("5000000"),
                occupation="salaried", income_mode="bank",
                market_value=Decimal("10000000"), **out,
            )
        )
        assert result.status == EligibilityStatus.QUALIFIED, text


def test_unclear_tenure_stays_none():
    assert "tenure" not in extract("I don't know", prefer="tenure")
    assert "tenure" not in extract("not sure", prefer="tenure")


def test_bare_number_not_tenure_at_market_question():
    out = extract("10", prefer="market_value")
    assert "tenure" not in out


def test_multi_tenure_plus_market():
    out = extract("I'd like 10 years and the property is worth around 1 crore.")
    assert out["tenure"] == 10
    assert out["market_value"] == Decimal("10000000")


client = TestClient(app)


def _call_at_tenure_question():
    CALL_SESSIONS.clear()
    call_id = client.post("/api/calls", json={"customer_name": "Rahul"}).json()["call_id"]
    client.post(f"/api/calls/{call_id}/start")
    client.post(f"/api/calls/{call_id}/message", json={"message": "Yes, this is Rahul."})
    client.post(f"/api/calls/{call_id}/message", json={"message": "Yes."})
    structured = {
        "property_type": "residential", "ownership_status": "sole",
        "documents_available": True, "loan_amount": 5000000,
        "occupation": "salaried", "income_mode": "bank",
        "market_value": 10000000,
    }
    r = client.post(f"/api/calls/{call_id}/message", json={"message": "details", "extracted": structured})
    assert r.json()["next_question"] == "tenure", r.json()
    return call_id


def test_api_bare_tenure_collected_once():
    call_id = _call_at_tenure_question()
    body = client.post(f"/api/calls/{call_id}/message", json={"message": "10"}).json()
    assert body["action"] == "qualify", body
    q = client.get(f"/api/calls/{call_id}/qualification").json()
    assert q["tenure"] == 10


def test_api_invalid_tenure_disqualifies_immediately():
    for answer in ["19", "19 years", "2", "16 years"]:
        call_id = _call_at_tenure_question()
        body = client.post(f"/api/calls/{call_id}/message", json={"message": answer}).json()
        assert body["action"] == "disqualify", (answer, body)
        assert body["end_call"] is True
        assert "tenure" not in (body.get("next_question") or "")
        detail = client.get(f"/api/calls/{call_id}").json()
        assert detail["status"] == "disqualified", (answer, detail)
        assert detail["qualification"]["tenure"] == int(answer.split()[0])
        assert "3 and 15" in body["message"] or "3 to 15" in body["message"] or "tenure" in body["message"].lower()


def test_api_full_happy_path_spec():
    CALL_SESSIONS.clear()
    call_id = client.post("/api/calls", json={"customer_name": "Rahul"}).json()["call_id"]
    client.post(f"/api/calls/{call_id}/start")
    client.post(f"/api/calls/{call_id}/message", json={"message": "Yes, this is Rahul."})
    client.post(f"/api/calls/{call_id}/message", json={"message": "Yes."})
    for text in ["residential", "sole owner", "yes I have originals",
                 "75 lakh", "self employed, income in bank", "around 1 cr", "10"]:
        r = client.post(f"/api/calls/{call_id}/message", json={"message": text})
        assert r.status_code == 200, (text, r.text)
    last = r.json()
    assert last["action"] == "qualify", last
    q = client.get(f"/api/calls/{call_id}/qualification").json()
    assert q["property_type"] == "residential"
    assert q["ownership_status"] == "sole"
    assert q["documents_available"] is True
    assert Decimal(str(q["loan_amount"])) == Decimal("7500000")
    assert q["occupation"] == "self_employed"
    assert q["income_mode"] == "bank"
    assert Decimal(str(q["market_value"])) == Decimal("10000000")
    assert q["tenure"] == 10
