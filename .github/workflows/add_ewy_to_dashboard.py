"""
EWY 월별 수익률을 Yahoo Finance에서 가져와
DualMomentumDashboard.jsx의 REAL_ETF_DATA에 삽입하는 스크립트.

GitHub Actions에서 1회 수동 실행용.
"""

import yfinance as yf
import json
import re
import sys

JSX_FILE = "DualMomentumDashboard.jsx"

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
        if prev > 0 and not (hasattr(curr, 'isnan') or curr != curr):
            ret = (curr - prev) / prev
            date_str = closes.index[i].strftime("%Y-%m")
            monthly_returns[date_str] = round(float(ret), 6)

    print(f"✅ EWY 수익률 {len(monthly_returns)}개 수집 완료")
    print(f"   기간: {list(monthly_returns.keys())[0]} ~ {list(monthly_returns.keys())[-1]}")
    return monthly_returns

def insert_ewy_into_jsx(monthly_returns):
    print(f"📂 {JSX_FILE} 읽는 중...")
    with open(JSX_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    real_etf_match = re.search(r'const REAL_ETF_DATA = (\{.*?\});', content, re.DOTALL)
    if not real_etf_match:
        print("❌ REAL_ETF_DATA를 찾지 못했습니다.")
        sys.exit(1)

    try:
        data = json.loads(real_etf_match.group(1))
    except json.JSONDecodeError as e:
        print(f"❌ REAL_ETF_DATA JSON 파싱 실패: {e}")
        sys.exit(1)

    if "EWY" in data:
        print("⚠️  REAL_ETF_DATA에 이미 EWY가 존재합니다. 덮어쓰기합니다.")

    existing_dates = set()
    for ticker_data in data.values():
        existing_dates.update(ticker_data.keys())

    ewy_filtered = {k: v for k, v in monthly_returns.items() if k in existing_dates}
    print(f"   기존 날짜 범위와 교집합: {len(ewy_filtered)}개 (전체 {len(monthly_returns)}개 중)")

    data["EWY"] = ewy_filtered

    new_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    new_const = f"const REAL_ETF_DATA = {new_json};"

    old_const = f"const REAL_ETF_DATA = {real_etf_match.group(1)};"
    new_content = content.replace(old_const, new_const, 1)

    if new_content == content:
        new_content = re.sub(
            r'const REAL_ETF_DATA = \{.*?\};',
            new_const,
            content,
            count=1,
            flags=re.DOTALL
        )

    with open(JSX_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"✅ {JSX_FILE} 업데이트 완료 — EWY {len(ewy_filtered)}개 데이터 포인트 삽입")

if __name__ == "__main__":
    returns = fetch_ewy_monthly_returns()
    insert_ewy_into_jsx(returns)
    print("🎉 완료! DualMomentumDashboard.jsx에 EWY 데이터가 추가되었습니다.")
