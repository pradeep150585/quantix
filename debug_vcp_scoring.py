"""
Debug script to analyze VCP scanner scoring differences.
Run this to see detailed scoring breakdown for all stocks.
"""
import asyncio
import pandas as pd
from services.scan_runner import run_combined_scan_cached
import streamlit as st

async def debug_vcp_scoring():
    """Analyze VCP scoring without UI filtering."""
    from services.vcp_scanner import run_vcp_scan
    
    print("\n" + "="*80)
    print("VCP SCANNER DEBUG - FULL RESULTS (NO FILTERING)")
    print("="*80 + "\n")
    
    vcp_df, vcp_charts = await run_vcp_scan()
    
    if vcp_df.empty:
        print("❌ No VCP setups found!")
        return
    
    print(f"✅ Total VCP setups found: {len(vcp_df)}")
    print(f"   Score range: {vcp_df['vcp_score'].min():.1f} to {vcp_df['vcp_score'].max():.1f}")
    print(f"   Average score: {vcp_df['vcp_score'].mean():.1f}")
    
    # Analyze by score ranges
    score_ranges = [
        ("0-30", 0, 30),
        ("31-50", 31, 50),
        ("51-70", 51, 70),
        ("71-100", 71, 100)
    ]
    
    print("\n📊 SCORE DISTRIBUTION:")
    print("-" * 80)
    for label, min_score, max_score in score_ranges:
        filtered = vcp_df[(vcp_df['vcp_score'] > min_score) & (vcp_df['vcp_score'] <= max_score)]
        breakouts = filtered[filtered['is_breakout'] == True]
        print(f"{label:10s}: {len(filtered):3d} setups, {len(breakouts):3d} breakouts")
    
    # Show all breakouts regardless of score
    all_breakouts = vcp_df[vcp_df['is_breakout'] == True]
    print(f"\n🚀 TOTAL ACTIVE BREAKOUTS: {len(all_breakouts)}")
    
    if not all_breakouts.empty:
        print("\n📋 ALL BREAKOUTS (regardless of score):")
        print("-" * 80)
        for idx, row in all_breakouts.iterrows():
            print(f"{row['symbol']:12s} Score: {row['vcp_score']:5.1f}  "
                  f"CMP: ₹{row['cmp']:8.2f}  "
                  f"Vol Ratio: {row['volume_ratio']:.2f}x  "
                  f"Contractions: {row['contractions']}")
    
    # Analyze stocks filtered out by score > 30 threshold
    low_score = vcp_df[vcp_df['vcp_score'] <= 30]
    low_score_breakouts = low_score[low_score['is_breakout'] == True]
    
    print(f"\n⚠️  STOCKS FILTERED OUT (score ≤ 30): {len(low_score)}")
    print(f"    Breakouts lost due to low score: {len(low_score_breakouts)}")
    
    if not low_score_breakouts.empty:
        print("\n❌ BREAKOUTS HIDDEN BY SCORE FILTER:")
        print("-" * 80)
        for idx, row in low_score_breakouts.iterrows():
            print(f"{row['symbol']:12s} Score: {row['vcp_score']:5.1f}  "
                  f"CMP: ₹{row['cmp']:8.2f}  "
                  f"Vol Ratio: {row['volume_ratio']:.2f}x")
            print(f"              Squeeze: {row['squeeze']}  "
                  f"Vol Dry-up: {row['vol_dryup']}  "
                  f"Contractions: {row['contractions']}")
    
    # Near pivot analysis
    near_pivot = vcp_df[(vcp_df['is_breakout'] == False) & (vcp_df['dist_52h_pct'] >= -20)]
    near_pivot_filtered = near_pivot[near_pivot['vcp_score'] > 30]
    
    print(f"\n📍 NEAR PIVOT ANALYSIS:")
    print("-" * 80)
    print(f"Total near pivot: {len(near_pivot)}")
    print(f"After score filter (>30): {len(near_pivot_filtered)}")
    
    # Score components analysis
    print(f"\n🔍 SCORE COMPONENT ANALYSIS:")
    print("-" * 80)
    print(f"Stocks with squeeze: {len(vcp_df[vcp_df['squeeze'] == True])}")
    print(f"Stocks with vol dry-up: {len(vcp_df[vcp_df['vol_dryup'] == True])}")
    print(f"Stocks with ≥3 contractions: {len(vcp_df[vcp_df['contractions'] >= 3])}")
    print(f"Stocks with breakout: {len(vcp_df[vcp_df['is_breakout'] == True])}")
    
    return vcp_df


if __name__ == "__main__":
    # For standalone execution
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        pass
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        df = loop.run_until_complete(debug_vcp_scoring())
        
        # Save detailed CSV for analysis
        if df is not None and not df.empty:
            output_file = "vcp_debug_full_results.csv"
            df.to_csv(output_file, index=False)
            print(f"\n💾 Full results saved to: {output_file}")
    finally:
        loop.close()
