#!/usr/bin/env python3
"""
notify_signals.py  —  리밸런싱 시그널 감지 & 핸드폰 알림
------------------------------------------------------
매일 자동 실행하면 카나리아 상태 변화를 핸드폰으로 알려줍니다.

★ v3 업그레이드: price_history.json 누적 방식
  - 최초 실행 시 yfinance로 전체 히스토리 다운로드 (1회)
  - 이후 매일 오늘 종가만 추가
  - 월별 수익률을 직접 계산 → 대시보드와 동일한 데이터 기반

■ 최초 설정 (1회)
  1. yfinance 설치
       pip install yfinance --break-system-packages
  2. 핸드폰에 'ntfy' 앱 설치
  3. 앱에서 구독(Subscribe) → 토픽 이름 입력
  4. 아래 NTFY_TOPIC 에 같은 이름 설정
"""
import sys, os, re, json, urllib.request, urllib.parse
from datetime import datetime, date

# ══════════════════════════════════════════════════════════════════
# ★ 설정 — 여기만 수정하세요
# ══════════════════════════════════════════════════════════════════
NTFY_TOPIC         = os.environ.get("NTFY_TOPIC", "dual-momentum-alert")
NTFY_SERVER        = "https://ntfy.sh"
CANARY_TICKERS     = ["AGG", "EEM"]

BASE_DIR           = os.path.dirname(os.path.abspath(__file__))
STATE_FILE         = os.path.join(BASE_DIR, ".signal_state.json")
PRICE_HISTORY_FILE = os.path.join(BASE_DIR, "price_history.json")

JSX_PATH = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.path.join(BASE_DIR, "DualMomentumDashboard.jsx")
)

# ══════════════════════════════════════════════════════════════════
# ── 1. price_history.json 관리 ────────────────────────────────────
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

def update_price_history(tickers, history):
    """
    price_history에 데이터가 없거나 부족하면 전체 히스토리 다운로드(1회).
    이후에는 최근 며칠치만 받아서 오늘 종가를 추가.
    """
    try:
        import yfinance as yf
        import pandas as pd
    except ImportError:
        print("  yfinance 미설치. pip install yfinance --break-system-packages")
        return history

    today_str = date.today().strftime("%Y-%m-%d")
    MIN_DAYS  = 500  # 이 이하면 전체 재다운로드

    needs_bootstrap = any(
        ticker not in history or len(history.get(ticker, {})) < MIN_DAYS
        for ticker in tickers
    )

    period = "max" if needs_bootstrap else "10d"
    if needs_bootstrap:
        print("  전체 히스토리 다운로드 중 (최초 1회, 잠시 기다려주세요)...")
    else:
        print("  오늘 종가 업데이트 중...")

    for ticker in tickers:
        try:
            hist = yf.download(
                ticker, period=period, interval="1d",
                auto_adjust=True, progress=False
            )
            if hist.empty:
                print(f"  ✗ {ticker}: 데이터 없음")
                continue

            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = hist.columns.get_level_values(0)

            close = hist["Close"].dropna()

            if ticker not in history:
                history[ticker] = {}

            added = 0
            for dt, price in close.items():
                date_key = dt.strftime("%Y-%m-%d")
                if date_key not in history[ticker]:
                    history[ticker][date_key] = round(float(price), 4)
                    added += 1
                elif date_key == today_str:
                    # 오늘 값은 항상 최신으로 갱신
                    history[ticker][date_key] = round(float(price), 4)

            total  = len(history[ticker])
            latest = max(history[ticker].keys())
            print(f"  ✓ {ticker}: 총 {total}일치 (최신: {latest}, 신규: {added}일)")

        except Exception as e:
            print(f"  ✗ {ticker}: {e}")

    return history


def monthly_returns_from_history(history, ticker):
    """
    일별 가격 히스토리에서 월별 수익률 리스트 계산.
    - 완전한 달: 해당 월의 마지막 거래일 종가 기준
    - 당월 partial: 오늘 종가 / 전월 말 종가 - 1
    반환: [r_과거, ..., r_전월, r_당월partial]
    """
    if ticker not in history or len(history[ticker]) < 30:
        return None

    prices       = history[ticker]
    sorted_dates = sorted(prices.keys())
    current_ym   = date.today().strftime("%Y-%m")

    # 월별 마지막 거래일 종가 추출
    monthly = {}
    for d in sorted_dates:
        ym = d[:7]
        monthly[ym] = prices[d]  # 같은 달이면 나중 날짜가 덮어씀 → 월말 종가

    sorted_months   = sorted(monthly.keys())
    complete_months = [ym for ym in sorted_months if ym < current_ym]

    if len(complete_months) < 14:
        print(f"  ✗ {ticker}: 완전한 월 데이터 부족 ({len(complete_months)}개월)")
        return None

    # 완전한 달의 월별 수익률
    complete_returns = []
    for i in range(1, len(complete_months)):
        prev_p = monthly[complete_months[i-1]]
        curr_p = monthly[complete_months[i]]
        complete_returns.append((curr_p / prev_p) - 1)

    # 당월 partial return
    last_complete_price = monthly[complete_months[-1]]
    today_price         = monthly.get(current_ym, last_complete_price)
    partial_return      = (today_price / last_complete_price) - 1

    return complete_returns + [partial_return]


# ══════════════════════════════════════════════════════════════════
# ── 2. JSX fallback (price_history 없을 때) ───────────────────────
# ══════════════════════════════════════════════════════════════════

def fetch_canary_via_jsx(jsx_path, tickers):
    if not os.path.exists(jsx_path):
        return None
    jsx = open(jsx_path, encoding="utf-8").read()
    m = re.search(
        r"/\* __ETF_DATA_START__ \*/\s*const REAL_ETF_DATA\s*=\s*"
        r"(\{[\s\S]*?\}|\[[\s\S]*?\]|null)\s*;",
        jsx
    )
    if not m or m.group(1).strip() == "null":
        return None
    try:
        raw = json.loads(m.group(1))
    except Exception as e:
        print(f"  JSX 파싱 오류: {e}")
        return None
    result = {}
    for ticker in tickers:
        if ticker not in raw:
            continue
        sorted_dates = sorted(raw[ticker].keys())
        result[ticker] = [raw[ticker][d] for d in sorted_dates]
    return result if result else None


# ══════════════════════════════════════════════════════════════════
# ── 3. 모멘텀 & Z-Score 계산 ─────────────────────────────────────
# ══════════════════════════════════════════════════════════════════

def calc_momentum(returns_list):
    """DAA 13612W 공식: 12×r1 + 4×r3 + 2×r6 + 1×r12"""
    r = returns_list
    if len(r) < 13:
        return None
    r1 = r[-1]
    c3 = 1.0
    for i in range(-3, 0):
        c3 *= (1 + r[i])
    c6 = 1.0
    for i in range(-6, 0):
        c6 *= (1 + r[i])
    c12 = 1.0
    for i in range(-12, 0):
        c12 *= (1 + r[i])
    return 12 * r1 + 4 * (c3 - 1) + 2 * (c6 - 1) + 1 * (c12 - 1)


def calc_z_score(returns_list, window=36):
    """
    슬라이딩 윈도우로 과거 모멘텀 스코어를 구하고
    현재 스코어를 그 분포 기준으로 정규화.
    """
    n      = len(returns_list)
    scores = []
    for end in range(13, n):
        sub = returns_list[:end]
        s   = calc_momentum(sub)
        if s is not None:
            scores.append(s)
        if len(scores) >= window:
            break
    if len(scores) < 6:
        return None
    curr = calc_momentum(returns_list)
    if curr is None:
        return None
    mean = sum(scores) / len(scores)
    std  = (sum((x - mean) ** 2 for x in scores) / len(scores)) ** 0.5
    if std < 1e-10:
        return 0.0
    return (curr - mean) / std


def z_score_to_bil(z, safe=-0.5, panic=-2.0):
    if z is None or z >= safe:
        return 0.0
    if z <= panic:
        return 1.0
    return (safe - z) / (safe - panic)


# ══════════════════════════════════════════════════════════════════
# ── 4. 카나리아 상태 계산 ─────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════

Z_SCORE_MODE   = True
Z_SCORE_WINDOW = 36
Z_SCORE_SAFE   = -0.5
Z_SCORE_PANIC  = -2.0
Z_GUARDRAIL    = 0.05


def calc_canary_state(canary_data, date_str, prev_bil_ratio=0.0):
    scores    = {t: calc_momentum(r) for t, r in canary_data.items()}
    valid     = [s for s in scores.values() if s is not None]
    bad_count = sum(1 for s in valid if s < 0)

    if Z_SCORE_MODE:
        z_scores   = {}
        bil_ratios = []
        for t, r in canary_data.items():
            z = calc_z_score(r, Z_SCORE_WINDOW)
            z_scores[t] = z
            bil_ratios.append(z_score_to_bil(z, Z_SCORE_SAFE, Z_SCORE_PANIC))
        raw_bil   = sum(bil_ratios) / len(bil_ratios) if bil_ratios else 0.0
        bil_ratio = prev_bil_ratio if abs(raw_bil - prev_bil_ratio) < Z_GUARDRAIL else raw_bil
    else:
        bil_ratio = (0 if bad_count == 0 else
                     1.0 if bad_count >= len(valid) else 0.5)
        z_scores  = {}
        raw_bil   = bil_ratio

    return {
        "date":      date_str,
        "scores":    scores,
        "z_scores":  z_scores,
        "bad_count": bad_count,
        "bil_ratio": bil_ratio,
        "raw_bil":   raw_bil,
        "mode":      "zscore" if Z_SCORE_MODE else "binary",
    }


# ══════════════════════════════════════════════════════════════════
# ── 5. 상태 저장/불러오기 & 알림 ──────────────────────────────────
# ══════════════════════════════════════════════════════════════════

def load_prev_state():
    if not os.path.exists(STATE_FILE):
        return None
    try:
        return json.load(open(STATE_FILE, encoding="utf-8"))
    except:
        return None

def save_state(state):
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

def send_notification(title, message, priority="default", tags=""):
    url  = f"{NTFY_SERVER}/{urllib.parse.quote(NTFY_TOPIC)}"
    data = message.encode("utf-8")
    headers = {
        "Title":    title.encode("utf-8"),
        "Priority": priority.encode("utf-8"),
        "Tags":     tags.encode("utf-8"),
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"  ✓ 알림 전송 완료 (HTTP {resp.status})")
    except Exception as e:
        print(f"  ✗ 알림 전송 실패: {e}")


# ══════════════════════════════════════════════════════════════════
# ── 메인 ──────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════

def main():
    now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
    date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"[{now_str}] 시그널 체크 시작\n")

    # ── 가격 히스토리 업데이트 ───────────────────────────────────
    print("가격 히스토리 업데이트 중...")
    history = load_price_history()
    history = update_price_history(CANARY_TICKERS, history)
    save_price_history(history)
    print()

    # ── 월별 수익률 계산 ─────────────────────────────────────────
    canary_data = {}
    for ticker in CANARY_TICKERS:
        returns = monthly_returns_from_history(history, ticker)
        if returns is not None:
            canary_data[ticker] = returns
            print(f"  {ticker}: {len(returns)}개월치 수익률 준비 완료")

    data_source = f"price_history.json ({date_str} 기준)"

    # fallback: JSX 정적 데이터
    if not canary_data:
        print("\nprice_history 실패 — JSX 정적 데이터로 fallback\n")
        canary_data = fetch_canary_via_jsx(JSX_PATH, CANARY_TICKERS)
        data_source = "JSX 정적 데이터"
        if not canary_data:
            print("오류: 데이터를 가져올 수 없습니다.")
            return

    print(f"\n  [데이터 출처] {data_source}\n")

    # ── 카나리아 상태 계산 ──────────────────────────────────────
    prev           = load_prev_state()
    prev_bil_ratio = prev.get("bil_ratio", 0.0) if prev else 0.0
    curr           = calc_canary_state(canary_data, date_str, prev_bil_ratio)
    save_state(curr)

    # ── 점수 출력 ───────────────────────────────────────────────
    print(f"기준 날짜: {curr['date']}")
    for ticker, score in curr["scores"].items():
        if score is not None:
            z     = curr["z_scores"].get(ticker)
            z_str = f"  Z={z:+.3f}" if z is not None else ""
            sign  = "🔴 음수 (위험)" if score < 0 else "🟢 양수 (안전)"
            print(f"  {ticker}: {score:+.4f}  {sign}{z_str}")
        else:
            print(f"  {ticker}: N/A")
    print(f"BIL 비중: {curr['bil_ratio']*100:.1f}%\n")

    # ── 상태 변화 감지 & 알림 ───────────────────────────────────
    if prev is None:
        print("이전 상태 없음 — 기준 상태 저장 완료.\n")
        send_notification(
            "📊 듀얼모멘텀 모니터링 시작",
            f"시그널 감지 시작\n기준: {curr['date']}\n"
            f"BIL 비중: {curr['bil_ratio']*100:.0f}%\n출처: {data_source}",
            priority="low", tags="chart_increasing"
        )
        return

    prev_bil = prev.get("bil_ratio", 0)
    curr_bil = curr["bil_ratio"]
    changed  = abs(curr_bil - prev_bil) > 0.01

    score_lines = "\n".join(
        f"  {t}: {s:+.3f}  ({'⚠️ 위험' if s < 0 else '✅ 안전'})"
        + (f"  Z={curr['z_scores'].get(t):+.3f}"
           if curr["z_scores"].get(t) is not None else "")
        for t, s in curr["scores"].items() if s is not None
    )

    if not changed:
        print(f"변화 없음 — BIL {curr_bil*100:.1f}% 유지")
        status = "🔴 위험" if curr_bil > 0 else "🟢 안전"
        send_notification(
            f"📊 일일 시그널 요약 — {status}",
            f"변화 없음 (시스템 정상 작동 중)\n"
            f"BIL 비중: {curr_bil*100:.1f}%\n\n"
            f"카나리아 점수:\n{score_lines}\n\n"
            f"기준: {curr['date']}\n출처: {data_source}",
            priority="min", tags="white_check_mark"
        )
        return

    footer = f"\n기준: {curr['date']}\n출처: {data_source}"

    if prev_bil == 0 and curr_bil > 0:
        title         = "🔴 카나리아 위험 전환 — 즉시 리밸런싱"
        message       = (f"위험 신호 감지!\nBIL 비중: 0% → {curr_bil*100:.1f}%\n\n"
                         f"점수:\n{score_lines}{footer}")
        priority, tags = "urgent", "warning,rotating_light"
    elif prev_bil > 0 and curr_bil == 0:
        title         = "🟢 카나리아 위험 해제 — 정상 배분 복귀"
        message       = (f"카나리아 모두 안전 전환!\nBIL 비중: {prev_bil*100:.1f}% → 0%\n\n"
                         f"점수:\n{score_lines}{footer}")
        priority, tags = "high", "white_check_mark,chart_increasing"
    elif curr_bil > prev_bil:
        title         = "🟠 위험 수위 상승 — 리밸런싱 권고"
        message       = (f"BIL 비중 상승: {prev_bil*100:.1f}% → {curr_bil*100:.1f}%\n\n"
                         f"점수:\n{score_lines}{footer}")
        priority, tags = "high", "chart_with_downwards_trend"
    else:
        title         = "🟡 위험 수위 하락"
        message       = (f"BIL 비중 감소: {prev_bil*100:.1f}% → {curr_bil*100:.1f}%\n\n"
                         f"점수:\n{score_lines}{footer}")
        priority, tags = "default", "chart_with_upwards_trend"

    print(f"시그널 변화 감지: {title}")
    send_notification(title, message, priority=priority, tags=tags)


if __name__ == "__main__":
    main()
