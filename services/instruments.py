"""
Instruments service – fetches Nifty 200 constituents from NSE and resolves
Upstox instrument keys from the Upstox instrument master CSV.
"""
import asyncio
import io
import time
import httpx
import pandas as pd
from loguru import logger

_INDEX_URLS = {
    "NIFTY 200":        "https://archives.nseindia.com/content/indices/ind_nifty200list.csv",
    "NIFTY 50":         "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
    "NIFTY NEXT 50":    "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv",
    "NIFTY BANK":       "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
    "NIFTY IT":         "https://archives.nseindia.com/content/indices/ind_niftyitlist.csv",
    "NIFTY AUTO":       "https://archives.nseindia.com/content/indices/ind_niftyautolist.csv",
    "NIFTY FMCG":       "https://archives.nseindia.com/content/indices/ind_niftyfmcglist.csv",
    "NIFTY PHARMA":     "https://archives.nseindia.com/content/indices/ind_niftypharmalist.csv",
    "NIFTY METAL":      "https://archives.nseindia.com/content/indices/ind_niftymetallist.csv",
    "NIFTY ENERGY":     "https://archives.nseindia.com/content/indices/ind_niftyenergylist.csv",
    "NIFTY REALTY":     "https://archives.nseindia.com/content/indices/ind_niftyrealtylist.csv",
    "NIFTY PSU BANK":   "https://archives.nseindia.com/content/indices/ind_niftypsubanklist.csv",
    "NIFTY MIDCAP 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
    "NIFTY SMALLCAP 100": "https://archives.nseindia.com/content/indices/ind_niftysmallcap100list.csv",
    "NIFTY FINNIFTY":   "https://archives.nseindia.com/content/indices/ind_niftyfinancialserviceslist.csv",
}

# Upstox publishes a daily instrument master CSV (no auth required)
_UPSTOX_INSTRUMENT_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.csv.gz"

_cache: dict[str, tuple[float, pd.DataFrame]] = {}
_instrument_master: pd.DataFrame = pd.DataFrame()
_instrument_master_ts: float = 0.0
_CACHE_TTL = 3600

_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.nseindia.com/",
    "DNT": "1",
}


async def _get_upstox_instrument_master() -> pd.DataFrame:
    """Download Upstox NSE instrument master and return symbol→instrument_key map."""
    global _instrument_master, _instrument_master_ts
    now = time.time()
    if not _instrument_master.empty and (now - _instrument_master_ts) < _CACHE_TTL:
        return _instrument_master

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(_UPSTOX_INSTRUMENT_URL)
            resp.raise_for_status()
            df = pd.read_csv(io.BytesIO(resp.content), compression="gzip")
            df.columns = [c.strip().lower() for c in df.columns]
            # Filter to NSE EQUITY
            if "instrument_type" in df.columns:
                filtered = df[df["instrument_type"] == "EQUITY"]
                if not filtered.empty:
                    df = filtered
            _instrument_master = df
            _instrument_master_ts = now
            logger.info(f"Loaded {len(df)} NSE EQ instruments from Upstox master")
            return df
    except Exception as e:
        logger.warning(f"Upstox instrument master fetch failed: {e}")
        return pd.DataFrame()


def _build_instrument_key(symbol: str, isin: str, master_df: pd.DataFrame) -> str:
    """Resolve the Upstox instrument key (ISIN-based) for a symbol."""
    if not master_df.empty:
        sym_col = next((c for c in ["tradingsymbol", "trading_symbol", "symbol"] if c in master_df.columns), None)
        if sym_col:
            match = master_df[master_df[sym_col].str.upper() == symbol.upper()]
            if not match.empty and "instrument_key" in match.columns:
                return str(match.iloc[0]["instrument_key"])
        if isin and "isin" in master_df.columns:
            match = master_df[master_df["isin"] == isin]
            if not match.empty and "instrument_key" in match.columns:
                return str(match.iloc[0]["instrument_key"])
    return f"NSE_EQ|{isin}" if isin else f"NSE_EQ|{symbol}"


async def _fetch_nse_csv(url: str, client: httpx.AsyncClient) -> pd.DataFrame:
    """Fetch an NSE index CSV with proper cookie/session handling."""
    try:
        # Step 1: get session cookie from NSE homepage
        await client.get("https://www.nseindia.com", headers=_NSE_HEADERS, timeout=15)
        await asyncio.sleep(0.5)
        # Step 2: fetch the actual CSV
        resp = await client.get(url, headers=_NSE_HEADERS, timeout=15)
        resp.raise_for_status()
        if not resp.text.strip() or "<html" in resp.text[:100].lower():
            raise ValueError("Received HTML instead of CSV — NSE blocked the request")
        df = pd.read_csv(io.StringIO(resp.text))
        return df
    except Exception as e:
        raise RuntimeError(f"NSE CSV fetch failed: {e}") from e


async def fetch_index_constituents(index_name: str = "NIFTY 200") -> pd.DataFrame:
    now = time.time()
    if index_name in _cache and (now - _cache[index_name][0]) < _CACHE_TTL:
        return _cache[index_name][1]

    url = _INDEX_URLS.get(index_name)
    if not url:
        logger.warning(f"No URL configured for index: {index_name}")
        return pd.DataFrame()

    master_df = await _get_upstox_instrument_master()

    try:
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers=_NSE_HEADERS,
        ) as client:
            df = await _fetch_nse_csv(url, client)

        # Normalise columns
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        rename_map = {"isin_code": "isin", "company_name": "company_name"}
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        for col in ["symbol", "company_name", "series", "isin", "industry", "sector"]:
            if col not in df.columns:
                df[col] = ""
        # Map industry → sector if sector is missing/empty
        if df["sector"].eq("").all() and not df["industry"].eq("").all():
            df["sector"] = df["industry"]
        df["symbol"] = df["symbol"].str.strip()
        df["isin"] = df["isin"].str.strip()

        # Resolve instrument keys via Upstox master
        df["instrument_key"] = df.apply(
            lambda r: _build_instrument_key(r["symbol"], r["isin"], master_df), axis=1
        )

        _cache[index_name] = (now, df)
        logger.info(f"Loaded {len(df)} constituents for {index_name}")
        return df

    except Exception as e:
        logger.error(f"Failed to fetch {index_name}: {e}")
        if index_name in _cache:
            logger.info("Returning stale cached data")
            return _cache[index_name][1]
        return pd.DataFrame()


async def get_nifty200_symbols() -> pd.DataFrame:
    return await fetch_index_constituents("NIFTY 200")


async def get_all_index_constituents() -> dict[str, pd.DataFrame]:
    tasks = {name: fetch_index_constituents(name) for name in _INDEX_URLS}
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    return {
        name: (r if isinstance(r, pd.DataFrame) else pd.DataFrame())
        for name, r in zip(tasks.keys(), results)
    }
