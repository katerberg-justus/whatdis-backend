import json
import os
from openai import OpenAI
from api.common.response_codes import NO, YES, INDECISIVE, REFUSAL, WIN, POSSIBLE, POSSIBLY_NOT

_client = None

_VALID_RESPONSE_CODES = {NO, YES, INDECISIVE, REFUSAL, WIN, POSSIBLE, POSSIBLY_NOT}
_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "guess_judgement",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "response_code": {
                    "type": "integer",
                    "enum": sorted(_VALID_RESPONSE_CODES),
                },
            },
            "required": ["response_code"],
            "additionalProperties": False,
        },
    },
}

_SYSTEM = """
You are a decisive 20-questions host.

Return one response_code:
0 = no / wrong
1 = yes / correct
2 = unclear / irrelevant
3 = not answerable as yes/no
4 = player named the secret
5 = sometimes
6 = rarely true

Rules:
- Prefer 0 or 1 when the answer is clear.
- Use 5/6 only for real ambiguity, partial truth, or edge cases.
- Guesses may be in any language.

Secret: "{subject}"
{subject_hint_clause}
"""

_HINT_SYSTEM = (
    "You are a 20-questions host. Give ONE short sentence hinting at the secret "
    "without naming it or any obvious synonym. Be subtle; build on prior Q&A."
    "{lang_clause}{subject_hint_clause} "
    "Secret: \"{subject}\"."
)


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


def _subject_hint_clause(subject_hint: str | None) -> str:
    return f'\nPrivate clue: "{subject_hint}"' if subject_hint else ""


def judge_guess(
    subject: str,
    content: str,
    prior_guesses: list[dict],
    subject_hint: str | None = None,
) -> tuple[int, str]:
    """Call OpenAI and return (response_code, raw_model_content)."""
    messages = [
        {
            "role": "system",
            "content": _SYSTEM.format(
                subject=subject,
                subject_hint_clause=_subject_hint_clause(subject_hint),
            ),
        }
    ]
    for g in prior_guesses[-3:]:
        messages.append({"role": "user", "content": g["content"]})
        messages.append(
            {
                "role": "assistant",
                "content": json.dumps({"response_code": g["response_code"]}),
            }
        )

    messages.append({"role": "user", "content": content})

    response = _get_client().chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-5.4-mini"),
        messages=messages,
        response_format=_RESPONSE_FORMAT,
        max_completion_tokens=32,
        reasoning_effort="none",
        temperature=0,
    )

    message = response.choices[0].message
    raw = message.content or ""
    if getattr(message, "refusal", None):
        return REFUSAL, message.refusal or raw

    try:
        response_code = json.loads(raw)["response_code"]
    except (TypeError, KeyError, json.JSONDecodeError):
        return NO, raw

    return (response_code if response_code in _VALID_RESPONSE_CODES else NO), raw


def give_hint(
    subject: str,
    prior_guesses: list[dict],
    language: str | None = None,
    subject_hint: str | None = None,
) -> tuple[str, str]:
    """Generate a one-sentence hint. Returns (hint_text, raw_model_content)."""
    lang_clause = f" Respond in language code '{language}'." if language else ""
    messages = [
        {
            "role": "system",
            "content": _HINT_SYSTEM.format(
                subject=subject,
                lang_clause=lang_clause,
                subject_hint_clause=_subject_hint_clause(subject_hint),
            ),
        }
    ]
    for g in prior_guesses[-20:]:
        messages.append({"role": "user", "content": g["content"]})
        messages.append(
            {
                "role": "assistant",
                "content": json.dumps({"response_code": g["response_code"]}),
            }
        )
    messages.append({"role": "user", "content": "Give a hint."})

    response = _get_client().chat.completions.create(
        model=os.environ.get("OPENAI_HINT_MODEL", "gpt-5.2"),
        messages=messages,
        max_completion_tokens=40,
        temperature=0.7,
    )

    message = response.choices[0].message
    raw = message.content or ""
    if getattr(message, "refusal", None):
        return "", message.refusal or raw
    return raw.strip(), raw
