"""Normalize supported casting records while retaining the exact input tokens.

Primary source: 卜筮正术, DOCX body anchors in review_work/卜筮正术.txt:
B0304–B0305: recognize the 2/3 symbols; permutations share one four-state
meaning. No sum-to-6/7/8/9 conversion is used.
B0371–B0372: circle is 乾; square is 坤.
B0390 and B0430–B0433: 1震2兑3坎4艮5离6巽; lower trigram first,
upper second, moving position third.
B0461–B0462: square on the third draw is all static, circle all moving.

The sequence within a taiji token is retained as raw user input only. It has
no spatial meaning here and is never used to compute 六峜.
"""
from __future__ import annotations

from copy import deepcopy

SOURCE_ID = "SRC-BSZS"
SOURCE_RULES = {"meibu": "casting.meibu_conversion", "taiji": "casting.taiji_conversion"}
SOURCE_ANCHORS = {
    "taiji": ["B0304", "B0305"],
    "meibu": ["B0371", "B0372", "B0390", "B0430", "B0431", "B0432", "B0433", "B0461", "B0462"],
}
MEIBU_TRIGRAMS = {
    "circle": (1, 1, 1), "square": (0, 0, 0),
    "1": (1, 0, 0), "2": (1, 1, 0), "3": (0, 1, 0),
    "4": (0, 0, 1), "5": (1, 0, 1), "6": (0, 1, 1),
}
TAIJI_FOUR_STATES = {
    "222": "old_yin", "223": "young_yang", "233": "young_yin", "333": "old_yang",
}


class CastingInputError(ValueError):
    """Validation failure using the application's path/code/message convention."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("；".join(error["message"] for error in errors))


def _error(path, code, message):
    return {"path": path, "code": code, "message": message}


def derive_casting_lines(casting):
    """Return six four-state strings, bottom to top; never mutate casting.

    This function validates the casting object only. Complete request validation
    is performed by normalize_casting_input or validate_input.
    """
    if not isinstance(casting, dict):
        raise CastingInputError([_error("$/casting", "CASTING_OBJECT_REQUIRED", "起卦记录须为包含method和results的对象。")])
    errors = [_error("$/casting/" + str(key), "UNEXPECTED_CASTING_FIELD", "起卦记录不接收此字段。")
              for key in casting if key not in {"method", "results"}]
    method = casting.get("method")
    if not isinstance(method, str) or method not in {"meibu", "taiji"}:
        errors.append(_error("$/casting/method", "INVALID_CASTING_METHOD", "起卦方式须为meibu或taiji；直接录入六爻时仅提供lines。"))
    results = casting.get("results")
    expected = 3 if method == "meibu" else 6 if method == "taiji" else None
    if not isinstance(results, list):
        errors.append(_error("$/casting/results", "CASTING_RESULTS_REQUIRED", "须按实际先后次序提供起卦结果数组。"))
    elif expected is not None:
        if len(results) != expected:
            errors.append(_error("$/casting/results", "CASTING_RESULT_COUNT", f"{('枚卜丸' if method == 'meibu' else '太极丸')}须提供{expected}次结果。"))
        for index, token in enumerate(results):
            valid = (isinstance(token, str) and token in MEIBU_TRIGRAMS) if method == "meibu" else (
                isinstance(token, str) and len(token) == 3 and all(symbol in "23" for symbol in token))
            if not valid:
                message = "枚卜结果须为circle、square或字符串1至6。" if method == "meibu" else "每次太极结果须为三个2或3组成的字符串，例如222、223、233、333；排列次序不改变四象。"
                errors.append(_error("$/casting/results/" + str(index), "INVALID_CASTING_RESULT", message))
    if errors:
        raise CastingInputError(errors)
    if method == "taiji":
        # Sorting recognizes the multiset of yin/yang symbols. The raw token is
        # retained unchanged in normalized input; no numeric addition is used.
        return [TAIJI_FOUR_STATES["".join(sorted(token))] for token in results]
    bits = MEIBU_TRIGRAMS[results[0]] + MEIBU_TRIGRAMS[results[1]]
    third = results[2]
    moving = set(range(1, 7)) if third == "circle" else set() if third == "square" else {int(third)}
    return [("old_yang" if bit else "old_yin") if position in moving else
            ("young_yang" if bit else "young_yin")
            for position, bit in enumerate(bits, start=1)]


def normalize_casting_input(value):
    """Validate and copy a complete client input, deriving lines if needed.

    Accepted: question + lines; question + casting; or both agreeing exactly.
    Optional actual_cast_time is kept as given. Invalid or disagreeing data
    raises CastingInputError; no correction, truncation, inference or mutation
    occurs. Storage callers must retain this returned object, so raw casting
    and the derived lines are present in both the original and revision inputs.
    """
    # Deferred import avoids a cycle: validate_input calls the pure conversion
    # helper above, while this public entry point also validates the whole form.
    from validate_input import validate_input

    checked = validate_input(value)
    if not checked["valid"]:
        raise CastingInputError(checked["errors"])
    normalized = deepcopy(value)
    if "casting" in normalized:
        normalized["lines"] = derive_casting_lines(normalized["casting"])
    return normalized
