import os
import psycopg2
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from pydantic import BaseModel
from datetime import date
import anthropic

load_dotenv()

client = anthropic.Anthropic()


class PaymentCreate(BaseModel):
    amount: float
    payment_date: date
    method: str


class InvoiceCreate(BaseModel):
    customer_name: str
    issue_date: date
    due_date: date
    total_amount: float
    payments: list[PaymentCreate] = []


class InvoiceRawCreate(BaseModel):
    description: str


tools = [
    {
        "name": "extract_invoice_data",
        "description": "Extract the invoice data from a natural language description of an invoice.",
        "input_schema": InvoiceCreate.model_json_schema(),
    },
]


TOOL_MODELS = {
    "extract_invoice_data": InvoiceCreate,
}


def extract_invoice(description: str) -> InvoiceCreate:
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        tools=tools,
        tool_choice={"type": "tool", "name": "extract_invoice_data"},
        system="You are an invoice parser. Extract the invoice data from the natural language description of an invoice.",
        messages=[
            {"role": "user", "content": description},
        ],
    )

    tool_call = None
    for block in response.content:
        if block.type == "tool_use":
            tool_call = block

    if not tool_call:
        raise HTTPException(
            status_code=500, detail="LLM failed to extract invoice data"
        )

    try:
        return TOOL_MODELS[tool_call.name](**tool_call.input)
    except Exception as e:
        raise HTTPException(
            status_code=422, detail=f"Extraction validation failed: {str(e)}"
        )


def get_db():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


@asynccontextmanager
async def lifespan(app):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS invoices (
            id SERIAL PRIMARY KEY,
            customer_name TEXT NOT NULL,
            issue_date DATE NOT NULL,
            due_date DATE NOT NULL,
            total_amount FLOAT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS payments (
            id SERIAL PRIMARY KEY,
            invoice_id INTEGER REFERENCES invoices(id),
            amount FLOAT NOT NULL,
            payment_date DATE NOT NULL,
            method TEXT NOT NULL
        )
    """
    )
    conn.commit()
    cur.close()
    conn.close()
    yield


app = FastAPI(lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/invoices")
def create_invoice(invoice: InvoiceCreate):
    total_payments = 0

    for payment in invoice.payments:
        total_payments += payment.amount

    if total_payments > invoice.total_amount:
        raise HTTPException(
            status_code=400, detail="Total payments cannot exceed total amount"
        )

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO invoices (customer_name, issue_date, due_date, total_amount)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (
            invoice.customer_name,
            invoice.issue_date,
            invoice.due_date,
            invoice.total_amount,
        ),
    )

    row = cur.fetchone()
    invoice_id = row[0]

    for payment in invoice.payments:
        cur.execute(
            """
            INSERT INTO payments (invoice_id, amount, payment_date, method)
            VALUES (%s, %s, %s, %s)
            """,
            (
                invoice_id,
                payment.amount,
                payment.payment_date,
                payment.method,
            ),
        )

    conn.commit()
    cur.close()
    conn.close()

    return get_invoice(invoice_id)


@app.get("/invoices/{id}")
def get_invoice(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, customer_name, issue_date, due_date, total_amount FROM invoices WHERE id = %s
        """,
        (id,),
    )
    invoice = cur.fetchone()

    if not invoice:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Invoice not found")

    cur.execute(
        """
        SELECT id, amount, payment_date, method FROM payments WHERE invoice_id = %s
        """,
        (id,),
    )
    payments = cur.fetchall()

    balance_remaining = invoice[4] - sum(payment[1] for payment in payments)

    cur.close()
    conn.close()

    return {
        "id": invoice[0],
        "customer_name": invoice[1],
        "issue_date": str(invoice[2]),
        "due_date": str(invoice[3]),
        "total_amount": invoice[4],
        "balance_remaining": balance_remaining,
        "payments": [
            {
                "id": p[0],
                "amount": p[1],
                "payment_date": str(p[2]),
                "method": p[3],
            }
            for p in payments
        ],
    }


@app.post("/invoices/parse")
def parse_invoice(raw_invoice: InvoiceRawCreate):
    validated_result = extract_invoice(raw_invoice.description)
    return create_invoice(validated_result)


@app.post("/invoices/{id}/payments")
def add_payment(payment: PaymentCreate, id: int):
    invoice = get_invoice(id)

    if invoice["balance_remaining"] < payment.amount:
        raise HTTPException(
            status_code=400, detail="Payment amount exceeds balance remaining"
        )

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO payments (invoice_id, amount, payment_date, method)
        VALUES (%s, %s, %s, %s)
        """,
        (id, payment.amount, payment.payment_date, payment.method),
    )
    conn.commit()
    cur.close()
    conn.close()

    return get_invoice(id)


@app.get("/invoices")
def get_invoices():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM invoices")
    ids = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()

    return [get_invoice(id) for id in ids]
