"""
Diagnostic script to compare local vs cloud scan results
"""
import asyncio
import pandas as pd
from datetime import date
from database import get_conn
from scanner import run_scan
from services.vcp_scanner import run_vcp_scan

async def main():
    print("=" * 80)
    print("DIAGNOSTIC: Comparing Scan Results")
    print("=" * 80)
    
    # Check database cache
    today = date.today().isoformat()
    print(f"\n1. Checking SQLite cache for date: {today}")
    with get_conn() as conn:
        result = conn.execute(
            "SELECT scan_date, length(scan_data) as data_size FROM scan_results_cache"
        ).fetchall()
        if result:
            print(f"   Found {len(result)} cached scan(s):")
            for row in result:
                print(f"   - Date: {row[0]}, Size: {row[1]:,} bytes")
        else:
            print("   No cached scans found")
    
    # Clear cache and force fresh scan
    print("\n2. Clearing cache and running FRESH strategy scan...")
    with get_conn() as conn:
        conn.execute("DELETE FROM scan_results_cache")
        conn.commit()
    
    strategy_df = await run_scan(force=True)
    print(f"   Strategy scan complete: {len(strategy_df)} stocks")
    
    if not strategy_df.empty:
        print(f"\n   Top 10 by best_score:")
        top10 = strategy_df.head(10)[['symbol', 'best_strategy', 'best_score', 'cmp']]
        for idx, row in top10.iterrows():
            print(f"   {idx+1:2d}. {row['symbol']:15s} | {row['best_strategy']:12s} | Score: {row['best_score']:5.1f} | ₹{row['cmp']:8.2f}")
    
    # Run VCP scan
    print("\n3. Running FRESH VCP scan...")
    vcp_df, vcp_charts = await run_vcp_scan()
    print(f"   VCP scan complete: {len(vcp_df)} stocks")
    
    if not vcp_df.empty:
        print(f"\n   VCP Results:")
        print(f"   - All Setups: {len(vcp_df)}")
        breakouts = vcp_df[vcp_df['is_breakout'] == True] if 'is_breakout' in vcp_df.columns else pd.DataFrame()
        print(f"   - Active Breakouts: {len(breakouts)}")
        near_pivot = vcp_df[vcp_df.get('is_breakout', False) == False]
        print(f"   - Near Pivot: {len(near_pivot)}")
        
        print(f"\n   Top 10 VCP stocks:")
        top10_vcp = vcp_df.head(10)[['symbol', 'vcp_score', 'is_breakout', 'cmp']]
        for idx, row in top10_vcp.iterrows():
            status = "BREAKOUT" if row.get('is_breakout', False) else "Near Pivot"
            print(f"   {idx+1:2d}. {row['symbol']:15s} | Score: {row['vcp_score']:5.1f} | {status:12s} | ₹{row['cmp']:8.2f}")
    
    print("\n" + "=" * 80)
    print("COMPARISON COMPLETE")
    print("=" * 80)
    print("\nTo compare with Streamlit Cloud:")
    print("1. Run this script locally: python compare_scans.py")
    print("2. Check the results on Streamlit Cloud")
    print("3. Both should now match (using same fresh data)")
    print("\nIf they still differ, it's likely due to:")
    print("- Different Upstox tokens (local vs cloud secrets)")
    print("- API rate limits or temporary failures")
    print("- Time of day (market hours vs after hours)")

if __name__ == "__main__":
    asyncio.run(main())
