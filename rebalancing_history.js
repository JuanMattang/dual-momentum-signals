/* TEST FILE — 대시보드 렌더링 확인용 */
window.REBALANCING_HISTORY = {
  "today": {
    "date": "2026-03-19",
    "type": "오늘",
    "bil_ratio": 0.4,
    "canary": {
      "EEM": {"score": -0.0312, "z_score": -1.42},
      "AGG": {"score":  0.0105, "z_score":  0.87}
    },
    "portfolio": [
      {"ticker": "BIL",  "name": "초단기채(현금)",  "weight": 0.4000},
      {"ticker": "TLT",  "name": "미국 장기국채",   "weight": 0.1200, "score": 0.0431},
      {"ticker": "GLDM", "name": "금",             "weight": 0.1200, "score": 0.0389},
      {"ticker": "TIP",  "name": "물가연동채",      "weight": 0.1200, "score": 0.0274},
      {"ticker": "LQD",  "name": "투자등급 회사채", "weight": 0.1200, "score": 0.0198},
      {"ticker": "AGG",  "name": "미국 종합채권",   "weight": 0.1200, "score": 0.0105}
    ]
  },
  "last_regular": {
    "date": "2026-03-01",
    "type": "정기",
    "bil_ratio": 0.2,
    "canary": {
      "EEM": {"score": -0.0156, "z_score": -0.91},
      "AGG": {"score":  0.0134, "z_score":  1.03}
    },
    "portfolio": [
      {"ticker": "BIL",  "name": "초단기채(현금)",  "weight": 0.2000},
      {"ticker": "SPLG", "name": "미국 대형주",     "weight": 0.1600, "score": 0.0621},
      {"ticker": "GLDM", "name": "금",             "weight": 0.1600, "score": 0.0389},
      {"ticker": "TLT",  "name": "미국 장기국채",   "weight": 0.1600, "score": 0.0321},
      {"ticker": "TIP",  "name": "물가연동채",      "weight": 0.1600, "score": 0.0274},
      {"ticker": "LQD",  "name": "투자등급 회사채", "weight": 0.1600, "score": 0.0198}
    ]
  },
  "last_emergency": {
    "date": "2026-03-15",
    "type": "수시",
    "bil_ratio": 0.4,
    "canary": {
      "EEM": {"score": -0.0298, "z_score": -1.35},
      "AGG": {"score":  0.0112, "z_score":  0.91}
    },
    "portfolio": [
      {"ticker": "BIL",  "name": "초단기채(현금)",  "weight": 0.4000},
      {"ticker": "TLT",  "name": "미국 장기국채",   "weight": 0.1200, "score": 0.0431},
      {"ticker": "GLDM", "name": "금",             "weight": 0.1200, "score": 0.0389},
      {"ticker": "TIP",  "name": "물가연동채",      "weight": 0.1200, "score": 0.0274},
      {"ticker": "LQD",  "name": "투자등급 회사채", "weight": 0.1200, "score": 0.0198},
      {"ticker": "AGG",  "name": "미국 종합채권",   "weight": 0.1200, "score": 0.0105}
    ]
  },
  "history": []
};
