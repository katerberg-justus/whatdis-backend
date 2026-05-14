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
You are a 20-questions host.
The secret: "{subject}".
Judge the player's latest message.
response_code values:
0=wrong,
1=correct,
2=not sure/irrelevant,
3=not answerable with yes or no,
4=player named the secret exactly,
5=possible,
6=not likely
"""


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


def judge_guess(subject: str, content: str, prior_guesses: list[dict]) -> int:
    """Call OpenAI and return a response_code integer."""
    messages = [{"role": "system", "content": _SYSTEM.format(subject=subject)}]
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
    if getattr(message, "refusal", None):
        return REFUSAL

    try:
        response_code = json.loads(message.content)["response_code"]
    except (TypeError, KeyError, json.JSONDecodeError):
        return NO

    return response_code if response_code in _VALID_RESPONSE_CODES else NO
