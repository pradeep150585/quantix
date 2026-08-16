# QUANTIX APPLICATION - COMPREHENSIVE CODE REVIEW
## Senior-Level Analysis & Recommendations

---

## CRITICAL ISSUES (Must Fix)

### 1. Missing Error Handling in get_historical_df
**File**: `services/market_data.py` (lines 95-110)
**Issue**: API failures return empty DataFrame without logging specific errors
**Impact**: Difficult to debug data issues, silent failures
**Fix**:
```python
result = await client.get_historical_candles(instrument_key, interval, fetch_from, today_str)
if result is None:
    logger.error(f"API returned None for {instrument_key}")
    return pd.DataFrame()
if result.get("status") != "success":
    logger.error(f"API error for {instrument_key}: {result.get('errors', 'Unknown')}")
    return pd.DataFrame()
```

### 2. Benchmark DataFrame Not Validated
**File**: `scanner/__init__.py` (lines 120-145)
**Issue**: Benchmark resampled without checking if it has sufficient data
**Impact**: compute_all() may fail or produce invalid results
**Fix**:
```python
wbench = _resample_to_weekly(benchmark_df) if benchmark_df is not None and not benchmark_df.empty else None
if wbench is not None and len(wbench) < 20:
    logger.warning(f"Benchmark has insufficient data: {len(wbench)} weeks")
    wbench = None
```

### 3. Page Import Exceptions Not Caught
**File**: `app.py` (lines 265-272)
**Issue**: If a page module fails to import, entire app crashes
**Impact**: App becomes unusable
**Fix**:
```python
try:
    if page_module == "dashboard":
        from pages.dashboard import render
    elif page_module == "live_scanner":
        from pages.live_scanner import render
    # ... etc
except ImportError as e:
    st.error(f"Failed to load page: {e}")
    render = None
```

### 4. Global Cache Not Thread-Safe
**File**: `scanner/__init__.py` (line 15)
**Issue**: `_scan_cache` global variable modified without locks
**Impact**: Race conditions in concurrent scenarios
**Fix**:
```python
import threading
_scan_cache_lock = threading.Lock()

# In run_scan():
with _scan_cache_lock:
    if not force and _scan_cache and (now - _scan_cache[0]) < _SCAN_TTL:
        return _scan_cache[1]
    # ... rest of logic
    _scan_cache = (now, df)
```

### 5. No Validation of Indicator Computation
**File**: `scanner/__init__.py` (lines 155-160)
**Issue**: compute_all() result not validated before use
**Impact**: KeyError if indicators fail to compute
**Fix**:
```python
indicators = compute_all(wdf, wbench)
if not indicators or not all(k in indicators for k in ['rsi', 'macd', 'atr', 'adx']):
    logger.warning(f"Incomplete indicators for {symbol}")
    return None
```

### 6. Synchronous API Call in Async Context
**File**: `pages/strategies_page.py` (lines 85-110)
**Issue**: _build_strategy_chart() uses _run() to execute async code synchronously
**Impact**: Blocks event loop, performance issues
**Fix**:
```python
@st.cache_data(ttl=3600)
def _build_strategy_chart(symbol: str, row: pd.Series) -> go.Figure:
    # Move async logic to separate function
    # Use asyncio.run() only at top level
```

---

## HIGH PRIORITY ISSUES

### 7. Duplicate _resample_to_weekly() Function
**Files**: `scanner/__init__.py`, `services/vcp_scanner.py`, `services/elder_scanner.py`
**Issue**: Same function duplicated 3 times
**Impact**: Maintenance burden, inconsistency
**Fix**: Create `services/utils.py`:
```python
def resample_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLCV to weekly (week ending Friday)."""
    if df.empty or "datetime" not in df.columns:
        return df
    df = df.set_index("datetime")
    wdf = df.resample("W-FRI").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).dropna()
    wdf.index.name = "datetime"
    return wdf.reset_index()
```

Then import in all three files:
```python
from services.utils import resample_to_weekly as _resample_to_weekly
```

### 8. Bulk Prefetch Silent Failures
**File**: `services/market_data.py` (lines 130-160)
**Issue**: Exceptions silently caught without logging
**Impact**: Hard to debug data issues
**Fix**:
```python
for key, data in raw.items():
    try:
        # ... existing logic
    except Exception as e:
        logger.warning(f"Failed to save OHLC for {key}: {e}")
        continue
```

### 9. Chart DataFrame Missing Validation
**File**: `services/elder_scanner.py` (lines 250-280)
**Issue**: Chart data created without validating indicator columns
**Impact**: NaN values cause chart rendering errors
**Fix**:
```python
chart_df = wdf.tail(_CHART_BARS).copy().reset_index(drop=True)
chart_df["ema13"]  = _ema(close, 13).tail(_CHART_BARS).values
chart_df["ema26"]  = _ema(close, 26).tail(_CHART_BARS).values
chart_df["fi2"]    = _ema(_force_index(wdf), 2).tail(_CHART_BARS).values
chart_df["macd_h"] = _macd_hist(close).tail(_CHART_BARS).values

# Validate all columns exist and have no all-NaN columns
required_cols = ["ema13", "ema26", "fi2", "macd_h"]
for col in required_cols:
    if col not in chart_df.columns or chart_df[col].isna().all():
        logger.warning(f"Missing or invalid indicator: {col}")
        return None
```

### 10. ADX Calculation May Produce NaN
**File**: `services/elder_scanner.py` (lines 150-170)
**Issue**: Division by (di_plus + di_minus + 1e-9) can produce NaN
**Impact**: Invalid ADX values propagate downstream
**Fix**:
```python
dx = (100 * (di_plus - di_minus).abs() / (di_plus + di_minus + 1e-9))
adx_val = _ema(dx, n)
adx_val = adx_val.fillna(0)  # Replace NaN with 0
```

---

## MEDIUM PRIORITY ISSUES

### 11. Hardcoded Thresholds Not Configurable
**File**: `services/elder_scanner.py` (lines 200-220)
**Issue**: Thresholds (w_score < 15, pa_score < 10) hardcoded
**Impact**: Can't tune without code changes
**Fix**: Add at module level:
```python
# Configuration constants
MIN_WEEKLY_SCORE = 15
MIN_PA_SCORE = 10
MIN_RR_SIGNAL = "NO TRADE"
```

### 12. Key Normalization Logic Fragile
**File**: `services/market_data.py` (lines 50-75)
**Issue**: _normalise_keys() doesn't handle None or malformed keys
**Impact**: KeyError in downstream code
**Fix**:
```python
def _normalise_keys(raw: dict) -> dict:
    if not raw:
        return {}
    result = {}
    for k, v in raw.items():
        if not k or not isinstance(k, str):
            continue
        for variant in [k, k.replace(":", "|"), k.replace("|", ":")]:
            result[variant] = v
        token = v.get("instrument_token", "")
        if token and isinstance(token, str):
            for variant in [token, token.replace(":", "|"), token.replace("|", ":")]:
                result[variant] = v
    return result
```

### 13. Chart Store Dictionary Access Without Validation
**File**: `pages/ai_picks.py` (lines 140-165)
**Issue**: chart_data accessed without null checks
**Impact**: AttributeError if chart_data is None
**Fix**:
```python
chart_data = chart_store.get(symbol)
if chart_data is None:
    st.info("Chart data unavailable.")
    return
    
cdf = chart_data.get("df") if isinstance(chart_data, dict) else chart_data
if cdf is None or cdf.empty:
    st.info("Chart data unavailable.")
    return
```

### 14. RSI Calculation Inefficient
**File**: `pages/strategies_page.py` (lines 120-130)
**Issue**: RSI recalculated bar-by-bar in loop (O(n²) complexity)
**Impact**: Performance degradation with large datasets
**Fix**:
```python
# Use vectorized calculation instead
from indicators import rsi as compute_rsi
rsi_series = compute_rsi(close)
```

### 15. VCP Sector Summary May Fail
**File**: `pages/ai_picks.py` (lines 200-230)
**Issue**: groupby() fails if df empty or no sector data
**Impact**: App crash on empty results
**Fix**:
```python
if df.empty or "sector" not in df.columns or df["sector"].isna().all():
    st.info("No sector data available.")
    return

sector_df = (
    df.groupby("sector").agg(
        Setups=("vcp_score", "count"),
        Avg_Score=("vcp_score", "mean"),
        Breakouts=("is_breakout", "sum"),
    ).reset_index().sort_values("Avg_Score", ascending=False)
)
```

---

## LOW PRIORITY ISSUES

### 16. Contraction Detection May Return Empty List
**File**: `services/vcp_scanner.py` (lines 100-120)
**Issue**: _contractions_valid() doesn't explicitly handle empty list
**Impact**: Unclear behavior
**Fix**:
```python
def _contractions_valid(contractions: list[float]) -> bool:
    if not contractions:
        return False
    n = len(contractions)
    if n < _MIN_CONTRACTIONS or n > _MAX_CONTRACTIONS:
        return False
    for i in range(1, n):
        if contractions[i] >= contractions[i - 1]:
            return False
    return contractions[0] >= 3.0
```

### 17. Cache Clearing on Every Page Change
**File**: `app.py` (lines 75-77)
**Issue**: All caches cleared on page change (may be inefficient)
**Impact**: Unnecessary recomputation
**Fix**: Document why full clear is needed or implement selective clearing

### 18. Missing Validation in _render_strategy_row
**File**: `pages/strategies_page.py` (lines 60-90)
**Issue**: Row data accessed without validating required fields
**Impact**: KeyError if data incomplete
**Fix**:
```python
required_fields = ['symbol', 'best_score', 'best_strategy', 'cmp', 'pct_change']
for field in required_fields:
    if field not in row or pd.isna(row[field]):
        st.warning(f"Missing field: {field}")
        return
```

---

## SUMMARY OF FIXES

| Issue | Severity | File | Fix Type |
|-------|----------|------|----------|
| Missing error handling | Critical | market_data.py | Add logging |
| Benchmark validation | Critical | scanner/__init__.py | Add checks |
| Page import exceptions | Critical | app.py | Add try-catch |
| Thread-unsafe cache | Critical | scanner/__init__.py | Add locks |
| Indicator validation | Critical | scanner/__init__.py | Add validation |
| Async in sync context | Critical | strategies_page.py | Refactor |
| Duplicate functions | High | 3 files | Centralize |
| Silent failures | High | market_data.py | Add logging |
| Chart validation | High | elder_scanner.py | Add checks |
| ADX NaN values | High | elder_scanner.py | Fill NaN |
| Hardcoded thresholds | Medium | elder_scanner.py | Use constants |
| Key normalization | Medium | market_data.py | Add validation |
| Chart store access | Medium | ai_picks.py | Add null checks |
| RSI performance | Medium | strategies_page.py | Vectorize |
| Sector summary crash | Medium | ai_picks.py | Add guards |

---

## IMPLEMENTATION PRIORITY

1. **Immediate** (Next commit):
   - Fix critical issues #1-6
   - Centralize _resample_to_weekly()

2. **Short-term** (This week):
   - Fix high priority issues #7-10
   - Add comprehensive error logging

3. **Medium-term** (Next sprint):
   - Fix medium priority issues #11-15
   - Add unit tests for edge cases

4. **Long-term** (Ongoing):
   - Implement configuration system
   - Add performance monitoring
   - Refactor for better testability
