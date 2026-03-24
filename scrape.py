#!/usr/bin/env python3
"""
PropertyPulse scraper — full automation
Data sources:
  - FRED API: OBMMI daily rates + PMMS weekly rates
  - Fannie Mae APIs (OAuth2): Economic Indicators, Housing Indicators, NHS/HPSI, RALI
  - Fortune Real Estate RSS: headlines
  - MBA/HousingWire RSS: application data
"""

import os
import re
import json
import datetime
import urllib.request
import urllib.parse
import urllib.error

TODAY     = datetime.date.today()
TODAY_STR = TODAY.strftime("%B %d, %Y")
RUN_TS    = datetime.datetime.utcnow().strftime("%b %d, %Y %I:%M %p UTC")

FRED_KEY        = os.environ.get("FRED_API_KEY", "")
FANNIE_CLIENT_ID     = os.environ.get("FANNIE_CLIENT_ID", "")
FANNIE_CLIENT_SECRET = os.environ.get("FANNIE_CLIENT_SECRET", "")
FANNIE_BASE     = "https://api.fanniemae.com"

# ── HELPERS ───────────────────────────────────────────────────────────────────

def fetch(url, timeout=20, headers=None):
    h = {"User-Agent": "PropertyPulse/2.0 (github.com/z5dxnbyb5y-cmyk/propertypulse)"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  WARN fetch {url}: {e}")
        return ""

def post(url, data, headers=None, timeout=20):
    h = {"Content-Type": "application/x-www-form-urlencoded"}
    if headers:
        h.update(headers)
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  WARN post {url}: {e}")
        return ""

# ── FANNIE MAE OAUTH ───────────────────────────────────────────────────────────

_fannie_token = None
_fannie_token_expiry = None

def get_fannie_token():
    global _fannie_token, _fannie_token_expiry
    if _fannie_token and _fannie_token_expiry and datetime.datetime.utcnow() < _fannie_token_expiry:
        return _fannie_token
    if not FANNIE_CLIENT_ID or not FANNIE_CLIENT_SECRET:
        print("  WARN: Fannie Mae credentials not set")
        return None
    print("  Getting Fannie Mae OAuth token...")
    raw = post("https://api.fanniemae.com/v1/oauth2/token", {
        "grant_type":    "client_credentials",
        "client_id":     FANNIE_CLIENT_ID,
        "client_secret": FANNIE_CLIENT_SECRET,
    })
    if not raw:
        return None
    try:
        data = json.loads(raw)
        _fannie_token = data.get("access_token")
        expires_in = int(data.get("expires_in", 3600))
        _fannie_token_expiry = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in - 60)
        print(f"  Token acquired, expires in {expires_in}s")
        return _fannie_token
    except Exception as e:
        print(f"  WARN: token parse error: {e}")
        return None

def fannie_get(path):
    token = get_fannie_token()
    if not token:
        return None
    url = FANNIE_BASE + path
    raw = fetch(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception as e:
        print(f"  WARN: Fannie Mae JSON parse error for {path}: {e}")
        return None

# ── FRED HELPERS ──────────────────────────────────────────────────────────────

def fred(series_id, limit=5):
    if not FRED_KEY:
        return []
    params = urllib.parse.urlencode({
        "series_id": series_id, "api_key": FRED_KEY,
        "file_type": "json", "sort_order": "desc", "limit": limit,
        "observation_start": "2020-01-01",
    })
    raw = fetch(f"https://api.stlouisfed.org/fred/series/observations?{params}")
    if not raw:
        return []
    try:
        return [o for o in json.loads(raw).get("observations", []) if o.get("value") not in (".", "")]
    except Exception:
        return []

def fred_two(series_id):
    obs = fred(series_id, limit=10)
    valid = [(float(o["value"]), o["date"]) for o in obs if o.get("value") not in (".", "")]
    valid = [(v, d) for v, d in valid if v > 0]
    if len(valid) >= 2:
        return valid[0][0], valid[1][0], valid[0][1]
    elif len(valid) == 1:
        return valid[0][0], valid[0][0], valid[0][1]
    return None, None, None

# ── 1. OBMMI RATES VIA FRED ────────────────────────────────────────────────────

OBMMI_SERIES = [
    ("30-Year Conventional", "30Y CONV",  "OBMMIC30YF"),
    ("15-Year Conventional", "15Y CONV",  "OBMMIC15YF"),
    ("30-Year Jumbo",        "30Y JUMBO", "OBMMIJUMBO30YF"),
    ("30-Year FHA",          "30Y FHA",   "OBMMIFHA30YF"),
    ("30-Year VA",           "30Y VA",    "OBMMIVA30YF"),
    ("30-Year USDA",         "30Y USDA",  "OBMMIUSDA30YF"),
]
OBMMI_FALLBACKS = {
    "OBMMIC30YF": (6.356, 6.214), "OBMMIC15YF": (5.707, 5.507),
    "OBMMIJUMBO30YF": (6.597, 6.454), "OBMMIFHA30YF": (6.164, 6.014),
    "OBMMIVA30YF": (5.999, 5.830), "OBMMIUSDA30YF": (6.033, 5.968),
}

def fetch_obmmi():
    print("Fetching OBMMI rates from FRED...")
    rates = []
    for type_name, lb, series in OBMMI_SERIES:
        cur, prev, date = fred_two(series)
        if cur is None:
            cur, prev = OBMMI_FALLBACKS.get(series, (6.00, 6.00))
            date = "N/A"
        bps = round((cur - prev) * 100, 1)
        rates.append({"type": type_name, "lb": lb, "rate": round(cur, 3),
                       "prev": round(prev, 3), "bps": int(round(bps)),
                       "dod": f"{'+'if bps>=0 else ''}{bps:.0f}bps", "date": date})
        print(f"  {lb}: {cur:.3f}% ({bps:+.0f}bps) [{date}]")
    return rates

# ── 2. PMMS VIA FRED ───────────────────────────────────────────────────────────

def fetch_pmms():
    print("Fetching PMMS from FRED...")
    r30, p30, d30 = fred_two("MORTGAGE30US")
    r15, p15, _   = fred_two("MORTGAGE15US")
    obs_yago = fred("MORTGAGE30US", limit=60)
    r30_yago = None
    if len(obs_yago) >= 52:
        try:
            r30_yago = float(obs_yago[51]["value"])
        except Exception:
            pass
    if r30 is None:
        return {"rate_30y": 6.22, "rate_15y": 5.54, "prev_30y": 6.11,
                "prev_15y": 5.50, "date": "N/A", "yago_30y": 6.67}
    try:
        dt = datetime.datetime.strptime(d30, "%Y-%m-%d")
        date_str = dt.strftime("%b %d, %Y")
    except Exception:
        date_str = d30
    print(f"  PMMS 30Y: {r30:.2f}%  15Y: {r15:.2f}%  ({date_str})")
    return {"rate_30y": round(r30, 2), "rate_15y": round(r15, 2) if r15 else None,
            "prev_30y": round(p30, 2) if p30 else None,
            "prev_15y": round(p15, 2) if p15 else None,
            "date": date_str, "yago_30y": round(r30_yago, 2) if r30_yago else None}

# ── 3. FANNIE MAE: HOUSING INDICATORS ─────────────────────────────────────────

def get_latest_points(indicator_data, year, forecast_only=True):
    """Extract the most recent report's points for a given year, optionally only forecasted."""
    if not indicator_data or "indicators" not in indicator_data:
        return []
    # Sort by effectiveDate descending to get most recent report
    indicators = sorted(
        indicator_data["indicators"],
        key=lambda x: x.get("effectiveDate", ""),
        reverse=True
    )
    if not indicators:
        return []
    latest = indicators[0]
    points = latest.get("points") or latest.get("timeSeries") or []
    result = []
    for p in points:
        if p.get("year") == year:
            if forecast_only and not p.get("forecast", False):
                continue
            result.append(p)
    return result

def fetch_fannie_housing():
    print("Fetching Fannie Mae Housing Indicators...")
    year = TODAY.year
    result = {
        "mortgage_rate_30y": {},  # quarterly forecasts
        "total_home_sales": None,
        "sf_starts": None,
        "total_starts": None,
        "report_date": None,
    }

    # 30-year fixed rate mortgage forecast
    print("  Fetching 30-year FRM forecast...")
    data = fannie_get(f"/v1/housing-indicators/indicators/30-year-fixed-rate-mortgage")
    if data and "indicators" in data:
        indicators = sorted(data["indicators"], key=lambda x: x.get("effectiveDate",""), reverse=True)
        if indicators:
            result["report_date"] = indicators[0].get("effectiveDate","")[:10]
            points = indicators[0].get("points") or indicators[0].get("timeSeries") or []
            for p in points:
                if p.get("forecast") and p.get("year") in (year, year+1):
                    q = p.get("quarter", "")
                    yr = p.get("year")
                    key = f"{q} {yr}"
                    result["mortgage_rate_30y"][key] = round(float(p.get("value", 0)), 2)
            print(f"  30Y FRM forecast points: {result['mortgage_rate_30y']}")

    # Total home sales (EOY forecast)
    print("  Fetching total home sales forecast...")
    data = fannie_get(f"/v1/housing-indicators/indicators/total-home-sales")
    if data and "indicators" in data:
        indicators = sorted(data["indicators"], key=lambda x: x.get("effectiveDate",""), reverse=True)
        if indicators:
            points = indicators[0].get("points") or indicators[0].get("timeSeries") or []
            for p in points:
                if p.get("forecast") and p.get("year") == year and p.get("quarter") == "EOY":
                    result["total_home_sales"] = round(float(p.get("value", 0)) / 1000, 2)
                    break

    # Single-family housing starts
    print("  Fetching SF housing starts forecast...")
    data = fannie_get(f"/v1/housing-indicators/indicators/single-family-1-unit-housing-starts")
    if data and "indicators" in data:
        indicators = sorted(data["indicators"], key=lambda x: x.get("effectiveDate",""), reverse=True)
        if indicators and len(indicators) >= 2:
            # Compare most recent vs prior to get YoY change
            cur_pts  = {p.get("quarter"): p.get("value") for p in (indicators[0].get("points") or []) if p.get("year") == year}
            prev_pts = {p.get("quarter"): p.get("value") for p in (indicators[1].get("points") or []) if p.get("year") == year - 1}
            if cur_pts.get("EOY") and prev_pts.get("EOY"):
                cur_val  = float(cur_pts["EOY"])
                prev_val = float(prev_pts["EOY"])
                pct_chg  = (cur_val - prev_val) / prev_val * 100
                result["sf_starts"] = round(pct_chg, 1)

    print(f"  Home sales: {result['total_home_sales']}M  SF starts YoY: {result['sf_starts']}%")
    return result

# ── 4. FANNIE MAE: ECONOMIC INDICATORS ────────────────────────────────────────

def fetch_fannie_economic():
    print("Fetching Fannie Mae Economic Indicators...")
    result = {"fed_funds": None, "treasury_10y": None, "unemployment": None,
              "cpi": None, "gdp": None, "report_date": None}

    indicators_to_fetch = [
        ("federal-funds-rate",    "fed_funds"),
        ("10-year-treasury-note-yield", "treasury_10y"),
        ("unemployment-rate",     "unemployment"),
        ("consumer-price-index",  "cpi"),
        ("gross-domestic-product","gdp"),
    ]

    year = TODAY.year
    for indicator, key in indicators_to_fetch:
        data = fannie_get(f"/v1/economic-forecasts/indicators/{indicator}")
        if not data or "indicators" not in data:
            continue
        indicators = sorted(data["indicators"], key=lambda x: x.get("effectiveDate",""), reverse=True)
        if not indicators:
            continue
        if not result["report_date"]:
            result["report_date"] = indicators[0].get("effectiveDate","")[:10]
        points = indicators[0].get("points") or indicators[0].get("timeSeries") or []
        # Get EOY forecast for current year
        for p in points:
            if p.get("year") == year and p.get("forecast"):
                if p.get("quarter") in ("EOY", "Q4"):
                    result[key] = round(float(p.get("value", 0)), 2)
                    break
        print(f"  {indicator}: {result[key]}")

    return result

# ── 5. FANNIE MAE: HPSI (HOME PURCHASE SENTIMENT INDEX) ───────────────────────

def fetch_fannie_hpsi():
    print("Fetching Fannie Mae HPSI...")
    data = fannie_get("/v1/nhs/hpsi")
    if not data or not isinstance(data, list):
        return None
    # Most recent entry
    try:
        latest = sorted(data, key=lambda x: x.get("date",""), reverse=True)[0]
        val  = round(float(latest.get("hpsiValue", 0)), 1)
        date = latest.get("date","")[:10]
        # Format date
        try:
            dt = datetime.datetime.strptime(date, "%Y-%m-%d")
            date = dt.strftime("%b %Y")
        except Exception:
            pass
        print(f"  HPSI: {val} ({date})")
        return {"value": val, "date": date}
    except Exception as e:
        print(f"  WARN HPSI: {e}")
        return None

# ── 6. FANNIE MAE: RALI ────────────────────────────────────────────────────────

def fetch_fannie_rali():
    print("Fetching Fannie Mae RALI (refinance index)...")
    data = fannie_get("/v1/rali/most-recent-week")
    if not data or not isinstance(data, list):
        return None
    try:
        latest = data[0] if data else None
        if not latest:
            return None
        print(f"  RALI data: {list(latest.keys())[:5]}")
        return latest
    except Exception as e:
        print(f"  WARN RALI: {e}")
        return None

# ── 7. FORTUNE HEADLINES ───────────────────────────────────────────────────────

def fetch_fortune_news():
    print("Fetching Fortune Real Estate RSS...")
    raw = fetch("https://fortune.com/feed/section/real-estate/")
    articles = []
    seen = set()
    for m in re.finditer(
        r'<item>.*?<title><!\[CDATA\[(.*?)\]\]></title>.*?<link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>',
        raw, re.DOTALL
    ):
        title, url, pub = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        if url in seen or len(title) < 15:
            continue
        seen.add(url)
        try:
            dt = datetime.datetime.strptime(pub[:25], "%a, %d %b %Y %H:%M")
            date_str = dt.strftime("%b %d, %Y")
        except Exception:
            date_str = pub[:16]
        articles.append({"title": title, "url": url, "date": date_str})
        if len(articles) >= 6:
            break
    # Fallback scrape
    if not articles:
        html = fetch("https://fortune.com/section/real-estate/")
        for m in re.finditer(
            r'href="(https://fortune\.com/(?:article/)?20\d\d/\d\d/\d\d/[^"]+?)"[^>]*?>([^<]{20,200})</a>',
            html, re.IGNORECASE
        ):
            url, title = m.group(1), re.sub(r'\s+', ' ', m.group(2).strip())
            if url not in seen and len(title) > 20 and '<' not in title:
                seen.add(url)
                dm = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
                date_str = ""
                if dm:
                    try:
                        date_str = datetime.date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3))).strftime("%b %d, %Y")
                    except Exception:
                        pass
                articles.append({"title": title, "url": url, "date": date_str})
            if len(articles) >= 6:
                break
    print(f"  Found {len(articles)} Fortune articles")
    return articles

# ── 8. MBA VIA HOUSINGWIRE RSS ─────────────────────────────────────────────────

def fetch_mba():
    print("Fetching MBA data via HousingWire RSS...")
    rss = fetch("https://www.housingwire.com/feed/")
    weeks = []
    items = []
    for m in re.finditer(
        r'<item>.*?<title><!\[CDATA\[(.*?)\]\]></title>.*?<link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>',
        rss, re.DOTALL | re.IGNORECASE
    ):
        title, url, pub = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        if "application" not in title.lower() and "mba" not in title.lower():
            continue
        try:
            dt = datetime.datetime.strptime(pub[:25], "%a, %d %b %Y %H:%M")
            date_str = dt.strftime("%b %d, %Y")
        except Exception:
            date_str = pub[:16]
        pct = re.search(r'(increased|decreased|rose|fell|up|down)\s+([\d.]+)%', title, re.I)
        val = None
        if pct:
            direction = pct.group(1).lower()
            val = float(pct.group(2))
            if direction in ("decreased", "fell", "down"):
                val = -val
        items.append({"title": title, "url": url, "date": date_str})
        if val is not None:
            weeks.append({"title": title, "url": url, "date": date_str, "val": val})
    print(f"  MBA: {len(weeks)} weeks with values, {len(items)} total items")
    return {"weeks": weeks[:3], "items": items[:3]}

# ── HTML BUILDERS ──────────────────────────────────────────────────────────────

def build_news_html(articles):
    if not articles:
        return '<div style="padding:1rem;color:#7a7163;font-size:.75rem;">No articles available.</div>'
    out = ""
    for a in articles:
        out += (
            f'\n    <a class="news-item" href="{a["url"]}" target="_blank" rel="noopener">'
            f'\n      <div class="ni-date">{a["date"]}</div>'
            f'\n      <div class="ni-title">{a["title"]}</div>'
            f'\n    </a>'
        )
    return out

def build_mba_html(mba):
    weeks = mba.get("weeks", [])
    items = mba.get("items", [])
    if weeks:
        bars = ""
        for w in weeks:
            val = w["val"]
            pct = min(95, abs(val) / 12 * 100)
            col = "var(--down)" if val < 0 else "var(--up)"
            sign = "+" if val >= 0 else ""
            arr = "↑" if val >= 0 else "↓"
            tag = "Rising" if val > 0 else "Declining"
            bars += (
                f'\n<div class="bar-row">'
                f'<div class="bar-week">{w["date"][:6]}</div>'
                f'<div class="bar-track"><div class="bar-inner" style="width:{pct:.0f}%;background:{col};">'
                f'<span>{sign}{val:.1f}%</span></div></div>'
                f'<div class="bar-tag" style="color:{col};">{arr} {tag}</div></div>'
            )
        return f'<div class="chart-label">Total Applications — WoW Change</div>{bars}'
    if items:
        out = '<div class="chart-label">Latest MBA Headlines</div>'
        for item in items[:3]:
            out += (
                f'\n<a href="{item["url"]}" target="_blank" rel="noopener" style="display:block;padding:.6rem 0;border-bottom:1px solid var(--border);">'
                f'<div style="font-family:\'DM Mono\',monospace;font-size:.54rem;color:var(--muted);margin-bottom:.2rem;">{item["date"]}</div>'
                f'<div style="font-size:.75rem;font-weight:600;">{item["title"]}</div></a>'
            )
        return out
    return '<div style="padding:.5rem 0;color:var(--muted);font-size:.75rem;">MBA data temporarily unavailable.</div>'

def build_fannie_forecast_rows(housing):
    """Build forecast table rows from live Fannie Mae API data."""
    year = TODAY.year
    rates = housing.get("mortgage_rate_30y", {})
    tag_map = {"green": "fc-tag-green", "neutral": "fc-tag-neutral"}

    # Define the quarters we want to show
    quarters = [
        (f"Q1 {year}",      f"Q1 {year}"),
        (f"Q2 {year}",      f"Q2 {year}"),
        (f"Q3 {year}",      f"Q3 {year}"),
        (f"Q4 {year}",      f"Q4 {year}"),
        (f"EOY {year+1}",   f"Full Yr {year+1}"),
    ]

    rows = ""
    for key, label in quarters:
        val = rates.get(key)
        if val:
            rate_str = f"{val:.2f}%"
            tag = "green" if val < 6.0 else "neutral"
            signal = "Sub-6%" if val < 6.0 else "Above 6%"
            rows += (
                f'\n    <tr>'
                f'<td class="td-type">{label}</td>'
                f'<td class="fc {"fc-good" if val < 6.0 else ""}">{rate_str}</td>'
                f'<td class="fc fc-neu">Live from API</td>'
                f'<td><span class="fc-tag {tag_map[tag]}">{signal}</span></td>'
                f'</tr>'
            )
        else:
            rows += (
                f'\n    <tr>'
                f'<td class="td-type">{label}</td>'
                f'<td class="fc fc-neu">—</td>'
                f'<td class="fc fc-neu">—</td>'
                f'<td><span class="fc-tag fc-tag-neutral">Pending</span></td>'
                f'</tr>'
            )
    return rows

def build_ticker(rates, pmms, hpsi, rali):
    r30   = pmms.get("rate_30y") or 0
    r15   = pmms.get("rate_15y") or 0
    pdate = pmms.get("date", "")
    yago  = pmms.get("yago_30y") or 0
    yoy   = round((r30 - yago) * 100) if yago else 0
    p30   = pmms.get("prev_30y") or r30
    bps30 = round((r30 - p30) * 100, 1)

    items = [
        ("PMMS 30Y",    f"{r30:.2f}%",  "chup" if bps30 <= 0 else "chdn", f"{'▲' if bps30>0 else '▼'} {pdate}"),
        ("PMMS 15Y",    f"{r15:.2f}%",  "chup", "Weekly"),
        ("FED RATE",    "3.50–3.75%",   "",      "HOLD"),
    ]
    if hpsi:
        items.append(("HPSI", f"{hpsi['value']}", "chup", f"Sentiment · {hpsi['date']}"))
    items.append(("1YR AGO 30Y", f"{yago:.2f}%", "chdn", f"{'▼' if yoy<=0 else '▲'} {abs(yoy):.0f}bps YoY"))
    for r in rates:
        d = "chup" if r["bps"] >= 0 else "chdn"
        a = "▲" if r["bps"] >= 0 else "▼"
        items.append((f"OB {r['lb']}", f"{r['rate']:.3f}%", d, f"{a}{abs(r['bps'])}bps"))

    def ti(label, val, cls, chg):
        if label == "FED RATE":
            chg_s = f'<span style="color:#ffd88a">{chg}</span>'
        else:
            chg_s = f'<span class="{cls}">{chg}</span>'
        return f'<div class="ticker-item"><span class="lb">{label}</span><span>{val}</span>{chg_s}</div>'

    single = "\n    ".join(ti(*i) for i in items)
    return single + "\n    " + single

# ── MAIN HTML ──────────────────────────────────────────────────────────────────

def build_html(rates, pmms, housing, economic, hpsi, rali, news, mba):
    rates_json      = json.dumps(rates)
    news_html_str   = build_news_html(news)
    mba_html_str    = build_mba_html(mba)
    fannie_rows_str = build_fannie_forecast_rows(housing)
    ticker_str      = build_ticker(rates, pmms, hpsi, rali)

    r30   = pmms.get("rate_30y") or 0
    r15   = pmms.get("rate_15y") or 0
    p30   = pmms.get("prev_30y") or r30
    p15   = pmms.get("prev_15y") or r15
    pdate = pmms.get("date", "N/A")
    yago  = pmms.get("yago_30y") or 0
    yoy   = round((r30 - yago) * 100) if yago else 0
    bps30 = round((r30 - p30) * 100, 1)
    bps15 = round((r15 - p15) * 100, 1)
    dir30 = "▲" if bps30 >= 0 else "▼"
    dir15 = "▲" if bps15 >= 0 else "▼"
    yoy_label = "▼ More affordable YoY" if yoy <= 0 else "▲ Higher YoY"
    yoy_cls   = "pos" if yoy <= 0 else "up"

    # Fannie Mae data for cards
    home_sales  = f"~{housing.get('total_home_sales')}M" if housing.get("total_home_sales") else "~5.5M"
    sf_starts   = f"{housing.get('sf_starts'):+.1f}%" if housing.get("sf_starts") is not None else "−6.2%"
    gdp         = f"{economic.get('gdp'):.1f}%" if economic.get("gdp") else "N/A"
    unemployment = f"{economic.get('unemployment'):.1f}%" if economic.get("unemployment") else "N/A"
    cpi         = f"{economic.get('cpi'):.1f}%" if economic.get("cpi") else "N/A"
    treasury10y = f"{economic.get('treasury_10y'):.2f}%" if economic.get("treasury_10y") else "N/A"
    fed_rate_fc = f"{economic.get('fed_funds'):.2f}%" if economic.get("fed_funds") else "3.50–3.75%"
    hpsi_val    = f"{hpsi['value']}" if hpsi else "N/A"
    hpsi_date   = hpsi["date"] if hpsi else ""

    fannie_report_date = housing.get("report_date") or economic.get("report_date") or "Latest"
    try:
        dt = datetime.datetime.strptime(fannie_report_date, "%Y-%m-%d")
        fannie_report_date = dt.strftime("%B %Y")
    except Exception:
        pass

    obmmi_date = rates[0]["date"] if rates else "N/A"
    try:
        obmmi_date = datetime.datetime.strptime(obmmi_date, "%Y-%m-%d").strftime("%b %d, %Y")
    except Exception:
        pass

    mba_headline = ""
    mba_date = ""
    weeks = mba.get("weeks", [])
    items_list = mba.get("items", [])
    if weeks:
        mba_headline = weeks[0].get("title", "")
        mba_date = weeks[0].get("date", "")
    elif items_list:
        mba_headline = items_list[0].get("title", "")
        mba_date = items_list[0].get("date", "")
    mba_short = (mba_headline[:65] + "...") if len(mba_headline) > 65 else mba_headline

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PropertyPulse — Real Estate Market Tracker</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  :root{{--ink:#0d0d0d;--paper:#f4f0e8;--paper2:#ede8da;--accent:#c84b2f;--up:#2a6e4e;--down:#c84b2f;--gold:#d4943a;--muted:#7a7163;--border:#c8bfa8;--card:#faf7f0}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Syne',sans-serif;background:var(--paper);color:var(--ink);min-height:100vh;font-size:14px}}
  a{{color:inherit;text-decoration:none}}
  header{{background:var(--ink);color:var(--paper);padding:0 1.5rem;border-bottom:3px solid var(--accent)}}
  .hi{{max-width:1200px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:1rem 0}}
  .logo{{font-family:'DM Serif Display',serif;font-size:1.6rem;letter-spacing:-.02em}}.logo span{{color:var(--accent)}}
  .hmeta{{font-family:'DM Mono',monospace;font-size:.62rem;color:#a09880;text-align:right;line-height:1.7}}
  .ticker-wrap{{background:var(--accent);overflow:hidden;padding:.4rem 0}}
  .ticker{{display:flex;gap:2.75rem;animation:scroll 55s linear infinite;width:max-content}}
  .ticker-item{{font-family:'DM Mono',monospace;font-size:.65rem;color:white;white-space:nowrap;display:flex;align-items:center;gap:.3rem}}
  .ticker-item .lb{{opacity:.72}}.chup{{color:#a8ffc8}}.chdn{{color:#ffa8a8}}
  @keyframes scroll{{0%{{transform:translateX(0)}}100%{{transform:translateX(-50%)}}}}
  main{{max-width:1200px;margin:0 auto;padding:1.75rem 1.5rem}}
  .slbl{{font-family:'DM Mono',monospace;font-size:.58rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:.65rem;display:flex;align-items:center;gap:.5rem}}
  .slbl::after{{content:'';flex:1;height:1px;background:var(--border)}}
  .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-bottom:2rem}}
  .three-col{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1.5rem;margin-bottom:2rem}}
  .four-col{{display:grid;grid-template-columns:repeat(4,1fr);gap:1.5rem;margin-bottom:2rem}}
  @media(max-width:900px){{.four-col{{grid-template-columns:repeat(2,1fr)}}}}
  @media(max-width:860px){{.two-col,.three-col{{grid-template-columns:1fr}}}}
  .fed-note{{background:var(--ink);color:var(--paper);padding:1.25rem 1.5rem;margin-bottom:2rem;border-left:4px solid var(--gold);display:flex;gap:1.25rem;align-items:flex-start}}
  .fed-icon{{font-size:1.8rem;flex-shrink:0;opacity:.7}}
  .fed-note h4{{font-family:'DM Mono',monospace;font-size:.58rem;letter-spacing:.1em;text-transform:uppercase;color:var(--gold);margin-bottom:.35rem}}
  .fed-note p{{font-size:.76rem;line-height:1.65;color:#ccc}}.fed-note strong{{color:white}}
  .stat-tiles{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--border);border:1px solid var(--border);margin-bottom:2rem}}
  @media(max-width:700px){{.stat-tiles{{grid-template-columns:repeat(2,1fr)}}}}
  .stat-tile{{background:var(--card);padding:1rem 1.1rem}}
  .st-label{{font-family:'DM Mono',monospace;font-size:.55rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:.3rem}}
  .st-val{{font-family:'DM Serif Display',serif;font-size:1.7rem;line-height:1;margin-bottom:.2rem}}
  .st-sub{{font-family:'DM Mono',monospace;font-size:.56rem;color:var(--muted)}}
  .st-chg{{font-family:'DM Mono',monospace;font-size:.62rem;margin-top:.2rem}}
  .st-chg.up{{color:var(--down)}}.st-chg.pos{{color:var(--up)}}
  .rate-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:1px;background:var(--border);border:1px solid var(--border);margin-bottom:2rem}}
  @media(min-width:500px){{.rate-grid{{grid-template-columns:repeat(3,1fr)}}}}
  @media(min-width:900px){{.rate-grid{{grid-template-columns:repeat(6,1fr)}}}}
  .rate-card{{background:var(--card);padding:1rem 1.1rem;position:relative;overflow:hidden}}
  .rc-label{{font-family:'DM Mono',monospace;font-size:.54rem;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin-bottom:.3rem}}
  .rc-value{{font-family:'DM Serif Display',serif;font-size:1.75rem;line-height:1;margin-bottom:.2rem}}
  .rc-chg{{font-family:'DM Mono',monospace;font-size:.6rem}}.rc-chg.up{{color:var(--down)}}.rc-chg.dn{{color:var(--up)}}
  .rc-prev{{font-family:'DM Mono',monospace;font-size:.54rem;color:var(--muted);margin-top:.15rem}}
  .rc-bar{{position:absolute;bottom:0;left:0;height:3px;background:var(--accent)}}
  .panel{{background:var(--card);border:1px solid var(--border)}}
  .ph{{padding:.85rem 1.1rem;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;background:var(--ink);color:var(--paper)}}
  .ph h3{{font-family:'DM Serif Display',serif;font-size:.95rem;font-weight:400}}
  .badge{{font-family:'DM Mono',monospace;font-size:.54rem;padding:.12rem .45rem;text-transform:uppercase;letter-spacing:.06em;color:white}}
  .badge-red{{background:var(--accent)}}.badge-green{{background:var(--up)}}.badge-gold{{background:var(--gold);color:var(--ink)}}.badge-blue{{background:#2a5298}}
  .sb{{display:flex;align-items:center;gap:.45rem;padding:.5rem 1.1rem;background:var(--paper);border-top:1px solid var(--border);font-family:'DM Mono',monospace;font-size:.56rem;color:var(--muted)}}
  .sd{{width:5px;height:5px;border-radius:50%;background:var(--up);flex-shrink:0}}
  .tbl-wrap{{background:var(--card);border:1px solid var(--border);margin-bottom:2rem;overflow-x:auto}}
  table{{width:100%;border-collapse:collapse;font-size:.78rem}}
  thead th{{font-family:'DM Mono',monospace;font-size:.54rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);padding:.65rem 1.1rem;text-align:left;border-bottom:1px solid var(--border);background:var(--paper);white-space:nowrap}}
  tbody tr{{border-bottom:1px solid var(--border);transition:background .15s}}
  tbody tr:hover{{background:var(--paper2)}}tbody tr:last-child{{border-bottom:none}}
  tbody td{{padding:.7rem 1.1rem;vertical-align:middle}}
  .td-type{{font-weight:700}}.td-rate{{font-family:'DM Serif Display',serif;font-size:1.15rem}}
  .td-prev{{font-family:'DM Mono',monospace;font-size:.66rem;color:var(--muted)}}
  .td-bps{{font-family:'DM Mono',monospace;font-size:.7rem;font-weight:500}}
  .td-bps.up{{color:var(--down)}}.td-bps.dn{{color:var(--up)}}
  .bar-wrap{{width:60px;height:4px;background:var(--paper2);border-radius:2px;overflow:hidden}}
  .bar-fill{{height:100%;border-radius:2px}}
  .pmms-strip{{display:flex;gap:1px;background:var(--border)}}
  .pmms-cell{{flex:1;background:var(--card);padding:.75rem 1rem}}
  .pmms-lbl{{font-family:'DM Mono',monospace;font-size:.54rem;text-transform:uppercase;color:var(--muted);margin-bottom:.2rem}}
  .pmms-val{{font-family:'DM Serif Display',serif;font-size:1.35rem;line-height:1}}
  .pmms-sub{{font-family:'DM Mono',monospace;font-size:.52rem;color:var(--muted);margin-top:.15rem}}
  .mba-section{{padding:1rem 1.1rem}}
  .chart-label{{font-family:'DM Mono',monospace;font-size:.55rem;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:.65rem}}
  .bar-row{{display:flex;align-items:center;gap:.6rem;margin-bottom:.5rem}}
  .bar-week{{font-family:'DM Mono',monospace;font-size:.58rem;color:var(--muted);width:52px;flex-shrink:0;text-align:right}}
  .bar-track{{flex:1;height:20px;background:var(--paper2);border-radius:2px;overflow:hidden}}
  .bar-inner{{height:100%;border-radius:2px;display:flex;align-items:center;justify-content:flex-end;padding-right:6px}}
  .bar-inner span{{font-family:'DM Mono',monospace;font-size:.56rem;color:white;font-weight:500}}
  .bar-tag{{font-family:'DM Mono',monospace;font-size:.54rem;width:72px;flex-shrink:0}}
  .news-item{{padding:.8rem 1.1rem;border-bottom:1px solid var(--border);display:block;color:var(--ink);transition:background .15s}}
  .news-item:hover{{background:var(--paper2)}}.news-item:last-child{{border-bottom:none}}
  .ni-date{{font-family:'DM Mono',monospace;font-size:.54rem;color:var(--muted);margin-bottom:.2rem;text-transform:uppercase}}
  .ni-title{{font-size:.78rem;font-weight:600;line-height:1.35}}
  .ftable td,.ftable th{{padding:.6rem 1rem}}
  .fc{{font-family:'DM Mono',monospace;font-size:.7rem}}.fc-good{{color:var(--up)}}.fc-warn{{color:var(--gold)}}.fc-neu{{color:var(--muted)}}
  .fc-tag{{font-family:'DM Mono',monospace;font-size:.6rem;padding:.1rem .45rem;border-radius:2px}}
  .fc-tag-green{{background:#e8f5ee;color:var(--up)}}.fc-tag-neutral{{background:var(--paper2);color:var(--muted)}}
  .econ-card{{background:var(--card);border:1px solid var(--border);padding:1rem 1.1rem}}
  .ec-label{{font-family:'DM Mono',monospace;font-size:.54rem;text-transform:uppercase;color:var(--muted);margin-bottom:.3rem;letter-spacing:.07em}}
  .ec-val{{font-family:'DM Serif Display',serif;font-size:1.5rem;line-height:1;margin-bottom:.2rem}}
  .ec-sub{{font-family:'DM Mono',monospace;font-size:.52rem;color:var(--muted)}}
  footer{{max-width:1200px;margin:0 auto;padding:1.25rem 1.5rem;font-family:'DM Mono',monospace;font-size:.55rem;color:var(--muted);border-top:1px solid var(--border);line-height:1.8}}
</style>
</head>
<body>

<header>
  <div class="hi">
    <div class="logo">Property<span>Pulse</span></div>
    <div class="hmeta">
      <div>{TODAY_STR}</div>
      <div>OBMMI · PMMS · Fannie Mae ESR API · HousingWire/MBA · Fortune</div>
    </div>
    <div style="font-family:'DM Mono',monospace;font-size:.6rem;color:#a09880;text-align:right;">
      Auto-updated daily<br>Last run: {RUN_TS}
    </div>
  </div>
</header>

<div class="ticker-wrap">
  <div class="ticker">
    {ticker_str}
  </div>
</div>

<main>

  <div class="fed-note">
    <div class="fed-icon">🏦</div>
    <div>
      <h4>Federal Reserve — Rate Held at 3.50–3.75% · Next Meeting April 28–29, 2026</h4>
      <p>PMMS 30Y at <strong>{r30:.2f}%</strong> as of {pdate} — <strong>{abs(yoy):.0f}bps</strong> {"below" if yoy <= 0 else "above"} a year ago ({yago:.2f}%). 10-Year Treasury forecast: <strong>{treasury10y}</strong>. Fannie Mae ESR report date: <strong>{fannie_report_date}</strong>. OBMMI daily lock data as of <strong>{obmmi_date}</strong>.</p>
    </div>
  </div>

  <div class="slbl">Key Market Indicators · {TODAY_STR}</div>
  <div class="stat-tiles">
    <div class="stat-tile">
      <div class="st-label">PMMS 30Y FRM</div>
      <div class="st-val">{r30:.2f}%</div>
      <div class="st-sub">Freddie Mac PMMS · {pdate}</div>
      <div class="st-chg up">{dir30} from {p30:.2f}% prev week</div>
    </div>
    <div class="stat-tile">
      <div class="st-label">PMMS 15Y FRM</div>
      <div class="st-val">{r15:.2f}%</div>
      <div class="st-sub">Freddie Mac PMMS · {pdate}</div>
      <div class="st-chg up">{dir15} from {p15:.2f}% prev week</div>
    </div>
    <div class="stat-tile">
      <div class="st-label">Year-Over-Year</div>
      <div class="st-val">{abs(yoy):.0f}bps</div>
      <div class="st-sub">30Y was {yago:.2f}% a year ago</div>
      <div class="st-chg {yoy_cls}">{yoy_label}</div>
    </div>
    <div class="stat-tile">
      <div class="st-label">HPSI Sentiment</div>
      <div class="st-val">{hpsi_val}</div>
      <div class="st-sub">Fannie Mae HPSI · {hpsi_date}</div>
      <div class="st-chg pos">Home Purchase Sentiment Index</div>
    </div>
  </div>

  <div class="slbl">OBMMI Daily Rate Locks · Optimal Blue via FRED API · {obmmi_date}</div>
  <div class="rate-grid" id="rate-grid"></div>

  <div class="slbl">Full OBMMI Rate Table · Day-over-Day Comparison</div>
  <div class="tbl-wrap">
    <div class="ph"><h3>Optimal Blue Mortgage Market Indices (OBMMI)</h3><span class="badge badge-red">FRED API · OBMMI</span></div>
    <table>
      <thead><tr><th>Loan Type</th><th>Current Rate</th><th>Prior Period</th><th>Change (bps)</th><th>Trend</th></tr></thead>
      <tbody id="rate-tbody"></tbody>
    </table>
    <div class="sb"><div class="sd"></div><span>Source: Optimal Blue OBMMI via FRED API · Calculated from actual locked rates across ~35% of US mortgage transactions · Updated nightly</span></div>
  </div>

  <div class="slbl">Freddie Mac PMMS · Via FRED API</div>
  <div class="panel" style="margin-bottom:2rem;">
    <div class="ph"><h3>PMMS Weekly Survey — Latest Rates</h3><span class="badge badge-green">Freddie Mac PMMS · FRED</span></div>
    <div class="pmms-strip">
      <div class="pmms-cell">
        <div class="pmms-lbl">30Y FRM ({pdate})</div>
        <div class="pmms-val">{r30:.2f}%</div>
        <div class="pmms-sub">Weekly avg · 20% down · excellent credit</div>
      </div>
      <div class="pmms-cell">
        <div class="pmms-lbl">15Y FRM ({pdate})</div>
        <div class="pmms-val">{r15:.2f}%</div>
        <div class="pmms-sub">Weekly survey avg</div>
      </div>
      <div class="pmms-cell">
        <div class="pmms-lbl">30Y Prev Week</div>
        <div class="pmms-val">{p30:.2f}%</div>
        <div class="pmms-sub">Prior PMMS reading</div>
      </div>
      <div class="pmms-cell">
        <div class="pmms-lbl">1 Year Ago 30Y</div>
        <div class="pmms-val">{yago:.2f}%</div>
        <div class="pmms-sub">Same week last year</div>
      </div>
      <div class="pmms-cell">
        <div class="pmms-lbl">WoW Change</div>
        <div class="pmms-val" style="color:{'var(--down)' if bps30 >= 0 else 'var(--up)'};">{dir30}{abs(bps30):.0f}bps</div>
        <div class="pmms-sub">Basis points WoW</div>
      </div>
    </div>
    <div class="sb"><div class="sd"></div><span>Source: Freddie Mac PMMS via FRED API · Series MORTGAGE30US / MORTGAGE15US · Released Thursdays</span></div>
  </div>

  <div class="two-col">
    <div>
      <div class="slbl">MBA Application Activity · HousingWire / MBA</div>
      <div class="panel">
        <div class="ph"><h3>Mortgage Purchase Applications</h3><span class="badge badge-red">MBA via HousingWire</span></div>
        <div class="mba-section">{mba_html_str}</div>
        <div class="sb"><div class="sd"></div><span>MBA Weekly Mortgage Applications Survey via HousingWire · housingwire.com/mortgage-purchase-applications-index</span></div>
      </div>
    </div>
    <div>
      <div class="slbl">Latest Headlines · fortune.com/section/real-estate</div>
      <div class="panel">
        <div class="ph"><h3>Market News</h3><span class="badge badge-red">Fortune</span></div>
        {news_html_str}
        <div class="sb"><div class="sd"></div><span>Source: fortune.com/feed/section/real-estate/ · Auto-refreshed daily</span></div>
      </div>
    </div>
  </div>

  <div class="slbl">Fannie Mae ESR — {fannie_report_date} Forecast · Live via API</div>
  <div class="tbl-wrap">
    <div class="ph"><h3>30-Year Fixed Rate Forecast — Fannie Mae ESR · {fannie_report_date}</h3><span class="badge badge-gold">Fannie Mae API</span></div>
    <table class="ftable">
      <thead><tr><th>Period</th><th>Forecast Rate</th><th>Source</th><th>Signal</th></tr></thead>
      <tbody>{fannie_rows_str}</tbody>
    </table>
    <div style="padding:.85rem 1.1rem;"><p style="font-size:.72rem;line-height:1.7;color:var(--muted);">Fannie Mae ESR forecast data pulled live from the Housing Indicators API. Each monthly release updates Q1–Q4 quarterly rate projections automatically. 10-year Treasury yield forecast: <strong>{treasury10y}</strong>. GDP growth forecast (EOY {TODAY.year}): <strong>{gdp}</strong>.</p></div>
    <div class="sb"><div class="sd"></div><span>Source: Fannie Mae Housing Indicators API · api.fanniemae.com · Auto-updated monthly</span></div>
  </div>

  <div class="slbl">Fannie Mae ESR — Economic & Housing Outlook · {fannie_report_date}</div>
  <div class="three-col">
    <div class="panel">
      <div class="ph"><h3>Housing Market Outlook</h3><span class="badge badge-gold">Fannie Mae API</span></div>
      <div style="padding:1rem 1.1rem;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--border);margin-bottom:.85rem;">
          <div style="background:var(--card);padding:.75rem;">
            <div class="ec-label">Total Home Sales</div>
            <div class="ec-val">{home_sales}</div>
            <div class="ec-sub">ESR Forecast {TODAY.year}</div>
          </div>
          <div style="background:var(--card);padding:.75rem;">
            <div class="ec-label">SF Starts YoY</div>
            <div class="ec-val">{sf_starts}</div>
            <div class="ec-sub">Single-family {TODAY.year}</div>
          </div>
        </div>
        <p style="font-size:.72rem;line-height:1.65;color:var(--muted);">Both new and existing segments contributing to sales growth. Limited inventory despite lower rates keeps prices elevated. Spring season showing improving purchase applications vs last year.</p>
      </div>
      <div class="sb"><div class="sd"></div><span>Fannie Mae Housing Indicators API · {fannie_report_date}</span></div>
    </div>
    <div class="panel">
      <div class="ph"><h3>Economic Indicators</h3><span class="badge badge-gold">Fannie Mae API</span></div>
      <div style="padding:1rem 1.1rem;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--border);margin-bottom:.85rem;">
          <div style="background:var(--card);padding:.75rem;">
            <div class="ec-label">GDP Growth</div>
            <div class="ec-val">{gdp}</div>
            <div class="ec-sub">EOY {TODAY.year} Forecast</div>
          </div>
          <div style="background:var(--card);padding:.75rem;">
            <div class="ec-label">Unemployment</div>
            <div class="ec-val">{unemployment}</div>
            <div class="ec-sub">EOY {TODAY.year} Forecast</div>
          </div>
          <div style="background:var(--card);padding:.75rem;">
            <div class="ec-label">CPI Inflation</div>
            <div class="ec-val">{cpi}</div>
            <div class="ec-sub">EOY {TODAY.year} Forecast</div>
          </div>
          <div style="background:var(--card);padding:.75rem;">
            <div class="ec-label">10-Yr Treasury</div>
            <div class="ec-val">{treasury10y}</div>
            <div class="ec-sub">EOY {TODAY.year} Forecast</div>
          </div>
        </div>
      </div>
      <div class="sb"><div class="sd"></div><span>Fannie Mae Economic Indicators API · {fannie_report_date}</span></div>
    </div>
    <div class="panel">
      <div class="ph"><h3>Consumer Sentiment · HPSI</h3><span class="badge badge-gold">Fannie Mae API</span></div>
      <div style="padding:1rem 1.1rem;">
        <div style="font-family:'DM Serif Display',serif;font-size:3rem;line-height:1;margin-bottom:.3rem;">{hpsi_val}</div>
        <div style="font-family:'DM Mono',monospace;font-size:.55rem;text-transform:uppercase;color:var(--muted);margin-bottom:.75rem;">Home Purchase Sentiment Index · {hpsi_date}</div>
        <p style="font-size:.72rem;line-height:1.65;color:var(--muted);">The HPSI distills 6 key questions from Fannie Mae's monthly National Housing Survey of 1,000 consumers into a single forward-looking indicator on housing market direction. Higher = more positive sentiment toward buying.</p>
      </div>
      <div class="sb"><div class="sd"></div><span>Fannie Mae National Housing Survey API · /v1/nhs/hpsi · Monthly</span></div>
    </div>
  </div>

</main>

<footer>
  <strong>PropertyPulse</strong> — Real Estate Market Tracker &nbsp;|&nbsp;
  Auto-updated daily via GitHub Actions &nbsp;|&nbsp;
  OBMMI: Optimal Blue via FRED API (fred.stlouisfed.org) &nbsp;·&nbsp;
  PMMS: Freddie Mac via FRED API &nbsp;·&nbsp;
  Fannie Mae ESR: Housing Indicators + Economic Indicators + NHS/HPSI APIs (api.fanniemae.com) &nbsp;·&nbsp;
  MBA Weekly Applications via HousingWire &nbsp;·&nbsp;
  Headlines: fortune.com/section/real-estate &nbsp;|&nbsp;
  Not financial advice. &nbsp;|&nbsp; Last updated: {RUN_TS}
</footer>

<script>
const RATES = {rates_json};
function renderCard(r) {{
  var u = r.bps >= 0;
  var pct = Math.min(100, Math.round(r.rate/8*100));
  var dir = u ? 'up' : 'dn';
  var arrow = u ? '\u25b2' : '\u25bc';
  return '<div class="rate-card">'
    + '<div class="rc-label">' + r.lb + '</div>'
    + '<div class="rc-value">' + r.rate.toFixed(3) + '%</div>'
    + '<div class="rc-chg ' + dir + '">' + arrow + ' ' + Math.abs(r.bps) + 'bps</div>'
    + '<div class="rc-prev">Prev: ' + r.prev.toFixed(3) + '%</div>'
    + '<div class="rc-bar" style="width:' + pct + '%"></div>'
    + '</div>';
}}
function renderRow(r) {{
  var u = r.bps >= 0;
  var bp = Math.min(100, Math.round(Math.abs(r.bps)/25*100));
  var dir = u ? 'up' : 'dn';
  var arrow = u ? '\u25b2' : '\u25bc';
  var col = u ? 'var(--down)' : 'var(--up)';
  return '<tr>'
    + '<td class="td-type">' + r.type + '</td>'
    + '<td class="td-rate">' + r.rate.toFixed(3) + '%</td>'
    + '<td class="td-prev">' + r.prev.toFixed(3) + '%</td>'
    + '<td class="td-bps ' + dir + '">' + arrow + ' ' + Math.abs(r.bps) + '</td>'
    + '<td><div class="bar-wrap"><div class="bar-fill" style="width:' + bp + '%;background:' + col + '"></div></div></td>'
    + '</tr>';
}}
document.getElementById('rate-grid').innerHTML = RATES.map(renderCard).join('');
document.getElementById('rate-tbody').innerHTML = RATES.map(renderRow).join('');
</script>
</body>
</html>"""

# ── ENTRY POINT ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{'='*60}\nPropertyPulse scraper — {RUN_TS}\n{'='*60}\n")

    if not FRED_KEY:
        print("WARNING: FRED_API_KEY not set\n")
    if not FANNIE_CLIENT_ID or not FANNIE_CLIENT_SECRET:
        print("WARNING: FANNIE_CLIENT_ID / FANNIE_CLIENT_SECRET not set\n")

    rates    = fetch_obmmi()
    pmms     = fetch_pmms()
    housing  = fetch_fannie_housing()
    economic = fetch_fannie_economic()
    hpsi     = fetch_fannie_hpsi()
    rali     = fetch_fannie_rali()
    news     = fetch_fortune_news()
    mba      = fetch_mba()

    html = build_html(rates, pmms, housing, economic, hpsi, rali, news, mba)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n{'='*60}")
    print(f"Done — index.html written ({len(html):,} bytes)")
    print(f"  OBMMI 30Y   : {rates[0]['rate'] if rates else 'N/A'}%")
    print(f"  PMMS 30Y    : {pmms.get('rate_30y')}%")
    print(f"  FM 30Y fcst : {housing.get('mortgage_rate_30y')}")
    print(f"  HPSI        : {hpsi['value'] if hpsi else 'N/A'}")
    print(f"  Fortune news: {len(news)} articles")
    print(f"  MBA weeks   : {len(mba.get('weeks', []))}")
    print(f"{'='*60}\n")
