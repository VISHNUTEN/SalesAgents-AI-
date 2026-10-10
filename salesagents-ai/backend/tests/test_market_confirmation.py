"""Market-value extraction + ₹75L confirmation tests (no LLM)."""

from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.dependencies import CALL_SESSIONS
from app.main import app
from app.services import response_extractor

extract = response_extractor.extract


def test_crore_variants():
    for text in [
        "1 cr", "1 crore", "1 crores", "1 cr.", "₹1 cr", "₹1 crore",
        "around 1 cr", "approximately 1 crore", "property is worth 1 cr",
        "market value is 1 crore",
    ]:
        out = extract(text, prefer="market_value")
        assert out.get("market_value") == Decimal("10000000"), text
        assert "loan_amount" not in out, text


def test_decimal_crore():
    assert extract("1.2 cr", prefer="market_value")["market_value"] == Decimal("12000000")
    assert extract("1.5 crore", prefer="market_value")["market_value"] == Decimal("15000000")
    assert extract("0.8 crore", prefer="market_value")["market_value"] == Decimal("8000000")
    assert extract("₹1.25 crore", prefer="market_value")["market_value"] == Decimal("12500000")


def test_lakh_variants():
    assert extract("50 lakh", prefer="market_value")["market_value"] == Decimal("5000000")
    assert extract("75 lakh", prefer="market_value")["market_value"] == Decimal("7500000")
    assert extract("80 lakhs", prefer="market_value")["market_value"] == Decimal("8000000")
    assert extract("50L", prefer="market_value")["market_value"] == Decimal("5000000")
    assert extract("75.5 lakh", prefer="market_value")["market_value"] == Decimal("7550000")
    assert extract("62.5L", prefer="market_value")["market_value"] == Decimal("6250000")


def test_plain_rupees_and_commas():
    assert extract("10000000", prefer="market_value")["market_value"] == Decimal("10000000")
    assert extract("₹10000000", prefer="market_value")["market_value"] == Decimal("10000000")
    assert extract("Rs 10000000", prefer="market_value")["market_value"] == Decimal("10000000")
    assert extract("1,00,00,000", prefer="market_value")["market_value"] == Decimal("10000000")


def test_loan_routing_unchanged():
    out = extract("50 lakh", prefer="loan_amount")
    assert out.get("loan_amount") == Decimal("5000000")
    assert "market_value" not in out
    # Default (no question context) still routes to loan.
    out = extract("I need 50 lakh")
    assert out.get("loan_amount") == Decimal("5000000")
    assert "market_value" not in out


def test_hedged_market_answers():
    for text in [
        "around 1 crore", "approximately 1 crore", "it is worth around 1 crore",
        "my property is worth 1 crore", "market value is around 1 crore",
        "I think it's about 1 crore", "roughly 80 lakh", "maybe 90 lakhs",
        "around 1.2 cr",
    ]:
        out = extract(text, prefer="market_value")
        assert "market_value" in out, text


def test_ambiguous_market_stays_none():
    for text in ["I don't know", "not sure", "no idea", "I can't estimate"]:
        out = extract(text, prefer="market_value")
        assert "market_value" not in out, text
        assert "loan_amount" not in out, text


def test_multi_market_plus_tenure():
    out = extract("The property is worth around 1 crore and I want a 10 year tenure.")
    assert out["market_value"] == Decimal("10000000")
    assert out["tenure"] == 10


def test_downgrade_accept_variants():
    for text in ["yes", "yeah", "yes, proceed", "sure", "okay", "okay, proceed",
                 "75 lakh is fine", "I'll proceed with 75 lakh", "sounds good", "go ahead"]:
        assert response_extractor.downgrade_answer(text) is True, text


def test_downgrade_decline_variants():
    for text in ["no", "no thanks", "no, thank you", "not interested",
                 "I don't want 75 lakh", "I don't want that", "that's too much",
                 "I don't want to proceed", "nope"]:
        assert response_extractor.downgrade_answer(text) is False, text


def test_downgrade_unclear_reasks():
    assert response_extractor.downgrade_answer("what are the charges?") is None
    assert response_extractor.downgrade_answer("maybe later") is None


client = TestClient(app)


def _call_at_market_question():
    CALL_SESSIONS.clear()
    call_id = client.post("/api/calls", json={"customer_name": "Rahul"}).json()["call_id"]
    client.post(f"/api/calls/{call_id}/start")
    client.post(f"/api/calls/{call_id}/message", json={"message": "Yes, this is Rahul."})
    client.post(f"/api/calls/{call_id}/message", json={"message": "Yes, tell me more."})
    structured = {
        "property_type": "residential", "ownership_status": "sole",
        "documents_available": True, "loan_amount": 5000000,
        "occupation": "salaried", "income_mode": "bank",
    }
    r = client.post(f"/api/calls/{call_id}/message", json={"message": "here are my details", "extracted": structured})
    assert r.json()["next_question"] == "market_value", r.json()
    return call_id


def test_api_market_value_then_tenure_once():
    call_id = _call_at_market_question()
    r = client.post(f"/api/calls/{call_id}/message", json={"message": "around 1 cr"})
    body = r.json()
    assert body["next_question"] == "tenure", body
    assert "market value" not in body["message"].lower()
    q = client.get(f"/api/calls/{call_id}/qualification").json()
    assert Decimal(str(q["market_value"])) == Decimal("10000000")
    r2 = client.post(f"/api/calls/{call_id}/message", json={"message": "10 years"}).json()
    assert r2["action"] == "qualify", r2


def test_api_downgrade_no_ends_call():
    for decline in ["no thanks", "I don't want 75 lakh", "not interested"]:
        CALL_SESSIONS.clear()
        call_id = client.post("/api/calls", json={"customer_name": "Rahul"}).json()["call_id"]
        client.post(f"/api/calls/{call_id}/start")
        client.post(f"/api/calls/{call_id}/message", json={"message": "Yes, this is Rahul."})
        client.post(f"/api/calls/{call_id}/message", json={"message": "Yes."})
        asked = client.post(f"/api/calls/{call_id}/message", json={"message": "I need 1 crore"}).json()
        assert "75" in asked["message"], asked
        ended = client.post(f"/api/calls/{call_id}/message", json={"message": decline}).json()
        assert ended["end_call"] is True, (decline, ended)
        detail = client.get(f"/api/calls/{call_id}").json()
        assert detail["status"] == "completed", (decline, detail)
        assert Decimal(str(detail["qualification"]["loan_amount"])) != Decimal("7500000")
        # No further questions after the call ends.
        again = client.post(f"/api/calls/{call_id}/message", json={"message": "hello?"})
        assert again.status_code == 409


def test_api_downgrade_yes_continues():
    CALL_SESSIONS.clear()
    call_id = client.post("/api/calls", json={"customer_name": "Rahul"}).json()["call_id"]
    client.post(f"/api/calls/{call_id}/start")
    client.post(f"/api/calls/{call_id}/message", json={"message": "Yes, this is Rahul."})
    client.post(f"/api/calls/{call_id}/message", json={"message": "Yes."})
    client.post(f"/api/calls/{call_id}/message", json={"message": "I need 1 crore"})
    accepted = client.post(f"/api/calls/{call_id}/message", json={"message": "75 lakh is fine"}).json()
    assert accepted["end_call"] is False, accepted
    assert accepted["next_question"] == "property_type", accepted
    q = client.get(f"/api/calls/{call_id}/qualification").json()
    assert Decimal(str(q["loan_amount"])) == Decimal("7500000")
