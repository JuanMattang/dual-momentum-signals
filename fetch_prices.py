#!/usr/bin/env python3
"""
fetch_prices.py  —  현재가 주입 스크립트
------------------------------------------------------
yfinance 로 23개 ETF 현재가를 가져와서
live_prices.js 에 저장합니다. (GitHub Pages용)

사용법:
    python fetch_prices.py

※ 미국 장중:  당일 실시간 가격 (15분 지연)
※ 장 종료 후: 직전 종가
"""

import sys, os, re, json, shutil, time
from datetime import datetime

try:
    import yfinance as yf
except ImportError:
    print("yfinance 가 설치되어 있지 않습니다.")
    print("  pip install yfinance --break-system-packages")
    sys.exit(1)

# ── 대상 파일 경로 ────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIVE_PRICES_PATH = os.path.join(BASE_DIR, "live_prices.js")

TICKERS = [
    "SPLG", "QQQM", "IWM",
    "EFA",  "EEM",  "VNQ",
    "GLDM", "PDBC", "TLT",
    "TIP",  "LQD",  "HYG",
    "EWJ",  "INDA", "EWZ",
    "EWG",  "EMB",  "MBB",
    "AGG",  "BNDX", "EWY",
    "SHY",  "BIL",
]

def fetch_batch(tickers, retries=3, delay=5):
    """yf.download 로 여러 티커를 한 번에 가져옵니다 (요청 1회)."""
    for attempt in range(retries):
        try:
            raw = yf.download(
                tickers,
                period="5d",
                interval="1d",
                auto_adjust=True,
                progress=False,
                group_by="ticker",
                threads=False,  # 스레드 비활성 → 요청 최소화
            )
            return raw
        except Exception as e:
            if attempt < retries - 1:
                wait = delay * (attempt + 1)
                print(f"  재시도 {attempt+1}/{retries} ({wait}초 후)... ({e})")
                time.sleep(wait)
            else:
                raise

print(f"현재가 일괄 조회 중 ({len(TICKERS)}개 티커, 요청 1회)...")

prices = {}
failed = []

try:
    raw = fetch_batch(TICKERS)

    import pandas as pd

    for ticker in TICKERS:
        try:
            # 멀티인덱스(group_by=ticker) 처리
            if isinstance(raw.columns, pd.MultiIndex):
                close_col = raw[ticker]["Close"] if ticker in raw.columns.get_level_values(0) else None
            else:
                # 티커가 1개일 때는 단순 컬럼
                close_col = raw["Close"] if "Close" in raw.columns else None

            if close_col is not None and not close_col.dropna().empty:
                price = float(close_col.dropna().iloc[-1])
                prices[ticker] = round(price, 4)
                print(f"  ✓ {ticker:6s}: ${price:.4f}")
            else:
                failed.append(ticker)
                print(f"  ✗ {ticker:6s}: 데이터 없음")
        except Exception as e:
            failed.append(ticker)
            print(f"  ✗ {ticker:6s}: {e}")

except Exception as e:
    print(f"\n일괄 조회 실패: {e}")
    print("개별 조회로 폴백 중... (요청 간 1초 간격)")
    for ticker in TICKERS:
        time.sleep(1)
        for attempt in range(3):
            try:
                hist = yf.download(ticker, period="5d", interval="1d",
                                   auto_adjust=True, progress=False)
                if not hist.empty:
                    price = float(hist["Close"].dropna().iloc[-1])
                    prices[ticker] = round(price, 4)
                    print(f"  ✓ {ticker:6s}: ${price:.4f}")
                    break
                else:
                    if attempt == 2:
                        failed.append(ticker)
                        print(f"  ✗ {ticker:6s}: 데이터 없음")
            except Exception as e2:
                if attempt < 2:
                    time.sleep(3 * (attempt + 1))
                else:
                    failed.append(ticker)
                    print(f"  ✗ {ticker:6s}: {e2}")

if not prices:
    print("\n오류: 가격 조회에 모두 실패했습니다.")
    print("잠시 후 다시 시도하거나, 미국 장 시간(한국시간 오후 10시 30분~다음날 오전 5시)에 실행해 보세요.")
    sys.exit(1)

prices["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

print(f"\n수집 완료: {len(prices)-1}/{len(TICKERS)}개")
if failed:
    print(f"실패 티커: {', '.join(failed)}")

# ── live_prices.js 저장 ───────────────────────────────────────────
prices_json = json.dumps(prices, ensure_ascii=False, separators=(",", ":"))
new_block = (
    "/* __PRICE_DATA_START__ */\n"
    f"const LIVE_PRICES = {prices_json};\n"
    "/* __PRICE_DATA_END__ */"
)

with open(LIVE_PRICES_PATH, "w", encoding="utf-8") as f:
    f.write(new_block + "\n")

print(f"\n✅ live_prices.js 업데이트 완료")
print(f"   기준 시각: {prices['updatedAt']}")
print("   브라우저를 새로고침하면 현재가가 주문 시트에 반영됩니다.")
