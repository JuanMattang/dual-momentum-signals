#!/usr/bin/env python3
"""
notify_signals.py  —  리밸런싱 시그널 감지 & 핸드폰 알림
------------------------------------------------------
매일 자동 실행하면 카나리아 상태 변화를 핸드폰으로 알려줍니다.

★ v2 업그레이드: yfinance 직접 호출로 당월 부분수익률(partial return) 반영
  → fetch_etf_data.py / fetch_prices.py 를 별도 실행하지 않아도 됩니다.
  → 오늘 종가 기준의 최신 모멘텀 점수를 계산합니다.

■ 최초 설정 (1회)
  1. yfinance 설치
       pip install yfinance --break-system-packages

  2. 핸드폰에 'ntfy' 앱 설치
     - iOS:     https://apps.apple.com/app/ntfy/id1625396347
     - Android: https://play.google.com/store/apps/details?id=io.heckel.ntfy

  3. 앱에서 구독(Subscribe) → 토픽 이름 입력 (예: dual-momentum-기태)
  4. 아래 NTFY_TOPIC 에 같은 이름 설정

■ 사용법
  python notify_signals.py
  python notify_signals.py /path/to/DualMomentumDashboard.jsx
"""

import sys, os, re, json, urllib.request, urllib.parse
from datetime import datetime, date

# ══════════════════════════════════════════════════════════════════
# ★ 설정 — 여기만 수정하세요
# ══════════════════════════════════════════════════════════════════
NTFY_TOPIC     = os.environ.get("NTFY_TOPIC", "dual-momentum-alert")  # 환경변수 우선, 없으면 기본값
NTFY_SERVER    = "https://ntfy.sh"       # 기본 서버 (변경 불필요)
CANARY_TICKERS = ["EEM", "HYG"]         # 카나리 자산 (EEM, HYG, AGG, SPLG 중 선택)
STATE_FILE     = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               ".signal_state.json")
# ══════════════════════════════════════════════════════════════════

JSX_PATH = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "DualMomentumDashboard.jsx")
)


# ── 1. yfinance 직접 호출: 당월 부분수익률 포함 월별 수익률 계산 ─────
def fetch_canary_via_yfinance(tickers):
    """
    각 ticker의 월별 수익률 리스트를 반환.
    마지막 원소 = 당월 현재까지의 부분 수익률 (partial month return).
    예: [r_5개월전, r_4개월전, ..., r_전월, r_당월partial]

    모멘텀 계산에 필요한 최소 7개월치 수익률을 확보합니다.
    """
    try:
        import yfinance as yf
        import pandas as pd
    except ImportError:
        print("  yfinance 미설치. pip install yfinance --break-system-packages")
        return None

    result = {}
    today = date.today()
    current_ym = today.strftime("%Y-%m")

    for ticker in tickers:
        try:
            # 10개월치 일별 데이터 다운로드
            hist = yf.download(
                ticker, period="10mo", interval="1d",
                auto_adjust=True, progress=False,
                multi_level_column=False
            )
            if hist.empty:
                print(f"  ✗ {ticker}: 데이터 없음")
                continue

            close = hist["Close"].dropna()

            # ── 월말 종가 시리즈 (완전한 달만) ─────────────────────
            monthly_prices = close.resample("ME").last()

            # 이번달이 monthly_prices 마지막에 포함된 경우 제거
            # (아직 이번달이 끝나지 않았으므로 완전한 달이 아님)
            if monthly_prices.index[-1].strftime("%Y-%m") == current_ym:
                monthly_prices = monthly_prices.iloc[:-1]

            if len(monthly_prices) < 2:
                print(f"  ✗ {ticker}: 월별 데이터 부족")
                continue

            # ── 당월 부분 수익률 ────────────────────────────────────
            # 오늘 종가 / 전월 말 종가 - 1
            today_price        = float(close.iloc[-1])
            prev_month_end     = float(monthly_prices.iloc[-1])
            partial_return     = (today_price / prev_month_end) - 1

            # ── 완전한 월별 수익률 (전월까지) ──────────────────────
            complete_returns   = list(monthly_prices.pct_change().dropna().values)

            # ── 당월 partial 추가 ───────────────────────────────────
            returns_with_partial = complete_returns + [partial_return]

            if len(returns_with_partial) < 7:
                print(f"  ✗ {ticker}: 수익률 데이터 부족 ({len(returns_with_partial)}개월)")
                continue

            result[ticker] = returns_with_partial

            prev_ym   = monthly_prices.index[-1].strftime("%Y-%m")
            print(f"  ✓ {ticker}: 전월({prev_ym}) 이후 당월 부분수익률 "
                  f"{partial_return*100:+.2f}% (오늘 기준)")

        except Exception as e:
            print(f"  ✗ {ticker}: {e}")

    return result if result else None


# ── 2. JSX 에서 REAL_ETF_DATA 파싱 (yfinance 불가시 fallback) ────────
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


# ── 3. 가중 모멘텀 계산 (12×r1 + 4×r3_cum + 2×r6_cum) ───────────────
def calc_momentum(returns_list):
    """
    returns_list 의 마지막 원소가 가장 최근 수익률.
    최소 7개 필요 (r1 + r3 + r6 = 6개월 + 여분 1).
    """
    r = returns_list
    if len(r) < 7:
        return None

    r1 = r[-1]               # 최근 1개월 (당월 partial 포함)

    c3 = 1.0                 # 최근 3개월 누적
    for i in range(-3, 0):
        c3 *= (1 + r[i])

    c6 = 1.0                 # 최근 6개월 누적
    for i in range(-6, 0):
        c6 *= (1 + r[i])

    return 12 * r1 + 4 * (c3 - 1) + 2 * (c6 - 1)


# ── 4. 카나리아 상태 계산 ─────────────────────────────────────────────
def calc_canary_state(canary_data, date_str):
    scores = {t: calc_momentum(r) for t, r in canary_data.items()}
    valid  = [s for s in scores.values() if s is not None]

    bad_count = sum(1 for s in valid if s < 0)
    bil_ratio = (
        0   if bad_count == 0       else
        1.0 if bad_count >= len(valid) else
        0.5
    )

    return {
        "date":      date_str,
        "scores":    scores,
        "bad_count": bad_count,
        "bil_ratio": bil_ratio,
    }


# ── 5. 상태 저장 / 불러오기 ───────────────────────────────────────────
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


# ── 6. ntfy 알림 전송 ─────────────────────────────────────────────────
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
        print(f"    토픽 확인: {NTFY_TOPIC}")


# ── 메인 ──────────────────────────────────────────────────────────────
def main():
    now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
    date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"[{now_str}] 시그널 체크 시작\n")

    # ── 데이터 수집 (yfinance 우선 → JSX fallback) ──────────────────
    print("카나리아 데이터 수집 중 (yfinance)...")
    canary_data = fetch_canary_via_yfinance(CANARY_TICKERS)
    data_source = f"실시간 yfinance ({date_str} 기준)"

    if canary_data is None:
        print("\nyfinance 실패 — JSX 정적 데이터 사용 (시의성 낮음)\n")
        canary_data = fetch_canary_via_jsx(JSX_PATH, CANARY_TICKERS)
        data_source = "JSX 정적 데이터 (fetch_etf_data.py 마지막 실행 기준)"

        if canary_data is None:
            print("오류: 데이터를 가져올 수 없습니다.")
            print("  해결: pip install yfinance --break-system-packages")
            return

    print(f"\n  [데이터 출처] {data_source}\n")

    # ── 카나리아 상태 계산 ──────────────────────────────────────────
    curr = calc_canary_state(canary_data, date_str)
    prev = load_prev_state()
    save_state(curr)

    # ── 점수 출력 ───────────────────────────────────────────────────
    print(f"기준 날짜: {curr['date']}")
    for ticker, score in curr["scores"].items():
        if score is not None:
            sign = "🔴 음수 (위험)" if score < 0 else "🟢 양수 (안전)"
            print(f"  {ticker}: {score:+.4f}  {sign}")
        else:
            print(f"  {ticker}: N/A (데이터 부족)")
    print(f"BIL 비중: {curr['bil_ratio']*100:.0f}%\n")

    # ── 상태 변화 감지 ──────────────────────────────────────────────
    if prev is None:
        print("이전 상태 없음 — 기준 상태 저장 완료.")
        print("다음 실행부터 변화를 감지합니다.\n")
        send_notification(
            "📊 듀얼모멘텀 모니터링 시작",
            f"시그널 감지 시작\n"
            f"기준: {curr['date']}\n"
            f"BIL 비중: {curr['bil_ratio']*100:.0f}%\n"
            f"출처: {data_source}",
            priority="low", tags="chart_increasing"
        )
        return

    prev_bil = prev.get("bil_ratio", 0)
    curr_bil = curr["bil_ratio"]
    changed  = abs(curr_bil - prev_bil) > 0.01

    if not changed:
        print(f"변화 없음 — BIL {curr_bil*100:.0f}% 유지")
        return

    # ── 알림 메시지 생성 ────────────────────────────────────────────
    score_lines = "\n".join(
        f"  {t}: {s:+.3f}  ({'⚠️ 위험' if s < 0 else '✅ 안전'})"
        for t, s in curr["scores"].items() if s is not None
    )
    footer = f"\n기준: {curr['date']}\n출처: {data_source}"

    if prev_bil == 0 and curr_bil > 0:
        title    = "🔴 카나리아 위험 전환 — 즉시 리밸런싱"
        message  = (f"위험 신호 감지!\n"
                    f"BIL 비중: 0% → {curr_bil*100:.0f}%\n\n"
                    f"점수:\n{score_lines}{footer}")
        priority = "urgent"
        tags     = "warning,rotating_light"

    elif prev_bil > 0 and curr_bil == 0:
        title    = "🟢 카나리아 위험 해제 — 정상 배분 복귀"
        message  = (f"카나리아 모두 안전 전환!\n"
                    f"BIL 비중: {prev_bil*100:.0f}% → 0%\n\n"
                    f"점수:\n{score_lines}{footer}")
        priority = "high"
        tags     = "white_check_mark,chart_increasing"

    elif curr_bil > prev_bil:
        title    = "🟠 위험 수위 상승 — 리밸런싱 권고"
        message  = (f"BIL 비중 상승: {prev_bil*100:.0f}% → {curr_bil*100:.0f}%\n\n"
                    f"점수:\n{score_lines}{footer}")
        priority = "high"
        tags     = "chart_with_downwards_trend"

    else:
        title    = "🟡 위험 수위 하락"
        message  = (f"BIL 비중 감소: {prev_bil*100:.0f}% → {curr_bil*100:.0f}%\n\n"
                    f"점수:\n{score_lines}{footer}")
        priority = "default"
        tags     = "chart_with_upwards_trend"

    print(f"시그널 변화 감지: {title}")
    send_notification(title, message, priority=priority, tags=tags)


if __name__ == "__main__":
    main()
