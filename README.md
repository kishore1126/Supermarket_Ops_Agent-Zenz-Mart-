# Supermarket Ops Agent 🏪

> **Nebula KnowLab Take-Home Engineering Assignment**
> Run an entire Indian kirana store / supermarket from a Telegram chat window — with a reasoning agent, not a fixed command menu or web dashboard.

[![Tests](https://img.shields.io/badge/pytest-30%20passed-emerald)](#running-tests)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://www.postgresql.org/)
[![Harness](https://img.shields.io/badge/Agent_Harness-Claude_Agent_SDK-purple.svg)](https://anthropic.com/)
[![Interface](https://img.shields.io/badge/Interface-Telegram_Only-blue)](https://core.telegram.org/bots)

---

## 0. Executive Summary

This project implements an autonomous conversational operations agent for Indian kirana store owners. Operating 100% via Telegram, the agent understands informal, real-shopkeeper phrasing ("50 packets Maggi came in", "make a bill: 2kg sugar, 4 Maggi, UPI", "drop the butter", "put ₹500 on Ramesh's credit", "close the day"), reasons dynamically, queries grounded facts from PostgreSQL, executes deterministic business rules, and delivers pixel-perfect artifacts (GST PDF invoices and PowerPoint analysis decks).

**No web dashboard, no admin panel, no forms.** The conversational Telegram interface *is* the product.

---

## 1. Agent Harness & Architectural Choices

| Component | Choice | Rationale & Justification |
|---|---|---|
| **Language** | Python 3.11+ | Native async support, richest ecosystem for AI SDKs, PTB, ReportLab PDF, python-pptx, and async PostgreSQL. |
| **Agent Harness** | **Claude Agent SDK / Anthropic Tool-Use Loop** | Full Observe-Reason-Act multi-turn loop. Uses Pydantic v2 schemas for deterministic tool contracts and dynamic system prompt injection. |
| **Bot Framework** | `python-telegram-bot` (v21 async) | Native asynchronous polling/webhooks, non-blocking coroutines, rich MarkdownV2 formatting, and inline `Confirm / Cancel` keyboards. |
| **Database** | PostgreSQL + SQLAlchemy 2.0 (asyncpg) | True MVCC row-level locking (`SELECT ... FOR UPDATE`) required for concurrency oversell guards. |
| **Migrations** | Alembic | Trackable database schema versions. |
| **Validation** | Pydantic v2 & `pydantic-settings` | Strict input/output validation across all 16 agent tools. |
| **PDF Generation** | ReportLab | Pixel-perfect vector GST invoices with HSN breakup tables and paise round-off line. |
| **Presentation Deck**| `python-pptx` + `matplotlib` | 16:9 widescreen PowerPoint presentation with embedded high-resolution analytics charts. |
| **Data Analytics** | Pandas | High-speed sales aggregations for daily closing and weekly metrics. |

---

## 2. The Control Loop

The agent rejects rigid regex/keyword intent routers in favor of an **Observe → Reason → Act → Observe Result → Answer** loop:

```
Shopkeeper Message
       │
       ▼
[ Telegram Bot Handler ] ── (Checks `processed_updates` for Idempotency)
       │
       ▼
[ Dynamic System Prompt Builder ] ── (Injects `owner_preferences` from DB)
       │
       ▼
┌──────────────── Claude Agent Multi-Turn Loop ──────────────┐
│                                                            │
│  1. OBSERVE: Receive user intent & conversation history    │
│  2. REASON:  Claude model decides which tool(s) to call    │
│  3. ACT:     Execute registered tool handler via DB Session│
│  4. FEEDBACK:Pass structured tool JSON back to context     │
│  5. REPEAT:  Continue reasoning until `stop_reason == end` │
│                                                            │
└────────────────────────────────────────────────────────────┘
       │
       ▼
[ Telegram UI Formatter ] ── Monospace Tables + Inline Keyboards + Documents
```

---

## 3. How the 9 "Hard Parts" are Concretely Solved

### 1. Grounding
- **Rule**: The model *never* invents a product name, price, GST rate, or stock number.
- **Solution**: Every lookup goes through `check_stock` or `start_or_update_bill`. Tool outputs provide grounded facts directly from the database; system prompt explicitly forbids fabricating figures.

### 2. Oversell Guard
- **Rule**: Stock can never go negative. Billing 10 when only 6 are in stock must be refused at the tool layer.
- **Solution**: `finalize_bill` locks product rows (`SELECT ... FOR UPDATE`) inside a transaction and validates `product.stock_qty >= item.quantity`. If violated, it rolls back and raises `InsufficientStockError(product, requested, available)`.

### 3. GST Correctness & Explicit Round-Off Line
- **Rule**: Correct intra-state CGST + SGST (50/50 split), HSN codes, and legible tax breakup.
- **Pricing Model**: Standard Indian retail tax-inclusive MRP decomposition:
  $$\text{Taxable Base} = \frac{\text{Selling Price}}{1 + \text{GST Rate}}$$
  $$\text{Total GST} = \text{Selling Price} - \text{Taxable Base}$$
  $$\text{CGST} = \text{round}\left(\frac{\text{Total GST}}{2}, 2\right), \quad \text{SGST} = \text{Total GST} - \text{CGST}$$
- **Round-Off**: The invoice calculates an explicit `Round Off: ±₹0.xx` adjustment line reconciling the raw total to the nearest integer Rupee on both Telegram receipts and ReportLab PDF invoices.

### 4. Multi-Turn Bills
- **Rule**: A bill builds over several messages, supports mid-flight edits ("drop the butter, make it 6 Maggi"), and only touches stock on finalization.
- **Solution**: `start_or_update_bill` manages a mutable `DRAFT` bill row in PostgreSQL. Items are added, updated, or removed (quantity $\le 0$). Stock is strictly untouched until `finalize_bill`.

### 5. Idempotency & Double-Tap Protection
- **Rule**: Telegram update redeliveries or rapid button double-taps must not double-bill or duplicate stock decrements.
- **Two-Layer Solution**:
  1. **Update Deduplication**: Every Telegram `update_id` is recorded in `processed_updates`. Duplicate update IDs short-circuit immediately.
  2. **Row-Locked Status Verification**: Inside the finalize transaction, `bill.status == DRAFT` is verified under row lock. A second click sees `status == FINALIZED` and raises `BillAlreadyFinalizedError` without touching inventory.

### 6. True Concurrency & Row-Level Locking
- **Rule**: Two simultaneous finalize calls racing for limited stock must not corrupt inventory.
- **Solution**: `finalize_bill` executes `SELECT ... FOR UPDATE` row locks in PostgreSQL. Concurrent finalize transactions serialize cleanly.
- *Note on Testing*: Concurrency tests target PostgreSQL because SQLite lacks true MVCC row-level locking.

### 7. Domain Guardrails at Intake & Billing
- **Rule**: Don't sell below cost, don't delete stock, don't settle non-existent khata accounts.
- **Solution**: `add_product` and `receive_stock` validate `selling_price >= cost_price`. If violated, `BelowCostError` is raised unless `allow_below_cost=True` is explicitly confirmed. `record_payment` raises `CustomerNotFoundError` for unknown customers.

### 8. Real Artifacts (PDF & PPTX)
- **PDF Invoices**: Generated via ReportLab (`invoice_pdf.py`) with shop header, GSTIN, tabular items with HSN codes, CGST/SGST breakdown, Round-Off line, and authorized signatory.
- **PPTX Presentations**: Generated via `python-pptx` + `matplotlib` (`analysis_pptx.py`) with 5 widescreen slides (KPI Cards, Daily Revenue Line Chart, Top SKUs Bar Chart, Payment Mode Pie Chart, Low Stock Alerts).

### 9. Durable Memory Across Sessions
- **Rule**: Standing preferences (`default_payment_method`, `preferred_atta_brand`, `shop_name`, `shop_gstin`) persist across `/new` resets.
- **Solution**: Preferences live in the `owner_preferences` PostgreSQL table and are injected into the system prompt on every agent turn. The `/new` command only clears the Telegram in-memory conversational history.

---

## 4. Tool Surface (~16 Registered Tools)

| Tool Name | Input Schema Summary | Description |
|---|---|---|
| `check_stock` | `query: str?`, `product_id: int?` | Query stock level, selling price, MRP, and GST rate. |
| `get_low_stock` | *(none)* | List all SKUs at or below their reorder threshold. |
| `receive_stock` | `product_name: str`, `quantity: float`, `cost_price: float?`, `mrp: float?`, `selling_price: float?`, `allow_below_cost: bool` | Record incoming stock delivery with below-cost checks. |
| `add_product` | `name`, `unit`, `cost_price`, `selling_price`, `mrp`, `gst_rate`, `hsn_code`, `initial_stock`, `reorder_level`, `allow_below_cost` | Add a brand new SKU to the catalog with guardrails. |
| `start_or_update_bill` | `items: list`, `customer_name: str?`, `customer_phone: str?`, `payment_method: str?`, `bill_id: int?` | Start or mutate a multi-turn draft bill (add/edit/drop items). |
| `preview_bill` | `bill_id: int?` | Preview line items, tax breakdown, round-off, and grand total. |
| `finalize_bill` | `bill_id: int?`, `payment_method: str?`, `allow_below_cost: bool` | Atomically finalize bill, decrement stock via row locks. |
| `cancel_bill` | `bill_id: int?` | Cancel an open draft bill without touching stock. |
| `add_credit` | `customer_name: str`, `amount: float`, `note: str?`, `phone: str?` | Add debt to a customer's khata ledger account. |
| `record_payment` | `customer_name: str`, `amount: float`, `note: str?` | Record customer cash/UPI payment to settle balance. |
| `get_khata_balance` | `customer_name: str?` | Get customer balance & history or total store receivables. |
| `get_daily_close` | `date_str: str?` | Compute day's gross sales, tax collected, cash vs UPI, top items. |
| `get_sales_analysis` | `days: int = 7` | Multi-day sales trends, top SKUs by velocity, payment shares. |
| `generate_invoice_pdf` | `bill_id: int?` | Render and save official GST Tax Invoice PDF document. |
| `generate_analysis_deck` | `days: int = 7` | Generate 5-slide PowerPoint deck with Matplotlib charts. |
| `set_preference` | `key: str`, `value: str` | Save persistent store setting (survives `/new` chats). |
| `get_preferences` | *(none)* | Retrieve all active store settings and preferences. |

---

## 5. Quickstart & Installation

### Prerequisites
- Python 3.11+
- PostgreSQL 14+ (or Docker Compose)

### 1. Clone & Setup Virtual Environment
```bash
git clone https://github.com/your-repo/supermarket-ops-agent.git
cd supermarket-ops-agent

python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and configure your credentials:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
ANTHROPIC_API_KEY=sk-ant-api03-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

DATABASE_URL=postgresql+asyncpg://postgres:postgrespassword@localhost:5432/kirana_db
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgrespassword@localhost:5432/kirana_test_db
```

### 3. Spin up PostgreSQL with Docker Compose
```bash
docker compose up -d postgres
```

### 4. Seed Database with Real Indian Kirana SKUs
```bash
python -m app.scripts.seed
```
*Seeds Aashirvaad Atta, Loose Sugar/Rice/Dal, Tata Salt, Amul Butter, Maggi 70g, Surf Excel, Ramesh Kumar Khata, and store preferences.*

### 5. Start the Bot
```bash
python -m app.main
```

---

## 6. Running Tests

Run the complete test suite:
```bash
pytest -v
```

### Test Coverage Highlights
- `tests/inventory/` — Stock search, intake, below-cost guardrails & overrides, low stock detection.
- `tests/billing/` — Pure GST mathematics (0%, 5%, 12%, 18% slabs), round-off line, draft multi-turn editing, line item deletion, atomic stock decrement, and oversell guard rollback.
- `tests/khata/` — Credit addition, payment settlement, running balances, unknown customer guard.
- `tests/analytics/` — Daily close calculations, cash vs UPI share, top selling products.
- `tests/documents/` — ReportLab GST Invoice PDF rendering & python-pptx presentation deck generation.
- `tests/preferences/` — Durable preference persistence across conversation resets.
- `tests/integration/` — End-to-end Kirana lifecycle & PostgreSQL concurrency race-condition simulation.

---

## 7. Demo Walkthrough Script (4–5 Minute Scenario)

Follow this sequence in Telegram to demonstrate the entire evaluation scenario:

1. **/start** — View branded greeting and example prompts.
2. **Stock Query**:
   `how much Maggi is left?`
   *(Agent checks DB: 150 packets available)*
3. **Receive Stock**:
   `50 packets of Maggi came in, cost ₹12, MRP ₹14`
   *(Stock updates atomically to 200 packets)*
4. **Multi-Item Draft Bill**:
   `make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, 1 Amul butter, UPI`
   *(Agent builds draft bill: ₹447.00 total with GST breakdown; displays inline [Confirm / Cancel] buttons; inventory untouched)*
5. **Mid-Build Edit**:
   `drop the butter, make it 6 Maggi`
   *(Agent drops butter, updates Maggi to 6: new total ₹417.00)*
6. **Confirm & Finalize**:
   *Tap `[ ✅ Confirm & Finalize ]` inline button*
   *(Row-locks acquired, stock decrements atomically: Maggi becomes 194, Sugar becomes 78)*
7. **Generate PDF Invoice**:
   `send me that bill as a PDF invoice`
   *(Agent returns ReportLab GST Tax Invoice PDF with HSN breakup, Round-Off line, and signature block)*
8. **Oversell Guard**:
   `make a bill: 300 packets of Maggi` -> *Try to finalize*
   *(Agent refuses: "Cannot finalize: Insufficient stock for Maggi 70g (Requested: 300, Available: 194)")*
9. **Khata Credit & Settlement**:
   - `put ₹500 on Ramesh's credit` *(Balance becomes ₹1000.00)*
   - `Ramesh paid ₹300` *(Balance reduces to ₹700.00)*
   - `what is Ramesh's balance?` *(Shows running ledger balance)*
10. **Daily Close & Weekly Presentation Deck**:
    - `close the day` *(Monospace summary of revenue, tax collected, cash vs UPI)*
    - `make this week's sales analysis deck` *(Agent generates and sends 16:9 PPTX deck with Matplotlib charts)*
11. **Persistent Memory Across Chats**:
    - `always assume UPI unless I say cash` *(Saved in `owner_preferences`)*
    - `/new` *(Clears chat context)*
    - `make a bill for 1 Tata Salt` *(Agent automatically applies UPI payment method!)*

---

## 8. Interview Talking Points

- **Why an Agent over a fixed command menu?** Shopkeepers speak in fuzzy intents ("drop the butter, make it 6 Maggi"), not rigid slash commands. An agent resolves ambiguities, composes tools, and preserves context.
- **Why business rules in services, not prompts?** Prompts are probabilistic; accounting and inventory must be deterministic. GST math, oversell guards, and row-level locks belong strictly in Python & PostgreSQL.
- **How is grounding guaranteed?** Tools are the sole source of truth. System prompt strictly forbids estimating prices or inventory numbers.
- **Why test concurrency against PostgreSQL vs SQLite?** SQLite lacks true MVCC row-level locking (`SELECT ... FOR UPDATE` is a no-op in SQLite). Testing against PostgreSQL proves serialized finalization without race conditions.
- **Double-Tap Idempotency**: Protected at both the transport layer (`processed_updates` table) and the database transaction layer (`status == BillStatus.DRAFT` check under row lock).

---

## 9. Collaborators & Submission
- **Author**: Supermarket Ops Agent Team
- **Invited Reviewers**: `Aswath363`, `akshaiP`, `ashwanthnebula`
