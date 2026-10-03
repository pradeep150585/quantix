"""
Test to compare our scanner results with Chartink results
"""
import asyncio
import pandas as pd
from services.short_term_scanner import run_short_term_scan

# Chartink BUY signals from user
chartink_buy = [
    'GAIL', 'ADANIGREEN', 'SBIN', 'BAJFINANCE', 'BSE',
    'ONGC', 'VOLTAS', 'COLPAL', 'INDUSINDBK', 'UNIONBANK',
    'BDL', 'DRREDDY', 'PFC', 'IOC', 'ADANIENT',
    'JINDALSTEL', 'AMBUJACEM', 'TATASTEEL'
]

async def main():
    print("Running scanner...")
    df = await run_short_term_scan()
    
    print(f"\n{'='*80}")
    print(f"OUR SCANNER RESULTS")
    print(f"{'='*80}")
    print(f"Total signals: {len(df)}")
    print(f"BUY signals: {len(df[df['signal'] == 'BUY'])}")
    print(f"SELL signals: {len(df[df['signal'] == 'SELL'])}")
    
    if not df.empty:
        print(f"\n📅 Data date range check (first stock):")
        # Get one stock to check date
        from services.market_data import get_historical_df
        from services.instruments import get_nifty200_symbols
        
        nifty200 = await get_nifty200_symbols()
        if not nifty200.empty:
            first_stock = nifty200.iloc[0]
            test_df = await get_historical_df(first_stock['instrument_key'], interval="day", days=30)
            if not test_df.empty:
                print(f"   Latest date in data: {test_df['datetime'].max()}")
                print(f"   Last 3 dates: {test_df['datetime'].tail(3).tolist()}")
    
    print(f"\n{'='*80}")
    print(f"COMPARISON WITH CHARTINK")
    print(f"{'='*80}")
    
    if df.empty:
        print("❌ No signals found by our scanner")
        return
    
    # Check which Chartink stocks are in our results
    print(f"\n🔍 Checking Chartink BUY signals in our results:")
    for symbol in chartink_buy:
        match = df[df['symbol'] == symbol]
        if not match.empty:
            signal = match.iloc[0]['signal']
            price = match.iloc[0]['price']
            change = match.iloc[0]['change_pct']
            print(f"   {symbol:15} - Our signal: {signal:4} | Price: ₹{price:8.2f} | Change: {change:+.2f}%")
        else:
            print(f"   {symbol:15} - ❌ Not in our results")
    
    # Show our BUY signals
    print(f"\n{'='*80}")
    print(f"OUR BUY SIGNALS")
    print(f"{'='*80}")
    buy_df = df[df['signal'] == 'BUY']
    if buy_df.empty:
        print("❌ No BUY signals found")
    else:
        for _, row in buy_df.iterrows():
            print(f"   {row['symbol']:15} - Price: ₹{row['price']:8.2f} | Change: {row['change_pct']:+.2f}%")
    
    # Show our SELL signals
    print(f"\n{'='*80}")
    print(f"OUR SELL SIGNALS (First 10)")
    print(f"{'='*80}")
    sell_df = df[df['signal'] == 'SELL'].head(10)
    if sell_df.empty:
        print("❌ No SELL signals found")
    else:
        for _, row in sell_df.iterrows():
            print(f"   {row['symbol']:15} - Price: ₹{row['price']:8.2f} | Change: {row['change_pct']:+.2f}%")

if __name__ == "__main__":
    asyncio.run(main())
