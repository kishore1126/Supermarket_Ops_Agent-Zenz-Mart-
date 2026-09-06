# Supermarket Ops Agent — System Architecture & Design Specification

> High-reliability, Telegram-first conversational AI agent for Indian kirana store operations. Built for the Nebula KnowLab Engineering evaluation.

---

## 1. System Architecture Diagram

```mermaid
flowchart TD
    subgraph TelegramClient["Telegram User Interface (No Web App / Forms)"]
        User["🏪 Kirana Shopkeeper (Natural Language)"]
        InlineBtn["🔘 Inline Callbacks [Confirm / Cancel / PDF]"]
    end

    subgraph BotLayer["Telegram Bot Harness (python-telegram-bot v21 Async)"]
        PTB["PTB Application / Dispatcher"]
        IdempGuard{"Idempotency Check\n(processed_updates)"}
        Formatter["Formatters & UI\n(MarkdownV2 Tables, Inline Keyboards)"]
    end

    subgraph AgentLayer["Claude Agent Harness (Observe-Reason-Act Loop)"]
        PromptBuilder["Dynamic System Prompt\n+ Owner Preferences Injection"]
        AgentLoop["Claude Agent Control Loop\n(Multi-Turn Tool Chaining)"]
        LLM["Anthropic Claude 3.5 / 3.7 Sonnet"]
        ToolReg["Pydantic Tool Registry\n(~16 Registered Tools)"]
    end

    subgraph ServiceLayer["Domain Services & Deterministic Business Rules"]
        InvSvc["Inventory Service\n(Oversell & Below-Cost Guard)"]
        BillSvc["Billing Service\n(Draft State Machine)"]
        GSTEngine["GST & Round-Off Engine\n(Pure Python Math)"]
        KhataSvc["Khata Ledger Service\n(Credit & Payment Math)"]
        AnalyticsSvc["Analytics Service\n(Pandas Aggregations)"]
        PrefSvc["Preferences Service\n(Persistent Memory)"]
        DocSvc["Document Generators\n(ReportLab PDF + python-pptx)"]
    end

    subgraph DataLayer["PostgreSQL Persistence (SQLAlchemy 2.0 Async + asyncpg)"]
        DB[(PostgreSQL Database\nRow-Level MVCC Locks)]
        ProductsTable[("products (stock >= 0)")]
        BillsTable[("bills & bill_items")]
        KhataTable[("customers & khata_entries")]
        PrefsTable[("owner_preferences")]
        AuditTable[("audit_log")]
        UpdateTable[("processed_updates")]
    end

    %% Connections
    User -->|Message| PTB
    InlineBtn -->|Callback Query| PTB
    PTB --> IdempGuard
    IdempGuard -->|New Update| AgentLoop
    IdempGuard -->|Duplicate Update| PTB

    AgentLoop <-->|Context & Tools| LLM
    PromptBuilder -->|System Prompt| AgentLoop
    PrefSvc --> PromptBuilder

    AgentLoop -->|Execute Tool| ToolReg
    ToolReg --> InvSvc & BillSvc & KhataSvc & AnalyticsSvc & PrefSvc & DocSvc

    BillSvc --> GSTEngine
    DocSvc --> ReportLab["ReportLab PDF Engine"]
    DocSvc --> PPTXEngine["python-pptx + Matplotlib"]

    InvSvc --> ProductsTable
    BillSvc -->|SELECT ... FOR UPDATE| ProductsTable
    BillSvc --> BillsTable
    KhataSvc --> KhataTable
    PrefSvc --> PrefsTable
    InvSvc & BillSvc & KhataSvc & PrefSvc --> AuditTable
    IdempGuard --> UpdateTable

    AgentLoop --> Formatter
    DocSvc -->|Generated Artifacts| Formatter
    Formatter -->|Rich Receipt / Document Attachment| User
```

---

## 2. Billing State Machine & Concurrency Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Owner as Shopkeeper (Telegram)
    participant Bot as Telegram Bot Handler
    participant Agent as Claude Agent
    participant BillSvc as Billing Service
    participant GST as GST Engine
    participant DB as PostgreSQL (AsyncSession)

    Note over Owner, DB: Phase 1: Multi-Turn Draft Building
    Owner->>Bot: "make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, UPI"
    Bot->>Agent: process_message()
    Agent->>BillSvc: start_or_update_bill(items=[...], payment="UPI")
    BillSvc->>DB: Query Product Prices & GST Slabs (Grounding)
    BillSvc->>GST: calculate_invoice_gst(items)
    GST-->>BillSvc: Subtotal, CGST, SGST, Round-Off, Total
    BillSvc->>DB: Save/Update Bill (Status: DRAFT)
    BillSvc-->>Agent: Draft Preview JSON
    Agent-->>Bot: Formatted Monospace Receipt + [Confirm / Cancel] Keyboard
    Bot-->>Owner: Display Preview with Inline Buttons

    Note over Owner, DB: Phase 2: Atomic Finalize with Row Locking
    Owner->>Bot: Clicks [ ✅ Confirm & Finalize ]
    Bot->>BillSvc: finalize_bill(bill_id)
    BillSvc->>DB: BEGIN TRANSACTION
    BillSvc->>DB: Check Bill Status == DRAFT (Double-tap guard)
    BillSvc->>DB: SELECT * FROM products WHERE id IN (...) FOR UPDATE
    Note over DB: Product rows locked exclusively against concurrent sales
    BillSvc->>BillSvc: Validate Stock: stock_qty >= requested_qty
    alt Insufficient Stock
        BillSvc->>DB: ROLLBACK
        BillSvc-->>Bot: InsufficientStockError
        Bot-->>Owner: ⚠️ Cannot finalize: Insufficient stock
    else Stock Available
        BillSvc->>DB: Decrement product.stock_qty -= item.qty
        BillSvc->>DB: UPDATE bills SET status = 'FINALIZED'
        BillSvc->>DB: INSERT INTO audit_log (BILL_FINALIZED)
        BillSvc->>DB: COMMIT TRANSACTION
        BillSvc-->>Bot: Finalized Invoice Summary
        Bot-->>Owner: ✅ Finalized Receipt + [ 📄 Download PDF ]
    end
```

---

## 3. Database Entity Relationship (ER) Diagram

```mermaid
erDiagram
    products ||--o{ bill_items : "billed in"
    products {
        int id PK
        string name UK
        string unit
        float cost_price
        float selling_price
        float mrp
        float gst_rate
        string hsn_code
        float stock_qty "CHECK >= 0"
        float reorder_level
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    customers ||--o{ bills : "purchases"
    customers ||--o{ khata_entries : "ledger history"
    customers {
        int id PK
        string name UK
        string phone
        datetime created_at
    }

    bills ||--|{ bill_items : "contains"
    bills ||--o{ khata_entries : "linked credit"
    bills {
        int id PK
        int customer_id FK
        string customer_name
        string customer_phone
        enum status "DRAFT | FINALIZED | CANCELLED"
        float subtotal "Taxable base"
        float cgst "Central GST"
        float sgst "State GST"
        float round_off "Paise adjustment"
        float total "Grand payable"
        string payment_method "UPI | Cash | Card | Khata"
        text notes
        datetime created_at
        datetime finalized_at
    }

    bill_items {
        int id PK
        int bill_id FK
        int product_id FK
        string product_name
        string unit
        float quantity
        float unit_price
        float gst_rate
        string hsn_code
        float taxable_value
        float cgst_amount
        float sgst_amount
        float tax_amount
        float line_total
    }

    khata_entries {
        int id PK
        int customer_id FK
        enum type "CREDIT | PAYMENT"
        float amount
        int bill_id FK
        string note
        datetime created_at
    }

    owner_preferences {
        int id PK
        string key UK
        text value
        datetime updated_at
    }

    processed_updates {
        string telegram_update_id PK
        string update_type
        datetime processed_at
    }

    audit_log {
        int id PK
        string action_type
        string reference_id
        text payload
        datetime created_at
    }
```
