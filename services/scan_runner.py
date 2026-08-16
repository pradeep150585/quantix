"""
Combined scan runner — runs VCP and Elder Triple Screen concurrently,
sharing a single bulk_prefetch + get_ltp call to halve API round-trips.
"""
import asyncio
import pandas as pd
import streamlit as st
from loguru import logger

from services.instruments import get_nifty200_symbols
from services.market_data import bulk_prefetch_today_ohlc, get_ltp
from services import vcp_scanner as _vcp
from services import elder_scanner as _elder


async def _run_both(symbols_df: pd.DataFrame, ltp_map: dict):
    all_keys = symbols_df["instrument_key"].tolist()
    # Reduced semaphore limits for Streamlit stability
    sem_vcp   = asyncio.Semaphore(50)
    sem_elder = asyncio.Semaphore(50)

    vcp_tasks   = [_vcp._process(row, ltp_map, sem_vcp)   for _, row in symbols_df.iterrows()]
    elder_tasks = [_elder._process(row, ltp_map, sem_elder) for _, row in symbols_df.iterrows()]

    vcp_res, elder_res = await asyncio.gather(
        asyncio.gather(*vcp_tasks,   return_exceptions=True),
        asyncio.gather(*elder_tasks, return_exceptions=True),
    )
    return vcp_res, elder_res


async def _combined_scan():
    try:
        symbols_df = await get_nifty200_symbols()
        if symbols_df.empty:
            logger.error("No symbols retrieved from Nifty200")
            return pd.DataFrame(), {}, pd.DataFrame(), {}

        logger.info(f"Scanning {len(symbols_df)} stocks from Nifty200")
        all_keys = symbols_df["instrument_key"].tolist()

        # Single shared prefetch + LTP — both scanners reuse the same data
        await bulk_prefetch_today_ohlc(all_keys)
        ltp_map = await get_ltp(all_keys)

        vcp_res, elder_res = await _run_both(symbols_df, ltp_map)

        # --- VCP results ---
        vcp_records, vcp_chart_store = [], {}
        for r in vcp_res:
            if not isinstance(r, dict):
                continue
            vcp_chart_store[r["symbol"]] = {
                "df": r.pop("_chart_df"),
                "hi": r.pop("_swing_hi"),
                "lo": r.pop("_swing_lo"),
            }
            vcp_records.append(r)

        vcp_df = (
            pd.DataFrame(vcp_records)
            .sort_values("vcp_score", ascending=False)
            .reset_index(drop=True)
            if vcp_records else pd.DataFrame()
        )

        # --- Elder results ---
        elder_records, elder_chart_store = [], {}
        for r in elder_res:
            if not isinstance(r, dict):
                continue
            elder_chart_store[r["symbol"]] = r.pop("_chart_df")
            elder_records.append(r)

        elder_df = (
            pd.DataFrame(elder_records)
            .sort_values("score", ascending=False)
            .reset_index(drop=True)
            if elder_records else pd.DataFrame()
        )

        logger.info(f"Scan complete: VCP={len(vcp_df)}, Elder={len(elder_df)}")
        
        # Debug: Check what we're returning
        logger.debug(f"Returning: vcp_df shape={vcp_df.shape}, elder_df shape={elder_df.shape}")
        
        return vcp_df, vcp_chart_store, elder_df, elder_chart_store
        
    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)
        return pd.DataFrame(), {}, pd.DataFrame(), {}


def run_combined_scan_cached():
    """
    Runs both scans concurrently. Results cached in session state (survives tab
    switches). Re-runs only on page refresh or explicit cache clear.
    """
    _KEY = "_combined_scan_result"
    if _KEY in st.session_state:
        return st.session_state[_KEY]

    # Apply nest_asyncio to allow nested event loops in Streamlit
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        logger.warning("nest_asyncio not available - async operations may fail")
    
    # Get or create event loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(_combined_scan())
        logger.info(f"Scan completed - returning result with VCP rows: {len(result[0]) if result and len(result) > 0 and not result[0].empty else 0}")
    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)
        result = (pd.DataFrame(), {}, pd.DataFrame(), {})
    
    st.session_state[_KEY] = result
    return result
