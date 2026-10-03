"""Test Minervini SEPA Scanner"""
import asyncio
from services.sepa_scanner import run_sepa_scan

async def main():
    print("\n" + "="*80)
    print("MINERVINI SEPA SCANNER - TOP 10 STOCKS")
    print("="*80)
    
    df, meta = await run_sepa_scan()
    
    print(f"\n📊 Scan Summary:")
    print(f"   Total Scanned: {meta['total_scanned']}")
    print(f"   Total Analyzed: {meta['total_analyzed']}")
    print(f"   Methodology: {meta['methodology']}")
    print(f"   Showing Top: {meta['showing_top']}")
    
    print("\n" + "="*80)
    print("TOP 10 SEPA STOCKS")
    print("="*80)
    
    for idx, row in df.iterrows():
        print(f"\n#{idx+1}. {row['symbol']} - {row['company_name']}")
        print(f"   Score: {row['score']}/100 | Grade: {row['grade']} | Signal: {row['signal']}")
        print(f"   Price: ₹{row['price']:,.2f} ({row['change_pct']:+.2f}%)")
        print(f"\n   📈 Score Breakdown:")
        print(f"      Trend Template:    {row['trend_score']:>2}/25  ({row['trend_detail']['passed']}/8 conditions)")
        print(f"      Relative Strength: {row['rs_score']:>2}/20  (RS Rating: {row['rs_detail']['rs_rating']:.0f})")
        print(f"      VCP Pattern:       {row['vcp_score']:>2}/25  ({row['vcp_detail']['quality']})")
        print(f"      Pivot Point:       {row['pivot_score']:>2}/15  ({row['pivot_detail']['status']})")
        print(f"      Volume Analysis:   {row['volume_score']:>2}/15  ({row['volume_detail']['classification']})")
        
        print(f"\n   💰 Trade Setup:")
        print(f"      Entry:  ₹{row['entry']:,.2f}")
        print(f"      Stop:   ₹{row['stop']:,.2f}  (Risk: {row['risk_pct']:.1f}%)")
        print(f"      Target: ₹{row['target1']:,.2f}  (R:R = 1:{row['risk_reward']:.1f})")
        
        print(f"\n   {'─'*76}")

if __name__ == "__main__":
    asyncio.run(main())
