"""
SOAP client + Flask wrapper for the public Number Conversion Service.

Service (from "Public SOAP Web Services for Interoperability Application"):
    WSDL: https://www.dataaccess.com/webservicesserver/NumberConversion.wso?WSDL

WSDL operations used:
    NumberToWords(ubiNum: xs:unsignedLong)  -> xs:string
    NumberToDollars(dNum: xs:decimal)        -> xs:string

What this program does:
    1. Reads the WSDL with zeep, which generates the client stub at runtime.
    2. Validates user input BEFORE calling the service (type + range checks).
    3. Calls the SOAP operation and turns the XML reply into a native Python
       object (the ConversionResult dataclass).
    4. Validates the returned "words" column (non-empty, only allowed characters).
    5. Raises custom errors and concatenates them with the underlying {exc}.
    6. Exposes everything through Flask with GET and POST endpoints.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000/ or use the curl commands in README.md.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import Flask, jsonify, render_template_string, request
from zeep import Client
from zeep.exceptions import Error as ZeepError
from zeep.exceptions import Fault

WSDL_URL = "https://www.dataaccess.com/webservicesserver/NumberConversion.wso?WSDL"

# ---- Validation rules ("value constraints") --------------------------------
WORDS_MIN, WORDS_MAX = 0, 1_000_000_000              # whole numbers only
DOLLARS_MIN, DOLLARS_MAX = Decimal("0.00"), Decimal("1000000.00")
MAX_DECIMAL_PLACES = 2                                # dollars and cents
ALLOWED_WORDS_PATTERN = re.compile(r"^[a-z\- ]+$")    # lowercase letters, spaces, hyphens


# ---- Custom exceptions -------------------------------------------------------
class ValidationError(Exception):
    """Input or returned data failed a validation rule."""


class ServiceError(Exception):
    """The SOAP service returned a fault or could not be reached."""


class ResponseValidationError(ValidationError):
    """The service replied, but the returned data failed validation."""


# ---- Native Python object for the XML reply ---------------------------------
@dataclass
class ConversionResult:
    operation: str
    input_value: str
    words: str
    retrieved_at: str


# ---- SOAP client --------------------------------------------------------------
_client: Client | None = None


def get_client() -> Client:
    """Create the zeep client once (downloads and parses the WSDL)."""
    global _client
    if _client is None:
        try:
            _client = Client(WSDL_URL)
        except Exception as exc:
            raise ServiceError(
                f"Custom error: could not load the WSDL from {WSDL_URL}. "
                f"Check your internet connection. Details: {exc}"
            ) from exc
    return _client


# ---- Input validation ---------------------------------------------------------
def validate_whole_number(raw) -> int:
    """Type check (integer) and range check (WORDS_MIN..WORDS_MAX)."""
    try:
        text = str(raw).strip()
        if not re.fullmatch(r"-?\d+", text):
            raise ValueError(f"'{raw}' is not a whole number")
        value = int(text)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f"Custom error: 'number' must be a whole number between "
            f"{WORDS_MIN:,} and {WORDS_MAX:,}. Details: {exc}"
        ) from exc

    if not WORDS_MIN <= value <= WORDS_MAX:
        raise ValidationError(
            f"Custom error: 'number' must be between {WORDS_MIN:,} and "
            f"{WORDS_MAX:,}. Details: received {value:,}"
        )
    return value


def validate_dollar_amount(raw) -> Decimal:
    """Type check (decimal), precision check (2 places), range check."""
    try:
        try:
            value = Decimal(str(raw).strip())
        except InvalidOperation:
            raise ValueError(f"'{raw}' is not a number") from None
        if not value.is_finite():
            raise InvalidOperation(f"'{raw}' is not a finite number")
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(
            f"Custom error: 'amount' must be a number such as 123.45. Details: {exc}"
        ) from exc

    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and -exponent > MAX_DECIMAL_PLACES:
        raise ValidationError(
            f"Custom error: 'amount' can have at most {MAX_DECIMAL_PLACES} "
            f"decimal places (dollars and cents). Details: received {raw}"
        )
    if not DOLLARS_MIN <= value <= DOLLARS_MAX:
        raise ValidationError(
            f"Custom error: 'amount' must be between {DOLLARS_MIN:,} and "
            f"{DOLLARS_MAX:,}. Details: received {value:,}"
        )
    return value


# ---- Output validation (the returned "words" column) ---------------------------
def validate_words(words, require: str | None = None) -> str:
    if not isinstance(words, str):
        raise ResponseValidationError(
            f"Custom error: service returned {type(words).__name__}, expected text. "
            f"Details: {words!r}"
        )
    cleaned = " ".join(words.split())  # service pads with trailing spaces
    if not cleaned:
        raise ResponseValidationError("Custom error: service returned an empty result.")
    if not ALLOWED_WORDS_PATTERN.fullmatch(cleaned):
        raise ResponseValidationError(
            "Custom error: service result contains unexpected characters "
            f"(only lowercase letters, spaces and hyphens allowed). Details: {cleaned!r}"
        )
    if require and require not in cleaned:
        raise ResponseValidationError(
            f"Custom error: expected the word '{require}' in the result. "
            f"Details: {cleaned!r}"
        )
    return cleaned


# ---- SOAP calls -----------------------------------------------------------------
def call_service(operation_name: str, **kwargs):
    client = get_client()
    try:
        operation = getattr(client.service, operation_name)
        return operation(**kwargs)
    except Fault as exc:
        raise ServiceError(
            f"Custom error: the SOAP service returned a fault for "
            f"{operation_name}. Details: {exc}"
        ) from exc
    except ZeepError as exc:
        raise ServiceError(
            f"Custom error: the SOAP request for {operation_name} failed. "
            f"Details: {exc}"
        ) from exc
    except Exception as exc:  # network problems, timeouts, etc.
        raise ServiceError(
            f"Custom error: could not reach the Number Conversion Service. "
            f"Details: {exc}"
        ) from exc


def number_to_words(raw) -> ConversionResult:
    value = validate_whole_number(raw)
    reply = call_service("NumberToWords", ubiNum=value)
    return ConversionResult(
        operation="NumberToWords",
        input_value=str(value),
        words=validate_words(reply),
        retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def number_to_dollars(raw) -> ConversionResult:
    value = validate_dollar_amount(raw)
    reply = call_service("NumberToDollars", dNum=value)
    return ConversionResult(
        operation="NumberToDollars",
        input_value=f"{value:.2f}",
        words=validate_words(reply, require="dollar"),
        retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


# ---- Flask app ----------------------------------------------------------------------
app = Flask(__name__)

FORM_PAGE = """
<!doctype html>
<title>Number Conversion SOAP Client</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 640px; margin: 2rem auto; }
  form { border: 1px solid #ccc; padding: 1rem; margin-bottom: 1rem; border-radius: 6px; }
  pre { background: #f4f4f4; padding: 1rem; white-space: pre-wrap; }
</style>
<h1>Number Conversion SOAP Client</h1>

<form method="get" action="/api/words">
  <h3>GET /api/words</h3>
  <label>Whole number ({{ wmin }} to {{ wmax }}):
    <input name="number" value="1234"></label>
  <button type="submit">Convert to words</button>
</form>

<form method="post" action="/api/dollars">
  <h3>POST /api/dollars</h3>
  <label>Amount ({{ dmin }} to {{ dmax }}, max 2 decimals):
    <input name="amount" value="1234.56"></label>
  <button type="submit">Convert to dollars</button>
</form>
"""


def error_response(exc: Exception):
    # 400 = bad user input; 502 = problem with the upstream SOAP service
    if isinstance(exc, ValidationError) and not isinstance(exc, ResponseValidationError):
        status = 400
    else:
        status = 502
    return jsonify({"status": "error", "error": str(exc)}), status


@app.get("/")
def index():
    return render_template_string(
        FORM_PAGE,
        wmin=f"{WORDS_MIN:,}", wmax=f"{WORDS_MAX:,}",
        dmin=f"{DOLLARS_MIN:,}", dmax=f"{DOLLARS_MAX:,}",
    )


@app.get("/api/words")
def words_endpoint():
    """GET /api/words?number=1234"""
    raw = request.args.get("number")
    if raw is None:
        return error_response(ValidationError(
            "Custom error: missing query parameter 'number'. "
            "Example: /api/words?number=1234"))
    try:
        result = number_to_words(raw)
    except (ValidationError, ServiceError) as exc:
        return error_response(exc)
    return jsonify({"status": "ok", "result": asdict(result)})


@app.post("/api/dollars")
def dollars_endpoint():
    """POST /api/dollars with JSON {"amount": 1234.56} or form field amount."""
    data = request.get_json(silent=True) or request.form
    raw = data.get("amount") if data else None
    if raw is None:
        return error_response(ValidationError(
            "Custom error: missing field 'amount'. "
            'Send JSON like {"amount": 1234.56}'))
    try:
        result = number_to_dollars(raw)
    except (ValidationError, ServiceError) as exc:
        return error_response(exc)
    return jsonify({"status": "ok", "result": asdict(result)})


if __name__ == "__main__":
    app.run(debug=True)
