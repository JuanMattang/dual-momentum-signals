#!/usr/bin/env python3
"""
save_snapshot.py — DAA 포트폴리오 스냅샷 저장
-----------------------------------------------
매일 notify_signals.py 실행 후 자동으로 실행됩니다.

- 정기: 매월 1일 (직전 월말 종가 기준)
- 수시: BIL 비중 변경 시
- 오늘: 매일 당일 포트폴리오 저장

결과물: rebalancing_history.json + rebalancing_history.js
"""
import json, os
from datetime import date

BASE_DIR                 = os.path.dirname(os.path.abspath(__file__))
PRICE_HISTORY_FILE       = os.path.join(BASE_DIR, "price_history.json")
REBALANCING_HISTORY_FILE = os.path.join(BASE_DIR, "rebalancing_history.json")
REBALANCING_HISTORY_JS   = os.path.join(BASE_DIR, "rebalancing_history.js")
SIGNAL_STATE_FILE        = os.path.join(BASE_DIR, ".signal_state.json")

# ══════════════════════════════════════════════════════════════════
# DAA 유니버스 정의
# ══════════════════════════════════════════════════════════════════
ASSETS = [
    {"ticker": "SPLG",  "name": "미국 대형주",      "group": "미국주식"},
    {"ticker": "QQQM",  "name": "미국 나스닥100",   "group": "미국주식"},
    {"ticker": "IWM",   "name": "미국 소형주",      "group": "미국주식"},
    {"ticker": "EFA",   "name": "선진국 주식",      "group": "선진국주식"},
    {"ticker": "EEM",   "name": "신흥국 주식",      "group": "신흥국주식"},
    {"ticker": "VNQ",   "name": "미국 리츠",        "group": "대체"},
    {"ticker": "GLDM",  "name": "금",              "group": "대체"},
    {"ticker": "PDBC",  "name": "원자재",          "group": "대체"},
    {"ticker": "TLT",   "name": "미국 장기국채",    "group": "채권"},
    {"ticker": "TIP",   "name": "물가연동채",       "group": "채권"},
    {"ticker": "LQD",   "name": "투자등급 회사채",  "group": "채권"},
    {"ticker": "HYG",   "name": "하이일드 채권",    "group": "채권"},
    {"ticker": "EWJ",   "name": "일본 주식",        "group": "선진국주식"},
    {"ticker": "INDA",  "name": "인도 주식",        "group": "신흥국주식"},
    {"ticker": "EWZ",   "name": "브라질 주식",      "group": "신흥국주식"},
    {"ticker": "EWG",   "name": "독일 주식",        "group": "선진국주식"},
    {"ticker": "EMB",   "name": "신흥국 국채",      "group": "채권"},
    {"ticker": "MBB",   "name": "미국 모기지채",    "group": "채권"},
    {"ticker": "AGG",   "name": "미국 종합채권",    "group": "채권"},
    {"ticker": "BNDX",  "name": "글로벌 채권",      "group": "채권"},
    {"ticker": "EWY",   "name": "한국 주식",        "group": "신흥국주식"},
    {"ticker": "SHY",   "name": "미국 단기국채",    "group": "현금"},
    {"ticker": "BIL",   "name": "초단기채(현금)",   "group": "현금"},
]
ALL_TICKERS = [a["ticker"] for a in ASSETS]
ASSET_MAP   = {a["ticker"]: a for a in ASSETS}

# 기본 DAA 설정 (대시보드 기본값과 동일)
LOOKBACK = 11
TOP_N    = 5
CAT_CAPS = {
    "미국주식":   0.50,
    "선진국주식": 0.50,
    "신흥국주식": 0.40,
    "대체":       0.40,
    "채권":       0.60,
}

# ══════════════════════════════════════════════════════════════════
# 유틸리티
# ══════════════════════════════════════════════════════════════════

def load_price_history():
    if not os.path.exists(PRICE_HISTORY_FILE):
        return {}
    try:
        return json.load(open(PRICE_HISTORY_FILE, encoding="utf-8"))
    except:
        return {}

def save_price_history(history):
    json.dump(history, open(PRICE_HISTORY_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))

def update_universe_prices(history):
    """전체 유니버스 가격 업데이트 (없는 티커만 전체 다운로드, 나머지는 오늘 종가만)"""
    try:
        import yfinance as yf
        import pandas as pd
    except ImportError:
        print("  yfinance 미설치")
        return history

    today_str = date.today().strftime("%Y-%m-%d")
    missing   = [t for t in ALL_TICKERS
                 if t not in history or len(history.get(t, {})) < 500]

    if missing:
        print(f"  신규 티커 전체 히스토리 다운로드: {missing}")

    for ticker in ALL_TICKERS:
        period = "max" if ticker in missing else "10d"
        try:
            hist = yf.download(ticker, period=period, interval="1d",
                               auto_adjust=True, progress=False)
            if hist.empty:
                continue
            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = hist.columns.get_level_values(0)
            close = hist["Close"].dropna()
            if ticker not in history:
                history[ticker] = {}
            added = 0
            for dt, price in close.items():
                dk = dt.strftime("%Y-%m-%d")
                if dk not in history[ticker] or dk == today_str:
                    history[ticker][dk] = round(float(price), 4)
                    added += 1
            latest = max(history[ticker].keys()) if history[ticker] else "-"
            if added > 0 or ticker in missing:
                print(f"    ✓ {ticker}: {len(history[ticker])}일치 (최신: {latest})")
        except Exception as e:
            print(f"    ✗ {ticker}: {e}")
    return history


def monthly_returns(history, ticker):
    """일별 가격 → 월별 수익률 (당월 partial 포함)"""
    if ticker not in history or len(history[ticker]) < 30:
        return None
    prices     = history[ticker]
    sorted_d   = sorted(prices.keys())
    current_ym = date.today().strftime("%Y-%m")

    monthly = {}
    for d in sorted_d:
        monthly[d[:7]] = prices[d]

    sorted_m   = sorted(monthly.keys())
    complete_m = [ym for ym in sorted_m if ym < current_ym]

    if len(complete_m) < LOOKBACK + 2:
        return None

    returns = []
    for i in range(1, len(complete_m)):
        p0 = monthly[complete_m[i-1]]
        p1 = monthly[complete_m[i]]
        returns.append((p1 / p0) - 1)

    today_p   = monthly.get(current_ym, monthly[complete_m[-1]])
    partial_r = (today_p / monthly[complete_m[-1]]) - 1
    return returns + [partial_r]


def lookback_score(returns_list):
    """LOOKBACK 기간 누적 수익률 (마지막 원소 = 당월 partial)"""
    if returns_list is None or len(returns_list) < LOOKBACK:
        return None
    cum = 1.0
    for r in returns_list[-LOOKBACK:]:
        cum *= (1 + r)
    return cum - 1


# ══════════════════════════════════════════════════════════════════
# DAA 포트폴리오 계산
# ══════════════════════════════════════════════════════════════════

def compute_daa_portfolio(history, bil_ratio):
    """
    현재 가격 기준 DAA 포트폴리오 계산
    Returns: (portfolio_list, all_scores_list)
    """
    # 전 종목 스코어 계산
    scores = {}
    for asset in ASSETS:
        t = asset["ticker"]
        if t in ("BIL", "SHY"):
            continue
        r = monthly_returns(history, t)
        s = lookback_score(r)
        if s is not None:
            scores[t] = s

    # BIL 기준 점수
    bil_r     = monthly_returns(history, "BIL")
    bil_score = lookback_score(bil_r) or 0.0

    # Top-N 선택 (BIL 이상 점수만)
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    selected      = [(t, s) for t, s in sorted_scores[:TOP_N] if s > bil_score]

    # 기본 비중 (균등)
    wts = {}
    if not selected:
        wts["SHY"] = 1.0
    else:
        w = 1.0 / len(selected)
        for t, _ in selected:
            wts[t] = w

    # 카테고리 캡 적용
    group_totals = {}
    for t, w in wts.items():
        g = ASSET_MAP.get(t, {}).get("group", "기타")
        group_totals[g] = group_totals.get(g, 0) + w

    excess = 0.0
    for g, total in group_totals.items():
        if g == "현금":
            continue
        cap = CAT_CAPS.get(g, 1.0)
        if total > cap:
            scale = cap / total
            for t in list(wts.keys()):
                if ASSET_MAP.get(t, {}).get("group") == g:
                    excess += wts[t] * (1 - scale)
                    wts[t] *= scale
    if excess > 0:
        wts["BIL"] = wts.get("BIL", 0) + excess

    # 카나리아 BIL 오버레이
    if bil_ratio > 0:
        remaining = 1.0 - bil_ratio
        for t in list(wts.keys()):
            wts[t] = wts[t] * remaining
        wts["BIL"] = wts.get("BIL", 0) + bil_ratio

    # 포트폴리오 리스트 (비중 순)
    portfolio = []
    for t, w in sorted(wts.items(), key=lambda x: -x[1]):
        entry = {
            "ticker": t,
            "name":   ASSET_MAP.get(t, {}).get("name", t),
            "weight": round(w, 4),
        }
        if t in scores:
            entry["score"] = round(scores[t], 4)
        portfolio.append(entry)

    # 전체 유니버스 스코어 (참고용, Top 순)
    all_scores = [
        {"ticker": t,
         "name":   ASSET_MAP.get(t, {}).get("name", t),
         "score":  round(s, 4)}
        for t, s in sorted_scores
    ]

    return portfolio, all_scores


# ══════════════════════════════════════════════════════════════════
# 이력 관리
# ══════════════════════════════════════════════════════════════════

def load_rebalancing_history():
    if not os.path.exists(REBALANCING_HISTORY_FILE):
        return {"last_regular": None, "last_emergency": None,
                "today": None, "history": []}
    try:
        return json.load(open(REBALANCING_HISTORY_FILE, encoding="utf-8"))
    except:
        return {"last_regular": None, "last_emergency": None,
                "today": None, "history": []}

def save_rebalancing_history(data):
    # JSON 저장
    json.dump(data, open(REBALANCING_HISTORY_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    # JS 파일 생성 (대시보드에서 window.REBALANCING_HISTORY로 접근)
    js = ("/* AUTO-GENERATED by save_snapshot.py — DO NOT EDIT */\n"
          f"window.REBALANCING_HISTORY = {json.dumps(data, ensure_ascii=False, separators=(',',':'))};\n")
    open(REBALANCING_HISTORY_JS, "w", encoding="utf-8").write(js)
    print(f"  rebalancing_history.json + .js 저장 완료")

def load_signal_state():
    if not os.path.exists(SIGNAL_STATE_FILE):
        return None
    try:
        return json.load(open(SIGNAL_STATE_FILE, encoding="utf-8"))
    except:
        return None


# ══════════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════════

def main():
    today     = date.today()
    today_str = today.strftime("%Y-%m-%d")
    print(f"[{today_str}] 포트폴리오 스냅샷 시작\n")

    # ── 가격 히스토리 업데이트 (전체 유니버스) ────────────────────
    print("전체 유니버스 가격 업데이트...")
    history = load_price_history()
    history = update_universe_prices(history)
    save_price_history(history)
    print()

    # ── 신호 상태 읽기 (notify_signals.py 결과) ───────────────────
    signal_state   = load_signal_state()
    bil_ratio      = signal_state.get("bil_ratio", 0.0) if signal_state else 0.0
    canary_info    = {}
    if signal_state:
        for t, score in signal_state.get("scores", {}).items():
            z = signal_state.get("z_scores", {}).get(t)
            canary_info[t] = {
                "score":   round(score, 4) if score is not None else None,
                "z_score": round(z, 4)     if z     is not None else None,
            }

    # ── DAA 포트폴리오 계산 ───────────────────────────────────────
    print(f"DAA 포트폴리오 계산 (BIL: {bil_ratio*100:.1f}%)...")
    portfolio, all_scores = compute_daa_portfolio(history, bil_ratio)
    tickers_str = ", ".join(
        f"{p['ticker']} {p['weight']*100:.0f}%" for p in portfolio
    )
    print(f"  결과: {tickers_str}\n")

    # ── 스냅샷 구성 ───────────────────────────────────────────────
    rh         = load_rebalancing_history()
    today_snap = {
        "date":      today_str,
        "type":      "오늘",
        "canary":    canary_info,
        "bil_ratio": round(bil_ratio, 4),
        "portfolio": portfolio,
        "all_scores": all_scores,
    }
    rh["today"] = today_snap

    # ── 정기/수시 판단 ────────────────────────────────────────────
    is_first_of_month = (today.day == 1)

    # 직전 스냅샷 BIL 비중
    last_snap_bil = None
    if rh["last_emergency"]:
        last_snap_bil = rh["last_emergency"]["bil_ratio"]
    elif rh["last_regular"]:
        last_snap_bil = rh["last_regular"]["bil_ratio"]

    bil_changed = (last_snap_bil is None or
                   abs(bil_ratio - last_snap_bil) >= 0.20)

    if is_first_of_month or bil_changed:
        snap_type = "정기" if is_first_of_month else "수시"
        record    = {
            "date":       today_str,
            "type":       snap_type,
            "canary":     canary_info,
            "bil_ratio":  round(bil_ratio, 4),
            "portfolio":  portfolio,
            "all_scores": all_scores,
            "settings":   {"lookback": LOOKBACK, "topN": TOP_N},
        }
        if snap_type == "정기":
            rh["last_regular"]   = record
        else:
            rh["last_emergency"] = record

        rh.setdefault("history", [])
        rh["history"].insert(0, record)
        rh["history"] = rh["history"][:20]  # 최대 20개 유지

        print(f"  [{snap_type}] 스냅샷 저장: {today_str}")
    else:
        print(f"  변화 없음 — 오늘 스냅샷만 갱신")

    save_rebalancing_history(rh)


if __name__ == "__main__":
    main()
