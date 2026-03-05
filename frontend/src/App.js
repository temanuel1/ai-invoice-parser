import { useState, useEffect } from "react";
import "./App.css";

function App() {
  const [invoices, setInvoices] = useState([]);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState(null);

  useEffect(() => {
    fetch("http://localhost:8000/invoices")
      .then((res) => res.json())
      .then((data) => setInvoices(data));
  }, []);

  const isOpen = (id) => selectedInvoiceId === id;
  const toggle = (id) => setSelectedInvoiceId(isOpen(id) ? null : id);

  return (
    <div className="page">
      <div className="container">
        <div className="header">
          <h1>Invoices</h1>
          <span className="badge-count">{invoices.length} total</span>
        </div>

        {invoices.map((inv) => (
          <div
            key={inv.id}
            className={`invoice-card${isOpen(inv.id) ? " active" : ""}`}
          >
            <div className="card-header" onClick={() => toggle(inv.id)}>
              <div className="customer-info">
                <p className="customer-name">{inv.customer_name}</p>
                <p className="invoice-meta">
                  {inv.payments.length} payment
                  {inv.payments.length !== 1 && "s"}
                </p>
              </div>

              <div className="card-right">
                <div className="amount-total">
                  <p className="value">${inv.total_amount}</p>
                  <p className="label">Total</p>
                </div>

                <span
                  className={`balance-badge ${
                    inv.balance_remaining > 0 ? "outstanding" : "paid"
                  }`}
                >
                  {inv.balance_remaining > 0
                    ? `$${inv.balance_remaining} due`
                    : "Paid"}
                </span>

                <span className={`chevron${isOpen(inv.id) ? " open" : ""}`}>
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path
                      fillRule="evenodd"
                      d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                      clipRule="evenodd"
                    />
                  </svg>
                </span>
              </div>
            </div>

            {isOpen(inv.id) && (
              <div className="payments-panel">
                <p className="payments-title">Payment History</p>
                {inv.payments.length > 0 ? (
                  inv.payments.map((payment, index) => (
                    <div key={index} className="payment-row">
                      <div>
                        <p className="payment-amount">${payment.amount}</p>
                        <p className="payment-date">{payment.date}</p>
                      </div>
                      <span className="payment-status">Paid</span>
                    </div>
                  ))
                ) : (
                  <p className="empty-state">No payments recorded</p>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;
