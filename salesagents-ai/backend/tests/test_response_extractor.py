"""Response extractor tests: natural text -> structured fields (no LLM)."""

from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.dependencies import CALL_SESSIONS
from app.main import app
from app.models.qualification import (
    IncomeMode,
    OccupationType,
    OwnershipStatus,
    PropertyType,
    QualificationState,
)
from app.services import eligibility_service, response_extractor
from app.services.eligibility_service import EligibilityStatus
from app.services.qualification_service import QualificationService

extract = response_extractor.extract


def test_house_is_residential():
    assert extract("house")["property_type"] == PropertyType.RESIDENTIAL
    assert extract("home")["property_type"] == PropertyType.RESIDENTIAL
    assert extract("residential")["property_type"] == PropertyType.RESIDENTIAL
    assert extract("residential property")["property_type"] == PropertyType.RESIDENTIAL


def test_commercial_building():
    assert extract("commercial building")["property_type"] == PropertyType.COMMERCIAL
    assert extract("shop")["property_type"] == PropertyType.COMMERCIAL


def test_factory_is_industrial():
    assert extract("factory")["property_type"] == PropertyType.INDUSTRIAL
    assert extract("industrial property")["property_type"] == PropertyType.INDUSTRIAL


def test_agricultural_land_disqualified():
    out = extract("agricultural land")
    assert out["property_type"] == PropertyType.AGRICULTURAL
    state = QualificationState(**out)
    result = eligibility_service.evaluate(state)
    assert result.status == EligibilityStatus.DISQUALIFIED
    assert result.disqualified is True


def test_bare_land_is_ambiguous():
    assert "property_type" not in extract("land")
    assert response_extractor.ambiguous_property("land") is True
    assert response_extractor.ambiguous_property("agricultural land") is False


def test_sole_owner():
    assert extract("I am the sole owner")["ownership_status"] == OwnershipStatus.SOLE


def test_jointly_owned():
    assert extract("it's jointly owned")["ownership_status"] == OwnershipStatus.JOINT
    assert extract("me and my wife own it")["ownership_status"] == OwnershipStatus.JOINT


def test_originals_available():
    assert extract("I have the original documents")["documents_available"] is True
    assert extract("yes, I have originals")["documents_available"] is True


def test_photocopies_disqualified():
    out = extract("I only have photocopies")
    assert out["documents_available"] is False
    result = eligibility_service.evaluate(QualificationState(**out))
    assert result.status == EligibilityStatus.DISQUALIFIED


def test_loan_amount_lakh():
    assert extract("50 lakh")["loan_amount"] == Decimal("5000000")
    assert extract("₹50 lakh")["loan_amount"] == Decimal("5000000")
    assert extract("5000000")["loan_amount"] == Decimal("5000000")


def test_one_crore_over_limit_pending():
    out = extract("1 crore")
    assert out["loan_amount"] == Decimal("10000000")
    result = eligibility_service.evaluate(QualificationState(**out))
    assert result.status == EligibilityStatus.PENDING
    assert result.disqualified is False


def test_salaried_bank():
    out = extract("I am salaried and my salary comes to my bank account")
    assert out["occupation"] == OccupationType.SALARIED
    assert out["income_mode"] == IncomeMode.BANK


def test_self_employed_cash_disqualified():
    out = extract("self employed, cash income")
    assert out["occupation"] == OccupationType.SELF_EMPLOYED
    assert out["income_mode"] == IncomeMode.CASH
    result = eligibility_service.evaluate(QualificationState(**out))
    assert result.status == EligibilityStatus.DISQUALIFIED


def test_market_value_no_minimum():
    out = extract("property is worth 1 crore")
    assert out["market_value"] == Decimal("10000000")
    assert "loan_amount" not in out


def test_tenure_years():
    assert extract("10 years")["tenure"] == 10
    assert extract("ten years")["tenure"] == 10


def test_multiple_fields_one_message():
    out = extract(
        "My property is a house, I am the sole owner, "
        "I have the original documents and I need 50 lakh."
    )
    assert out["property_type"] == PropertyType.RESIDENTIAL
    assert out["ownership_status"] == OwnershipStatus.SOLE
    assert out["documents_available"] is True
    assert out["loan_amount"] == Decimal("5000000")


def test_out_of_order_asks_earliest_missing():
    svc = QualificationService()
    state = svc.update_state(
        QualificationState(), extract("I am salaried and my income comes through the bank.")
    )
    assert state.occupation == OccupationType.SALARIED
    assert state.income_mode == IncomeMode.BANK
    assert svc.get_next_question(state) == "property_type"


def test_contradiction_latest_wins():
    assert extract("I am salaried, actually I run my own business")["occupation"] == OccupationType.SELF_EMPLOYED
    svc = QualificationService()
    state = svc.update_state(QualificationState(), {"occupation": OccupationType.SALARIED})
    state = svc.update_state(state, extract("I actually run my own business"))
    assert state.occupation == OccupationType.SELF_EMPLOYED


def test_full_happy_path_text_only():
    svc = QualificationService()
    state = QualificationState()
    for utterance in [
        "It's a house",
        "sole owner",
        "I have the original documents",
        "I need 40 lakh",
        "I am salaried, salary comes to bank",
        "worth 80 lakh",
        "10 years",
    ]:
        state = svc.update_state(state, extract(utterance))
    result = svc.evaluate(state)
    assert result.status == EligibilityStatus.QUALIFIED
    assert svc.get_next_question(state) is None


# --- API integration: text reaches state without explicit payloads ---

client = TestClient(app)


def _started_call():
    CALL_SESSIONS.clear()
    call_id = client.post("/api/calls", json={"customer_name": "Rahul"}).json()["call_id"]
    client.post(f"/api/calls/{call_id}/start")
    client.post(f"/api/calls/{call_id}/message", json={"message": "Yes, this is Rahul."})
    client.post(f"/api/calls/{call_id}/message", json={"message": "Yes, tell me more."})
    return call_id


def test_api_house_moves_to_ownership():
    call_id = _started_call()
    r = client.post(f"/api/calls/{call_id}/message", json={"message": "house"})
    body = r.json()
    assert body["next_question"] == "ownership_status", body
    assert "sole owner" in body["message"].lower() or "jointly" in body["message"].lower()
    q = client.get(f"/api/calls/{call_id}/qualification").json()
    assert q["property_type"] == "residential"


def test_api_bare_land_asks_clarification():
    call_id = _started_call()
    r = client.post(f"/api/calls/{call_id}/message", json={"message": "land"})
    body = r.json()
    assert body["next_question"] == "property_type"
    assert "residential" in body["message"] and "agricultural" in body["message"]
    q = client.get(f"/api/calls/{call_id}/qualification").json()
    assert q["property_type"] is None


def test_api_multi_slot_text_message():
    call_id = _started_call()
    body = client.post(
        f"/api/calls/{call_id}/message",
        json={"message": "house, I'm the sole owner and I have the original documents. I need 40 lakh."},
    ).json()
    assert body["next_question"] == "occupation", body
    q = client.get(f"/api/calls/{call_id}/qualification").json()
    assert q["property_type"] == "residential"
    assert q["ownership_status"] == "sole"
    assert q["documents_available"] is True
    assert Decimal(str(q["loan_amount"])) == Decimal("4000000")


# --- ownership extraction (bug fix) ---

def test_ownership_sole_variants():
    for text in [
        "solely owned",
        "Solely Owned",
        "sole",
        "sole owner",
        "sole ownership",
        "I am the sole owner",
        "I am the sole owner.",
        "I own it alone",
        "I am the only owner",
        "only owner",
        "owned by me",
        "it's only mine",
        "it's mine",
        "I own the property",
    ]:
        assert extract(text)["ownership_status"] == OwnershipStatus.SOLE, text


def test_ownership_joint_variants():
    for text in [
        "joint",
        "jointly owned",
        "joint ownership",
        "joint owner",
        "It's jointly owned by me and my wife.",
        "we own it together",
        "my wife and I own it",
        "my husband and I own it",
        "my brother and I own it",
        "owned by me and my wife",
        "owned by multiple people",
        "shared ownership",
    ]:
        assert extract(text)["ownership_status"] == OwnershipStatus.JOINT, text


def test_ownership_ambiguous_stays_none():
    assert "ownership_status" not in extract("I am involved with the property")
    assert "ownership_status" not in extract("tell me about loans")


def test_api_solely_owned_flow_to_loan_amount():
    call_id = _started_call()
    r1 = client.post(f"/api/calls/{call_id}/message", json={"message": "house"}).json()
    assert r1["next_question"] == "ownership_status", r1
    r2 = client.post(f"/api/calls/{call_id}/message", json={"message": "solely owned"}).json()
    assert r2["next_question"] == "documents_available", r2
    r3 = client.post(f"/api/calls/{call_id}/message", json={"message": "yes"}).json()
    assert r3["next_question"] == "loan_amount", r3
    q = client.get(f"/api/calls/{call_id}/qualification").json()
    assert q["property_type"] == "residential"
    assert q["ownership_status"] == "sole"
    assert q["documents_available"] is True
