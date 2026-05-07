#!/usr/bin/env python3
"""
update_etf_data.py — REAL_ETF_DATA 자동 갱신
-----------------------------------------------
price_history.json 의 일별 종가로부터 월별 수익률을 계산하여
DualMomentumDashboard.jsx 안의 REAL_ETF_DATA 를 업데이트합니다.

워크플로우 순서:
  save_snapshot.py (price_history.json 갱신)
  → update_etf_data.py (JSX 내 REAL_ETF_DATA 갱신)
  → build.js (JSX → dashboard.js 컴파일)
"""

import json, os, re
from datetime import date
from collections import defaultdict

BASE_DIR            = os.path.dirname(os.path.abspath(__file__))
PRICE_HISTORY_FILE  = os.path.join(BASE_DIR, "price_history.json")
JSX_PATH            = os.path.join(BASE_DIR, "DualMomentumDashboard.jsx")

# ══════════════════════════════════════════════════════════════════
# 1. price_history.json → 월별 수익률 계산
# ══════════════════════════════════════════════════════════════════

def calc_monthly_returns(daily_prices):
    """
    {date_str: price, ...} → {YYYY-MM: return, ...}
    각 월의 마지막 거래일 종가를 기준으로 월간 수익률 계산.
    당월(incomplete)은 제외.
    """
    if not daily_prices or len(daily_prices) < 30:
        return {}

    current_ym = date.today().strftime("%Y-%m")

    # 월별로 마지막 거래일 종가 추출
    month_end = {}
    for d in sorted(daily_prices.keys()):
        ym = d[:7]
        month_end[ym] = daily_prices[d]  # 정렬 순서로 마지막 값이 남음

    sorted_months = sorted(month_end.keys())

    # 당월 제외 (아직 완성되지 않은 달)
    complete_months = [ym for ym in sorted_months if ym < current_ym]

    if len(complete_months) < 2:
        return {}

    returns = {}
    for i in range(1, len(complete_months)):
        prev_ym = complete_months[i - 1]
        curr_ym = complete_months[i]
        p0 = month_end[prev_ym]
        p1 = month_end[curr_ym]
        if p0 > 0:
            returns[curr_ym] = round((p1 / p0) - 1, 6)

    return returns


# ══════════════════════════════════════════════════════════════════
# 2. JSX 에서 기존 REAL_ETF_DATA 읽기
# ══════════════════════════════════════════════════════════════════

def read_existing_etf_data(jsx_text):
    """JSX 파일에서 현재 REAL_ETF_DATA 파싱"""
    m = re.search(
        r"/\* __ETF_DATA_START__ \*/\s*const REAL_ETF_DATA\s*=\s*"
        r"(\{[\s\S]*?\})\s*;\s*\n\s*/\* __ETF_DATA_END__ \*/",
        jsx_text,
    )
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        print(f"  기존 REAL_ETF_DATA 파싱 실패: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
# 3. JSX 에 REAL_ETF_DATA 주입
# ══════════════════════════════════════════════════════════════════

def inject_etf_data(jsx_text, etf_data):
    """JSX 파일의 __ETF_DATA_START__ ~ __ETF_DATA_END__ 블록 교체"""
    data_json = json.dumps(etf_data, ensure_ascii=False, separators=(",", ":"))
    new_block = (
        "/* __ETF_DATA_START__ */\n"
        f"const REAL_ETF_DATA = {data_json};\n"
        "/* __ETF_DATA_END__ */"
    )
    updated = re.sub(
        r"/\* __ETF_DATA_START__ \*/[\s\S]*?/\* __ETF_DATA_END__ \*/",
        new_block,
        jsx_text,
    )
    return updated


# ══════════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════════

def main():
    today_str = date.today().strftime("%Y-%m-%d")
    print(f"[{today_str}] REAL_ETF_DATA 갱신 시작\n")

    # ── price_history.json 로드 ──────────────────────────────────
    if not os.path.exists(PRICE_HISTORY_FILE):
        print("  ✗ price_history.json 없음 — 스킵")
        return

    with open(PRICE_HISTORY_FILE, encoding="utf-8") as f:
        price_history = json.load(f)

    # ── JSX 로드 ─────────────────────────────────────────────────
    if not os.path.exists(JSX_PATH):
        print("  ✗ DualMomentumDashboard.jsx 없음 — 스킵")
        return

    with open(JSX_PATH, encoding="utf-8") as f:
        jsx_text = f.read()

    existing = read_existing_etf_data(jsx_text)
    if existing is None:
        print("  ✗ 기존 REAL_ETF_DATA를 찾을 수 없음 — 스킵")
        return

    # ── 기존 데이터의 마지막 날짜 확인 ───────────────────────────
    all_existing_dates = set()
    for dates in existing.values():
        all_existing_dates.update(dates.keys())
    last_existing = max(all_existing_dates) if all_existing_dates else "없음"
    print(f"  기존 REAL_ETF_DATA 마지막: {last_existing}")

    # ── 각 티커별 새 월 데이터 병합 ──────────────────────────────
    added_count = 0
    for ticker, daily in price_history.items():
        new_returns = calc_monthly_returns(daily)
        if not new_returns:
            continue

        if ticker not in existing:
            existing[ticker] = {}

        for ym, ret in new_returns.items():
            if ym not in existing[ticker]:
                existing[ticker][ym] = ret
                added_count += 1

    # ── 결과 확인 ────────────────────────────────────────────────
    all_updated_dates = set()
    for dates in existing.values():
        all_updated_dates.update(dates.keys())
    new_last = max(all_updated_dates) if all_updated_dates else "없음"

    print(f"  갱신 후 REAL_ETF_DATA 마지막: {new_last}")
    print(f"  새로 추가된 데이터 포인트: {added_count}개")

    if added_count == 0:
        print("\n  변경 없음 — JSX 수정 스킵")
        return

    # ── JSX 파일 업데이트 ────────────────────────────────────────
    updated_jsx = inject_etf_data(jsx_text, existing)

    with open(JSX_PATH, "w", encoding="utf-8") as f:
        f.write(updated_jsx)

    print(f"\n✅ REAL_ETF_DATA 갱신 완료 ({last_existing} → {new_last})")


if __name__ == "__main__":
    main()
