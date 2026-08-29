"""
Database layer - SQLite for watchlist, alerts, scan history, and candle cache.
"""
import sqlite3
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from config import get

DB_PATH = Path(get("database.sqlite_path", "database/nifty_scanner.db"))


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                company_name TEXT,
                instrument_key TEXT,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                strategy TEXT,
                score REAL,
                message TEXT,
                triggered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                sent INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scanned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                total_stocks INTEGER,
                top_picks TEXT
            );
            CREATE TABLE IF NOT EXISTS candle_cache (
                instrument_key TEXT NOT NULL,
                interval TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL, volume REAL,
                PRIMARY KEY (instrument_key, interval, date)
            );
            CREATE INDEX IF NOT EXISTS idx_candle_key_interval
                ON candle_cache (instrument_key, interval);
            CREATE TABLE IF NOT EXISTS scan_results_cache (
                scan_date TEXT PRIMARY KEY,
                scan_data TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS scanner_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_date TEXT NOT NULL,
                scanner_type TEXT NOT NULL,
                symbol TEXT NOT NULL,
                company_name TEXT,
                instrument_key TEXT,
                entry_price REAL,
                stop_price REAL,
                target1_price REAL,
                target2_price REAL,
                score REAL,
                signal TEXT,
                sector TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(signal_date, scanner_type, symbol)
            );
            CREATE INDEX IF NOT EXISTS idx_scanner_signals_date
                ON scanner_signals (signal_date DESC);
            CREATE INDEX IF NOT EXISTS idx_scanner_signals_symbol
                ON scanner_signals (symbol);
        """)



# -- Watchlist -----------------------------------------------------------------

def add_to_watchlist(symbol: str, company_name: str = "", instrument_key: str = "", notes: str = ""):
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO watchlist (symbol, company_name, instrument_key, notes) VALUES (?,?,?,?)",
                (symbol, company_name, instrument_key, notes)
            )
    except Exception:
        pass


def remove_from_watchlist(symbol: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM watchlist WHERE symbol=?", (symbol,))


def get_watchlist() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM watchlist ORDER BY added_at DESC").fetchall()
        return [dict(r) for r in rows]


def is_in_watchlist(symbol: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM watchlist WHERE symbol=?", (symbol,)).fetchone()
        return row is not None


# -- Alerts -------------------------------------------------------------------

def save_alert(symbol: str, strategy: str, score: float, message: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO alerts (symbol, strategy, score, message) VALUES (?,?,?,?)",
            (symbol, strategy, score, message)
        )


def get_recent_alerts(limit: int = 50) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts ORDER BY triggered_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# -- Scan history -------------------------------------------------------------

def save_scan_result(total: int, top_picks: list):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO scan_history (total_stocks, top_picks) VALUES (?,?)",
            (total, json.dumps(top_picks))
        )


# -- Candle cache -------------------------------------------------------------

def get_cached_candles(instrument_key: str, interval: str, from_date: str) -> pd.DataFrame:
    """Return cached candles on or after from_date."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT date, open, high, low, close, volume FROM candle_cache "
            "WHERE instrument_key=? AND interval=? AND date>=? ORDER BY date",
            (instrument_key, interval, from_date)
        ).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def get_latest_cached_date(instrument_key: str, interval: str) -> str:
    """Return the most recent cached date string, or empty string if none."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(date) FROM candle_cache WHERE instrument_key=? AND interval=?",
            (instrument_key, interval)
        ).fetchone()
    return row[0] or ""


def save_candles(instrument_key: str, interval: str, df: pd.DataFrame):
    """Upsert candle rows into candle_cache."""
    if df.empty:
        return
    rows = [
        (
            instrument_key, interval,
            str(row["datetime"])[:10],
            float(row["open"]), float(row["high"]),
            float(row["low"]),  float(row["close"]),
            float(row["volume"]),
        )
        for _, row in df.iterrows()
    ]
    with get_conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO candle_cache "
            "(instrument_key, interval, date, open, high, low, close, volume) "
            "VALUES (?,?,?,?,?,?,?,?)",
            rows
        )


# -- Scanner Signals (for backtesting) ----------------------------------------

def save_scanner_signal(signal_date: str, scanner_type: str, symbol: str, 
                       company_name: str, instrument_key: str, entry_price: float,
                       stop_price: float, target1_price: float, target2_price: float,
                       score: float, signal: str, sector: str = ""):
    """Save a scanner signal for backtesting."""
    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO scanner_signals 
                   (signal_date, scanner_type, symbol, company_name, instrument_key,
                    entry_price, stop_price, target1_price, target2_price, score, signal, sector)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (signal_date, scanner_type, symbol, company_name, instrument_key,
                 entry_price, stop_price, target1_price, target2_price, score, signal, sector)
            )
    except Exception as e:
        print(f"Error saving scanner signal: {e}")


def get_scanner_signals(days: int = 30, scanner_type: str = None) -> pd.DataFrame:
    """Get scanner signals from the last N days, optionally filtered by scanner type."""
    with get_conn() as conn:
        if scanner_type:
            query = """
                SELECT * FROM scanner_signals 
                WHERE signal_date >= date('now', ?) AND scanner_type = ?
                ORDER BY signal_date DESC, score DESC
            """
            rows = conn.execute(query, (f'-{days} days', scanner_type)).fetchall()
        else:
            query = """
                SELECT * FROM scanner_signals 
                WHERE signal_date >= date('now', ?)
                ORDER BY signal_date DESC, score DESC
            """
            rows = conn.execute(query, (f'-{days} days',)).fetchall()
    
    if not rows:
        return pd.DataFrame()
    
    return pd.DataFrame([dict(r) for r in rows])


def get_all_scanner_signals(from_date: str = None) -> pd.DataFrame:
    """Get all scanner signals, optionally from a specific date."""
    with get_conn() as conn:
        if from_date:
            query = """
                SELECT * FROM scanner_signals 
                WHERE signal_date >= ?
                ORDER BY signal_date DESC, score DESC
            """
            rows = conn.execute(query, (from_date,)).fetchall()
        else:
            query = "SELECT * FROM scanner_signals ORDER BY signal_date DESC, score DESC"
            rows = conn.execute(query).fetchall()
    
    if not rows:
        return pd.DataFrame()
    
    return pd.DataFrame([dict(r) for r in rows])

