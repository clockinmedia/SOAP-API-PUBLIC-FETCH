# Number Conversion SOAP Client (Flask)

Consumes the public **Number Conversion Service** WSDL:
`https://www.dataaccess.com/webservicesserver/NumberConversion.wso?WSDL`

## Setup

```bash
pip install -r requirements.txt
python app.py
```

The server runs at http://127.0.0.1:5000/. Open that page in a browser for a
simple GUI, or use curl.

## Endpoints

| Method | Path           | Input                          | SOAP operation   |
|--------|----------------|--------------------------------|------------------|
| GET    | `/`            | none (HTML test form)          | none             |
| GET    | `/api/words`   | query `number` (whole number)  | `NumberToWords`  |
| POST   | `/api/dollars` | JSON or form field `amount`    | `NumberToDollars`|

## Validation rules

| Field      | Type rule        | Value constraint                         |
|------------|------------------|------------------------------------------|
| `number`   | whole number     | 0 to 1,000,000,000                       |
| `amount`   | decimal          | 0.00 to 1,000,000.00, at most 2 decimals |
| `words` (returned) | text     | non-empty; lowercase letters, spaces, hyphens only; dollar results must contain "dollar" |

Each failure returns a custom message joined to the underlying exception
(`... Details: {exc}`). Validation errors return HTTP 400; SOAP faults and
network errors return HTTP 502.

## curl tests

Success cases:

```bash
curl "http://127.0.0.1:5000/api/words?number=1234"

curl -X POST http://127.0.0.1:5000/api/dollars \
     -H "Content-Type: application/json" \
     -d '{"amount": 1234.56}'
```

Validation failures:

```bash
curl "http://127.0.0.1:5000/api/words?number=abc"          # wrong type
curl "http://127.0.0.1:5000/api/words?number=5000000000"   # out of range
curl "http://127.0.0.1:5000/api/words?number=-7"           # below minimum

curl -X POST http://127.0.0.1:5000/api/dollars \
     -H "Content-Type: application/json" -d '{"amount": "12.345"}'   # too many decimals

curl -X POST http://127.0.0.1:5000/api/dollars \
     -H "Content-Type: application/json" -d '{"amount": "ten"}'      # wrong type
```

Windows PowerShell users: run `curl.exe` instead of `curl`, and escape JSON
quotes, for example `-d '{\"amount\": 1234.56}'`.
