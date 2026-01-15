"""JSON extraction and parsing utilities for LLM output."""

import ast
import json
import re
from typing import Optional, Dict, Any, List

from ..core.exceptions import LLMOutputParseError


_ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _normalize_llm_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\ufeff", "")
    text = _ANSI_ESCAPE_RE.sub("", text)
    text = _CONTROL_CHARS_RE.sub("", text)
    text = _strip_common_line_prefix(text)
    return text.strip()


def _strip_common_line_prefix(text: str) -> str:
    lines = text.splitlines()
    non_empty = [line for line in lines if line.strip()]
    if not non_empty:
        return text
    prefixes = ("| ", "│ ", "> ", "» ")
    for prefix in prefixes:
        if all(line.lstrip().startswith(prefix) for line in non_empty):
            stripped_lines = []
            for line in lines:
                if not line.strip():
                    stripped_lines.append(line)
                    continue
                line_stripped = line.lstrip()
                stripped_lines.append(line_stripped[len(prefix):])
            return "\n".join(stripped_lines)
    return text


def _try_parse_candidate(candidate: str) -> Optional[Any]:
    if not candidate:
        return None
    candidate = candidate.strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    try:
        parsed = ast.literal_eval(candidate)
    except (ValueError, SyntaxError):
        return None
    if isinstance(parsed, (dict, list)):
        return parsed
    return None


def extract_json(text: str) -> Optional[Any]:
    """
    Extract JSON from LLM output that may contain surrounding text.
    Handles cases where LLM adds explanation before/after JSON.
    """
    text = _normalize_llm_text(text)

    # First, try direct parsing
    direct = _try_parse_candidate(text)
    if direct is not None:
        return direct

    # Try to find JSON in code fences
    patterns = [
        r'```json\s*([\s\S]*?)\s*```',  # JSON code fence
        r'```\s*([\s\S]*?)\s*```',       # Generic code fence
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            parsed = _try_parse_candidate(match)
            if parsed is not None:
                return parsed

    # Try to find raw JSON objects
    for candidate in _balanced_candidates(text, '{', '}'):
        parsed = _try_parse_candidate(candidate)
        if parsed is not None:
            return parsed

    return None


def parse_questions_json(text: str) -> Dict[str, Any]:
    """
    Parse questions JSON from LLM output.
    Raises LLMOutputParseError if parsing fails.

    Expected format:
    {
        "questions": [
            {"id": "q1", "question": "...", "options": ["A", "B", "C"]}
        ]
    }
    """
    result = extract_json(text)
    if result is None:
        array_result = extract_json_array(text)
        if array_result is not None:
            result = {"questions": array_result}

    if result is None:
        raise LLMOutputParseError(f"No valid JSON found in output: {text[:500]}...")

    if isinstance(result, dict) and "questions" not in result:
        nested = _extract_nested_json(result)
        if nested is not None:
            result = nested

    if isinstance(result, list):
        result = {"questions": result}

    if not isinstance(result, dict):
        raise LLMOutputParseError("JSON must be an object")

    if "questions" not in result:
        raise LLMOutputParseError("JSON missing 'questions' key")

    questions = result["questions"]
    if isinstance(questions, dict):
        questions = [
            {"id": key, **value} if isinstance(value, dict) else {"id": key, "question": str(value)}
            for key, value in questions.items()
        ]
    if not isinstance(questions, list):
        raise LLMOutputParseError("'questions' must be a list")

    # Validate question structure
    normalized_questions = []
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            raise LLMOutputParseError(f"Question {i} is not an object")

        q_id = q.get("id") or f"q{i + 1}"
        q_text = q.get("question") or q.get("text") or q.get("prompt")
        if not q_text:
            raise LLMOutputParseError(f"Question {i} missing 'question'")

        options = q.get("options")
        if options is None:
            options = q.get("choices") or q.get("answers")

        options_list = _normalize_options(options)
        if len(options_list) < 2:
            raise LLMOutputParseError(f"Question {i} must have at least 2 options")

        normalized_questions.append({
            "id": str(q_id).strip(),
            "question": str(q_text).strip(),
            "options": options_list,
        })

    result["questions"] = normalized_questions
    return result


def extract_json_array(text: str) -> Optional[List[Any]]:
    """
    Extract a JSON array from LLM output.
    """
    text = _normalize_llm_text(text)

    # First, try direct parsing
    direct = _try_parse_candidate(text)
    if isinstance(direct, list):
        return direct

    # Try to find array in code fences
    patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            parsed = _try_parse_candidate(match)
            if isinstance(parsed, list):
                return parsed

    # Try to find raw arrays
    for candidate in _balanced_candidates(text, '[', ']'):
        parsed = _try_parse_candidate(candidate)
        if isinstance(parsed, list):
            return parsed

    return None


def safe_json_loads(text: str, default: Any = None) -> Any:
    """
    Safely parse JSON, returning default on failure.
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def format_json_for_prompt(data: Any) -> str:
    """
    Format data as compact JSON for inclusion in prompts.
    """
    return json.dumps(data, separators=(',', ':'))


def format_json_pretty(data: Any) -> str:
    """
    Format data as pretty-printed JSON for display.
    """
    return json.dumps(data, indent=2)


def _normalize_options(options: Any) -> List[str]:
    if options is None:
        return []
    if isinstance(options, list):
        return [str(option).strip() for option in options if str(option).strip()]
    if isinstance(options, dict):
        return [str(option).strip() for option in options.values() if str(option).strip()]
    if isinstance(options, str):
        stripped = options.strip()
        parsed = _try_parse_candidate(stripped)
        if isinstance(parsed, list):
            return [str(option).strip() for option in parsed if str(option).strip()]
        parts = re.split(r"[,\n\r|/;]", stripped)
        return [part.strip() for part in parts if part.strip()]
    return []


def _balanced_candidates(text: str, open_char: str, close_char: str) -> List[str]:
    candidates = []
    depth = 0
    start_idx = None
    for i, char in enumerate(text):
        if char == open_char:
            if depth == 0:
                start_idx = i
            depth += 1
        elif char == close_char and depth > 0:
            depth -= 1
            if depth == 0 and start_idx is not None:
                candidates.append(text[start_idx:i + 1])
                start_idx = None
    return candidates


def _extract_nested_json(data: Any) -> Optional[Any]:
    if isinstance(data, str):
        parsed = extract_json(data)
        if parsed is not None:
            return parsed
        array_parsed = extract_json_array(data)
        if array_parsed is not None:
            return array_parsed
        return None
    if isinstance(data, dict):
        for value in data.values():
            nested = _extract_nested_json(value)
            if nested is not None:
                return nested
        return None
    if isinstance(data, list):
        for value in data:
            nested = _extract_nested_json(value)
            if nested is not None:
                return nested
        return None
    return None
