"""Step 6: prompt rendering tests."""

from app.services import prompt_service


def _vars(**overrides):
    base = dict(
        company_name="Home Credit",
        customer_name="Rahul Sharma",
        agent_name="Priya",
        agent_gender="female",
        current_date="2026-10-10",
        current_day="Saturday",
        current_time="12:00",
        additional_context_from_rag="LAP up to Rs. 75 lakh for existing customers.",
        language_to_speak="English",
        conversation_history="Agent: Hello\nCustomer: Hi",
        customer_utterance="I need 50 lakhs.",
    )
    base.update(overrides)
    return base


def test_all_variables_render():
    rendered = prompt_service.render_prompt(_vars())
    assert "{{" not in rendered and "}}" not in rendered


def test_customer_name_appears():
    assert "Rahul Sharma" in prompt_service.render_prompt(_vars())


def test_language_appears():
    assert "English" in prompt_service.render_prompt(_vars())


def test_history_inserted():
    assert "Agent: Hello" in prompt_service.render_prompt(_vars())


def test_utterance_inserted():
    assert "I need 50 lakhs." in prompt_service.render_prompt(_vars())


def test_rag_inserted():
    assert "LAP up to Rs. 75 lakh" in prompt_service.render_prompt(_vars())


def test_missing_rag_does_not_crash():
    vars_ = _vars()
    del vars_["additional_context_from_rag"]
    rendered = prompt_service.render_prompt(vars_)
    assert "{{additional_context_from_rag}}" not in rendered
