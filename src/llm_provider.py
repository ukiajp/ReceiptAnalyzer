import json
import logging
import re
import time

from config import Config


logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = "あなたはレシート・領収書のOCRテキストを構造化JSONに変換する専門家です。"
_SCHEMA_INSTRUCTION = """以下のJSON構造で出力してください。
- schema_version: '1.0.0'
- status: 'success'/'partial'/'failed'
- document.document_type: 'receipt'/'invoice'
- document.partner_name: 取引先名（必須）
- document.date: 'YYYY-MM-DD'（必須）
- document.total: 整数（必須）
- document.tax.rate_10: {base: int, amount: int}
- document.tax.rate_8: {base: int, amount: int}
- document.payment_method: 任意
- document.inferred.account_title: 勘定科目（コンテキストから推定）
- document.inferred.account_source: 'csv_history'/'mf_api'/'rule'/'default'
- document.confidence: {total: float, date: float, partner_name: float}
- document.validation.tax_sum_matches_total: boolean"""
_ANTHROPIC_MODEL = "claude-3-5-sonnet-20241022"
_OPENAI_MODEL = "gpt-4o-mini"
_GEMINI_MODEL = "gemini-2.0-flash"
_REQUEST_TIMEOUT = 60.0


def call_llm(ocr_text: str, context: str) -> tuple[str, float]:
    start_time = time.perf_counter()
    engine = Config.LLM_ENGINE.strip().lower()
    user_prompt = _build_user_prompt(ocr_text=ocr_text, context=context)

    try:
        if engine == "claude":
            raw_text = _call_anthropic(user_prompt)
        elif engine == "openai":
            raw_text = _call_openai(user_prompt)
        elif engine == "gemini":
            raw_text = _call_gemini(user_prompt)
        else:
            raise Exception(f"Unsupported LLM_ENGINE: {Config.LLM_ENGINE}")

        json_text = _extract_json_text(raw_text)
        elapsed = time.perf_counter() - start_time
        logger.info("LLM completed with engine=%s in %.2f seconds", engine, elapsed)
        return json_text, elapsed
    except Exception as exc:
        logger.error("LLM call failed with engine=%s: %s", engine, exc, exc_info=True)
        raise Exception(str(exc)) from exc


def _build_user_prompt(ocr_text: str, context: str) -> str:
    return (
        f"{context}\n\n---\n\n"
        "以下のOCRテキストから正本JSONを生成してください。\n\n"
        f"{ocr_text}\n\n"
        f"出力形式:\n{_SCHEMA_INSTRUCTION}"
    )


def _call_anthropic(user_prompt: str) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=Config.ANTHROPIC_API_KEY, timeout=_REQUEST_TIMEOUT)
    response = client.messages.create(
        model=_ANTHROPIC_MODEL,
        max_tokens=1000,
        temperature=0.1,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    parts: list[str] = []
    for block in response.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)

    if not parts:
        raise Exception("Anthropic response did not contain text content")

    return "\n".join(parts).strip()


def _call_openai(user_prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=Config.OPENAI_API_KEY, timeout=_REQUEST_TIMEOUT)
    response = client.chat.completions.create(
        model=_OPENAI_MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    message = response.choices[0].message
    content = message.content

    if isinstance(content, str) and content.strip():
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                item_type = item.get("type")
                text = item.get("text")
            else:
                item_type = getattr(item, "type", None)
                text = getattr(item, "text", None)

            if item_type == "text" and text:
                parts.append(str(text))
        if parts:
            return "\n".join(parts).strip()

    raise Exception("OpenAI response did not contain text content")


def _call_gemini(user_prompt: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=Config.GEMINI_API_KEY)
    model = genai.GenerativeModel(_GEMINI_MODEL, system_instruction=_SYSTEM_PROMPT)
    response = model.generate_content(user_prompt)
    if not response.candidates:
        raise Exception('Gemini response blocked or empty (no candidates)')
    candidate = response.candidates[0]
    if not candidate.content or not candidate.content.parts:
        raise Exception(f'Gemini response blocked. finish_reason={candidate.finish_reason}')
    text = response.text.strip()
    if not text:
        raise Exception('Gemini response was empty')
    return text


def _extract_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced_match:
        text = fenced_match.group(1).strip()

    start = text.find("{")
    if start == -1:
        raise Exception("LLM response did not contain a JSON object")

    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : index + 1].strip()
                json.loads(candidate)
                return candidate

    raise Exception("Failed to extract valid JSON from LLM response")
