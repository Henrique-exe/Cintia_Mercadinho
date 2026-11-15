"""Persistência local e esquema do SIGEC. Todos os valores em centavos e quantidades-base."""
import sqlite3
from contextlib import contextmanager
from flask import current_app, g

SCHEMA = r"""
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS products (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL, brand TEXT NOT NULL DEFAULT '', presentation TEXT NOT NULL DEFAULT '',
 category TEXT NOT NULL DEFAULT '', barcode TEXT UNIQUE,
 unit TEXT NOT NULL CHECK(unit IN ('UN','KG')),
 purchase_price_cents INTEGER NOT NULL DEFAULT 0 CHECK(purchase_price_cents>=0),
 price_cents INTEGER NOT NULL CHECK(price_cents>=0),
 stock_base INTEGER NOT NULL DEFAULT 0 CHECK(stock_base>=0),
 minimum_base INTEGER NOT NULL DEFAULT 0 CHECK(minimum_base>=0),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS customers (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cash_sessions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 opened_at TEXT NOT NULL, opening_cents INTEGER NOT NULL CHECK(opening_cents>=0),
 opening_note TEXT NOT NULL DEFAULT '', status TEXT NOT NULL CHECK(status IN ('OPEN','CLOSED')),
 closed_at TEXT, expected_cents INTEGER, counted_cents INTEGER, difference_cents INTEGER, closing_note TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS single_open_session ON cash_sessions(status) WHERE status='OPEN';
CREATE TABLE IF NOT EXISTS sales (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 created_at TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('COMPLETED','CANCELED')),
 subtotal_cents INTEGER NOT NULL CHECK(subtotal_cents>=0),
 discount_percent TEXT NOT NULL, discount_percent_cents INTEGER NOT NULL,
 discount_fixed_cents INTEGER NOT NULL, total_cents INTEGER NOT NULL CHECK(total_cents>=0),
 session_id INTEGER NOT NULL REFERENCES cash_sessions(id),
 client_token TEXT NOT NULL UNIQUE, canceled_at TEXT, cancel_reason TEXT
);
CREATE TABLE IF NOT EXISTS sale_items (
 id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL REFERENCES sales(id),
 product_id INTEGER NOT NULL REFERENCES products(id), name_snapshot TEXT NOT NULL,
 unit TEXT NOT NULL CHECK(unit IN ('UN','KG')), quantity_base INTEGER NOT NULL CHECK(quantity_base>0),
 price_cents INTEGER NOT NULL, line_total_cents INTEGER NOT NULL,
 cost_cents INTEGER
);
CREATE TABLE IF NOT EXISTS sale_payments (
 id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL REFERENCES sales(id),
 method TEXT NOT NULL CHECK(method IN ('CASH','PIX','CARD','CREDIT')),
 applied_cents INTEGER NOT NULL CHECK(applied_cents>0),
 tendered_cents INTEGER NOT NULL DEFAULT 0, change_cents INTEGER NOT NULL DEFAULT 0,
 customer_id INTEGER REFERENCES customers(id)
);
CREATE TABLE IF NOT EXISTS debts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL UNIQUE REFERENCES sales(id),
 customer_id INTEGER NOT NULL REFERENCES customers(id), original_cents INTEGER NOT NULL CHECK(original_cents>0),
 outstanding_cents INTEGER NOT NULL CHECK(outstanding_cents>=0),
 status TEXT NOT NULL CHECK(status IN ('OPEN','PAID','CANCELED'))
);
CREATE TABLE IF NOT EXISTS credit_receipts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, debt_id INTEGER NOT NULL REFERENCES debts(id),
 session_id INTEGER NOT NULL REFERENCES cash_sessions(id),
 amount_cents INTEGER NOT NULL CHECK(amount_cents>0),
 method TEXT NOT NULL CHECK(method IN ('CASH','PIX','CARD')),
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cash_movements (
 id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL REFERENCES cash_sessions(id),
 kind TEXT NOT NULL CHECK(kind IN ('OPENING','SALE_CASH','RECEIPT_CASH','WITHDRAW','REFUND_CASH')),
 amount_cents INTEGER NOT NULL, sale_id INTEGER REFERENCES sales(id),
 receipt_id INTEGER REFERENCES credit_receipts(id),
 note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS refunds (
 id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL REFERENCES sales(id),
 session_id INTEGER NOT NULL REFERENCES cash_sessions(id),
 method TEXT NOT NULL CHECK(method IN ('CASH','PIX','CARD')),
 amount_cents INTEGER NOT NULL CHECK(amount_cents>0),
 note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stock_movements (
 id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL REFERENCES products(id),
 sale_id INTEGER REFERENCES sales(id), kind TEXT NOT NULL CHECK(kind IN ('INITIAL','ENTRY','SALE','CANCEL')),
 quantity_base INTEGER NOT NULL, stock_after_base INTEGER NOT NULL CHECK(stock_after_base>=0),
 note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shopping_entries (
 product_id INTEGER PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
 quantity_base INTEGER NOT NULL CHECK(quantity_base>=0), checked INTEGER NOT NULL DEFAULT 0 CHECK(checked IN (0,1)),
 manual INTEGER NOT NULL DEFAULT 0 CHECK(manual IN (0,1))
);
CREATE INDEX IF NOT EXISTS idx_sales_created ON sales(created_at);
CREATE INDEX IF NOT EXISTS idx_stock_product ON stock_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_receipts_debt ON credit_receipts(debt_id);
"""


def get_db():
    if 'db' not in g:
        conn = sqlite3.connect(current_app.config['DATABASE'], timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA busy_timeout = 15000')
        g.db = conn
    return g.db


def close_db(error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    # Migração aditiva: mantém as vendas e os produtos existentes intactos.
    columns = {row['name'] for row in db.execute('PRAGMA table_info(sale_items)')}
    if 'cost_cents' not in columns:
        db.execute('ALTER TABLE sale_items ADD COLUMN cost_cents INTEGER')
    # Custos históricos desconhecidos NÃO devem ser calculados com o preço atual.



@contextmanager
def atomic():
    conn = get_db()
    conn.execute('BEGIN IMMEDIATE')
    try:
        yield conn
        conn.execute('COMMIT')
    except BaseException:
        conn.execute('ROLLBACK')
        raise


def rowdict(row):
    return dict(row) if row is not None else None
