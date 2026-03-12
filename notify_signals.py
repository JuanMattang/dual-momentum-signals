#!/usr/bin/env python3
import sys, os, re, json, urllib.request, urllib.parse
from datetime import datetime, date

NTFY_TOPIC     = os.environ.get("NTFY_TOPIC", "dual-momentum-alert")
NTFY_SERVER    = "https://ntfy.sh"
CANARY_TICKERS = ["EEM", "HYG"]
STATE_FILE     = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".signal_state.json")
JSX_PATH       = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "DualMomentumDashboard.jsx")

def fetch_canary_via_yfinance(tickers):
    try:
        import yfinance as yf
        import pandas as pd
    except ImportError:
        return None
    result = {}
    today = date.today()
    current_ym = today.strftime("%Y-%m")
    for ticker in tickers:
        try:
            hist = yf.download(ticker, period="10mo", interval="1d", auto_adjust=True, progress=False)
            if hist.empty:
                continue
            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = hist.columns.get_level_values(0)
            close = hist["Close"].dropna()
            monthly_prices = close.resample("ME").last()
            if monthly_prices.index[-1].strftime("%Y-%m") == current_ym:
                monthly_prices = monthly_prices.iloc[:-1]
            if len(monthly_prices) < 2:
                continue
            today_price = float(close.iloc[-1])
            prev_month_end = float(monthly_prices.iloc[-1])
            partial_return = (today_price / prev_month_end) - 1
            complete_returns = list(monthly_prices.pct_change().dropna().values)
            returns_with_partial = complete_returns + [partial_return]
            if len(returns_with_partial) < 7:
                continue
            result[ticker] = returns_with_partial
            prev_ym = monthly_prices.index[-1].strftime("%Y-%m")
            print(f"  ✓ {ticker}: 전월({prev_ym}) 이후 당월 부분수익률 {partial_return*100:+.2f}%")
        except Exception as e:
            print(f"  ✗ {ticker}: {e}")
    return result if result else None

def fetch_canary_via_jsx(jsx_path, tickers):
    if not os.path.exists(jsx_path):
        return None
    jsx = open(jsx_path, encoding="utf-8").read()
    m = re.search(r"/\* __ETF_DATA_START__ \*/\s*const REAL_ETF_DATA\s*=\s*(\{[\s\S]*?\}|\[[\s\S]*?\]|null)\s*;", jsx)
    if not m or m.group(1).strip() == "null":
        return None
    try:
        raw = json.loads(m.group(1))
    except:
        return None
    result = {}
    for ticker in tickers:
        if ticker not in raw:
            continue
        sorted_dates = sorted(raw[ticker].keys())
        result[ticker] = [raw[ticker][d] for d in sorted_dates]
    return result if result else None

def calc_momentum(r):
    if len(r) < 7:
        return None
    r1 = r[-1]
    c3 = 1.0
    for i in range(-3, 0): c3 *= (1 + r[i])
    c6 = 1.0
    for i in range(-6, 0): c6 *= (1 + r[i])
    return 12 * r1 + 4 * (c3 - 1) + 2 * (c6 - 1)

def calc_canary_state(canary_data, date_str):
    scores = {t: calc_momentum(r) for t, r in canary_data.items()}
    valid = [s for s in scores.values() if s is not None]
    bad_count = sum(1 for s in valid if s < 0)
    bil_ratio = 0 if bad_count == 0 else (1.0 if bad_count >= len(valid) else 0.5)
    return {"date": date_str, "scores": scores, "bad_count": bad_count, "bil_ratio": bil_ratio}

def load_prev_state():
    if not os.path.exists(STATE_FILE):
        return None
    try:
        return json.load(open(STATE_FILE, encoding="utf-8"))
    except:
        return None

def save_state(state):
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def send_notification(title, message, priority="default", tags=""):
    url = f"{NTFY_SERVER}/{urllib.parse.quote(NTFY_TOPIC)}"
    req = urllib.request.Request(url, data=message.encode("utf-8"),
        headers={"Title": title.encode(), "Priority": priority.encode(), "Tags": tags.encode()}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"  ✓ 알림 전송 완료 (HTTP {resp.status})")
    except Exception as e:
        print(f"  ✗ 알림 전송 실패: {e}")

def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 시그널 체크 시작\n")
    print("카나리아 데이터 수집 중 (yfinance)...")
    canary_data = fetch_canary_via_yfinance(CANARY_TICKERS)
    data_source = f"실시간 yfinance ({date_str} 기준)"
    if canary_data is None:
        print("\nyfinance 실패 — JSX 정적 데이터 사용\n")
        canary_data = fetch_canary_via_jsx(JSX_PATH, CANARY_TICKERS)
        data_source = "JSX 정적 데이터"
        if canary_data is None:
            print("오류: 데이터를 가져올 수 없습니다.")
            return
    print(f"\n  [데이터 출처] {data_source}\n")
    curr = calc_canary_state(canary_data, date_str)
    prev = load_prev_state()
    save_state(curr)
    print(f"기준 날짜: {curr['date']}")
    for ticker, score in curr["scores"].items():
        if score is not None:
            sign = "🔴 음수 (위험)" if score < 0 else "🟢 양수 (안전)"
            print(f"  {ticker}: {score:+.4f}  {sign}")
    print(f"BIL 비중: {curr['bil_ratio']*100:.0f}%\n")
    if prev is None:
        print("이전 상태 없음 — 기준 상태 저장 완료.")
        send_notification("📊 듀얼모멘텀 모니터링 시작",
            f"시그널 감지 시작\n기준: {curr['date']}\nBIL 비중: {curr['bil_ratio']*100:.0f}%\n출처: {data_source}",
            priority="low", tags="chart_increasing")
        return
    prev_bil = prev.get("bil_ratio", 0)
    curr_bil = curr["bil_ratio"]
    if abs(curr_bil - prev_bil) <= 0.01:
        print(f"변화 없음 — BIL {curr_bil*100:.0f}% 유지")
        return
    score_lines = "\n".join(f"  {t}: {s:+.3f} ({'⚠️ 위험' if s < 0 else '✅ 안전'})" for t, s in curr["scores"].items() if s is not None)
    footer = f"\n기준: {curr['date']}\n출처: {data_source}"
    if prev_bil == 0 and curr_bil > 0:
        title, message, priority, tags = "🔴 카나리아 위험 전환 — 즉시 리밸런싱", f"위험 신호 감지!\nBIL: 0%→{curr_bil*100:.0f}%\n\n{score_lines}{footer}", "urgent", "warning,rotating_light"
    elif prev_bil > 0 and curr_bil == 0:
        title, message, priority, tags = "🟢 위험 해제 — 정상 배분 복귀", f"카나리아 안전 전환!\nBIL: {prev_bil*100:.0f}%→0%\n\n{score_lines}{footer}", "high", "white_check_mark"
    elif curr_bil > prev_bil:
        title, message, priority, tags = "🟠 위험 수위 상승", f"BIL: {prev_bil*100:.0f}%→{curr_bil*100:.0f}%\n\n{score_lines}{footer}", "high", "chart_with_downwards_trend"
    else:
        title, message, priority, tags = "🟡 위험 수위 하락", f"BIL: {prev_bil*100:.0f}%→{curr_bil*100:.0f}%\n\n{score_lines}{footer}", "default", "chart_with_upwards_trend"
    print(f"시그널 변화 감지: {title}")
    send_notification(title, message, priority=priority, tags=tags)

if __name__ == "__main__":
    main()
