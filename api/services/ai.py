import os
from openai import OpenAI
from api.common.response_codes import NO, YES, INDECISIVE, REFUSAL, WIN, POSSIBLE, POSSIBLY_NOT

_client = None

_RC_MAP = {"CORRECT": YES, "INCORRECT": NO, "INDECISIVE": INDECISIVE, "REFUSAL": REFUSAL, "WIN": WIN, "POSSIBLE": POSSIBLE, "POSSIBLY_NOT": POSSIBLY_NOT}
_RC_MAP_DIGIT = {"1": YES, "2": NO, "3": INDECISIVE, "4": REFUSAL, "5": WIN, "6": POSSIBLE, "7": POSSIBLY_NOT}
_RC_MAP_INVERSE = {v: k for k, v in _RC_MAP.items()}

_SYSTEM = """
You are a 20-questions host.
The secret: "{subject}".
Answer the question with ONE digit only:
1=yes,
2=no,
3=not sure/irrelevant,
4=not a yes-or-no question,
5=player named secret exactly,
6=possible
7=not likely
"""


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


def judge_guess(subject: str, challenge_type: int, content: str, prior_guesses: list[dict]) -> int:
    """Call OpenAI and return a response_code integer (0–4)."""
    from api.common.challenge_enums import CHALLENGE_TYPE_LABEL

    messages = [{"role": "system", "content": _SYSTEM.format(subject=subject)}]
    for g in prior_guesses[-3:]:
        messages.append({"role": "user", "content": g["content"]})
        messages.append({"role": "assistant", "content": str(g["response_code"])})

    messages.append({"role": "user", "content": content})

    response = _get_client().chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-5.4-mini"),
        messages=messages,
        max_completion_tokens=5,
        reasoning_effort="none",
        temperature=0,
    )

    token = response.choices[0].message.content.strip().upper()
    print(token)
    return (
        _RC_MAP_DIGIT.get(token) or
        _RC_MAP.get(token) or
        next((_RC_MAP.get(v) for k, v in _RC_MAP.items() if token in k), None)
        or NO
    )
