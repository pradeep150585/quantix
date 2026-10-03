"""
Test script to debug intraday scanner
"""
import asyncio
import pandas as pd
from loguru import logger
from services.market_data import get_intraday_df
from services.short_term_scanner import run_short_term_scan, _calculate_heikin_ashi, _calculate_ema_ha_close, _check_buy_conditions, _check_sell_conditions

async def test_single_stock():
    """Test intraday data fetch for a single stock"""
    # Test with Reliance
    instrument_key = "NSE_EQ|INE002A01018"  # Reliance
    
    print("\n" + "="*80)
    print("TESTING INTRADAY DATA FETCH")
    print("="*80)
    
    try:
        df = await get_intraday_df(instrument_key, interval="10minute")
        print(f"\n✅ Got {len(df)} candles for Reliance")
        
        if not df.empty:
            print(f"\n📊 Columns: {df.columns.tolist()}")
            print(f"\n📅 Date range: {df['datetime'].min()} to {df['datetime'].max()}")
            print(f"\n🕐 Last 3 candles:")
            print(df.tail(3).to_string())
            
            # Now test HA calculation
            print("\n" + "="*80)
            print("TESTING HEIKIN-ASHI CALCULATION")
            print("="*80)
            
            ha_df = _calculate_heikin_ashi(df)
            print(f"\n✅ Calculated HA for {len(ha_df)} candles")
            print(f"\n🕐 Last 3 HA candles:")
            print(ha_df[['datetime', 'ha_open', 'ha_high', 'ha_low', 'ha_close']].tail(3).to_string())
            
            # Test EMA calculation
            print("\n" + "="*80)
            print("TESTING EMA CALCULATION")
            print("="*80)
            
            ema = _calculate_ema_ha_close(ha_df, period=10)
            print(f"\n✅ Calculated EMA for {len(ema)} candles")
            print(f"\n📈 Last 3 EMA values:")
            for i in range(-3, 0):
                print(f"   [{i}]: {ema.iloc[i]:.2f}")
            
            # Test conditions
            print("\n" + "="*80)
            print("TESTING BUY/SELL CONDITIONS")
            print("="*80)
            
            is_buy, buy_debug = _check_buy_conditions(ha_df, ema)
            is_sell, sell_debug = _check_sell_conditions(ha_df, ema)
            
            print(f"\n🔍 BUY Signal: {is_buy}")
            print(f"   Debug: {buy_debug}")
            
            print(f"\n🔍 SELL Signal: {is_sell}")
            print(f"   Debug: {sell_debug}")
            
        else:
            print("❌ No data returned")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def test_full_scan():
    """Test full intraday scan"""
    print("\n" + "="*80)
    print("TESTING FULL INTRADAY SCAN")
    print("="*80)
    
    try:
        df = await run_short_term_scan()
        print(f"\n✅ Scan complete!")
        print(f"📊 Found {len(df)} signals")
        
        if not df.empty:
            print(f"\n📋 Signals:")
            print(df.to_string())
        else:
            print("\n⚠️  No signals found")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main test function"""
    # Test single stock first
    await test_single_stock()
    
    # Then test full scan
    print("\n\n")
    await test_full_scan()

if __name__ == "__main__":
    asyncio.run(main())
