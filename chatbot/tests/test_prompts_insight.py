"""
Sprint 10 — assert the Insight 5-step framework is present in the
Intelligence agent's system prompt.
"""
from chatbot.prompts import build_intelligence_prompt

REQUIRED_MARKERS = [
    "INSIGHT FRAMEWORK",
    "### Investment Position",
    "### Operating Performance",
    "### Key Strengths",
    "### Key Concerns",
    "### Verdict",
    "NKSquared should",
]


def test_insight_framework_present_read_only():
    prompt = build_intelligence_prompt(
        schema_context="(schema)", include_write_rules=False
    )
    for marker in REQUIRED_MARKERS:
        assert marker in prompt, f"missing {marker!r} in read-only prompt"


def test_insight_framework_present_with_write():
    prompt = build_intelligence_prompt(
        schema_context="(schema)", include_write_rules=True
    )
    for marker in REQUIRED_MARKERS:
        assert marker in prompt, f"missing {marker!r} in write-enabled prompt"


def test_insight_framework_appears_after_read_tool_rules():
    """
    Order matters for Azure prefix caching: framework must sit between
    read-tool rules and response format, not before tool rules.
    """
    prompt = build_intelligence_prompt(
        schema_context="(schema)", include_write_rules=False
    )
    tool_rules_idx = prompt.index("Tool Usage Guidelines")
    framework_idx = prompt.index("INSIGHT FRAMEWORK")
    response_idx = prompt.index("RESPONSE FORMAT")
    assert tool_rules_idx < framework_idx < response_idx
