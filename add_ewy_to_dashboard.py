import yfinance as yf
import json
import sys

def fetch_ewy_monthly_returns():
    print("📥 EWY 월별 데이터 수집 중...")
    df = yf.download("EWY", start="2000-01-01", interval="1mo",
                     auto_adjust=True, progress=False)

    if df.empty:
        print("❌ EWY 데이터를 가져오지 못했습니다.")
        sys.exit(1)

    closes = df["Close"].squeeze()
    monthly_returns = {}

    for i in range(1, len(closes)):
        prev = closes.iloc[i - 1]
        curr = closes.iloc[i]
        if prev > 0 and not (curr != curr):
            ret = (curr - prev) / prev
            date_str = closes.index[i].strftime("%Y-%m")
            monthly_returns[date_str] = round(float(ret), 6)

    print(f"✅ EWY 수익률 {len(monthly_returns)}개 수집 완료")
    print(f"   기간: {list(monthly_returns.keys())[0]} ~ {list(monthly_returns.keys())[-1]}")
    return monthly_returns

if __name__ == "__main__":
    returns = fetch_ewy_monthly_returns()
    with open("ewy_returns.json", "w") as f:
        json.dump(returns, f, separators=(",", ":"))
    print("💾 ewy_returns.json 저장 완료")
