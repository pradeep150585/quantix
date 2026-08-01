"""
Run: .venv\Scripts\python.exe diagnose.py
"""
import asyncio, sys, io
sys.path.insert(0, ".")
import httpx
import pandas as pd

async def main():
    url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.csv.gz"
    print(f"Downloading Upstox NSE instrument master...")
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    df = pd.read_csv(io.BytesIO(resp.content), compression="gzip")
    print(f"Total rows: {len(df)}")
    print(f"Columns: {df.columns.tolist()}")
    print(f"\nFirst 3 rows:\n{df.head(3).to_string()}")
    print(f"\nUnique instrument_type values: {df['instrument_type'].unique().tolist() if 'instrument_type' in df.columns else 'N/A'}")
    # Show a sample RELIANCE row
    for col in ["tradingsymbol", "trading_symbol", "symbol"]:
        if col in df.columns:
            rel = df[df[col] == "RELIANCE"]
            if not rel.empty:
                print(f"\nRELIANCE row:\n{rel.iloc[0].to_dict()}")
            break

asyncio.run(main())
