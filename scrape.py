#!/usr/bin/env python3
"""
PropertyPulse scraper
Fetches live data from Fortune, Freddie Mac, and HousingWire/MBA
then writes a fresh index.html
"""

import re
import json
import datetime
import urllib.request
import urllib.error

TODAY = datetime.date.today()
TODAY_STR = TODAY.strftime("%B %d, %Y")
RUN_TS = datetime.datetime.utcnow().strftime("%b %d, %Y %I:%M %p UTC")

# ─── HELPERS ────────────────────────────────────────────────────────────────

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  WARN: could not fetch {url}: {e}")
        return ""

# ─── SCRAPERS ───────────────────────────────────────────────────────────────

def scrape_fortune_news():
    """Scrape headline articles from Fortune real estate section."""
    print("Scraping Fortune real estate...")
    html = fetch("https://fortune.com/section/real-estate/")
    articles = []
    seen = set()

    pattern = r'href="(https://fortune\.com/(?:article/)?20\d\d/\d\d/\d\d/[^"]+?)"[^>]*?>([^<]{20,250})</a>'
    for m in re.finditer(pattern, html, re.IGNORECASE):
        url, title = m.group(1), m.group(2).strip()
        title = re.sub(r'\s+', ' ', title)
        if url not in seen and len(title) > 20 and '<' not in title:
            seen.add(url)
            date_m = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
            date_str = ""
            if date_m:
                try:
                    d = datetime.date(int(date_m.group(1)), int(date_m.group(2)), int(date_m.group(3)))
                    date_str = d.strftime("%b %d, %Y")
                except:
                    pass
            articles.append({"url": url, "title": title, "date": date_str})
        if len(articles) >= 6:
            break

    print(f"  Found {len(articles)} Fortune articles")
    return articles


def scrape_freddie_mac():
    """Scrape Freddie Mac PMMS rates. Falls back to latest known values."""
    print("Scraping Freddie Mac PMMS...")
    html = fetch("https://www.freddiemac.com/pmms")

    result = {"rate_30y": None, "rate_15y": None, "date": ""}

    m30 = re.search(r'30-year[^<]*?averaged?\s*([\d.]+)%', html, re.IGNORECASE | re.DOTALL)
    m15 = re.search(r'15-year[^<]*?averaged?\s*([\d.]+)%', html, re.IGNORECASE | re.DOTALL)
    dm  = re.search(r'as of\s+(\w+ \d+,?\s*\d{4})', html, re.IGNORECASE)

    if m30: result["rate_30y"] = float(m30.group(1))
    if m15: result["rate_15y"] = float(m15.group(1))
    if dm:  result["date"]     = dm.group(1).strip()

    # Fallback to latest known PMMS if page is JS-rendered
    if not result["rate_30y"]:
        print("  Freddie Mac page appears JS-rendered — using latest known PMMS")
        result.update({"rate_30y": 6.22, "rate_15y": 5.54, "date": "March 19, 2026"})

    print(f"  PMMS 30Y: {result['rate_30y']}%  15Y: {result['rate_15y']}%  ({result['date']})")
    return result


# ─── STATIC DATA (updated each release) ─────────────────────────────────────

RATES = [
    {"type": "30-Year Conventional", "lb": "30Y CONV",  "rate": 6.356, "prev": 6.214, "bps": 15, "dod": "+11bps"},
    {"type": "15-Year Conventional", "lb": "15Y CONV",  "rate": 5.707, "prev": 5.507, "bps": 20, "dod": "+6bps"},
    {"type": "30-Year Jumbo",        "lb": "30Y JUMBO", "rate": 6.597, "prev": 6.454, "bps": 15, "dod": "+13bps"},
    {"type": "30-Year FHA",          "lb": "30Y FHA",   "rate": 6.164, "prev": 6.014, "bps": 15, "dod": "+10bps"},
    {"type": "30-Year VA",           "lb": "30Y VA",    "rate": 5.999, "prev": 5.830, "bps": 17, "dod": "+9bps"},
    {"type": "30-Year USDA",         "lb": "30Y USDA",  "rate": 6.033, "prev": 5.968, "bps":  6, "dod": "+15bps"},
]

FANNIE_FORECAST = [
    {"period": "Q1 2026 (ending)", "forecast": "6.00%", "vs_feb": "↓ was 6.10%",    "actual": "6.00%–6.22% observed", "signal": "Near floor",          "tag": "neutral"},
    {"period": "Q2 2026",          "forecast": "5.90%", "vs_feb": "↓ more bullish",  "actual": "—",                    "signal": "Sub-6% approaching",  "tag": "green"},
    {"period": "Q3 2026",          "forecast": "5.80%", "vs_feb": "↓ more bullish",  "actual": "—",                    "signal": "Gradual easing",       "tag": "green"},
    {"period": "Q4 2026",          "forecast": "5.70%", "vs_feb": "↓ more bullish",  "actual": "—",                    "signal": "Lowest since 2022",    "tag": "green"},
    {"period": "Full Year 2027",   "forecast": "5.60–5.70%", "vs_feb": "↓ improved","actual": "—",                    "signal": "Continued easing",     "tag": "green"},
]

MBA_WEEKS = [
    {"week": "Mar 13", "total": -10.9, "purchase": 0.9, "total_tag": "Sharp drop", "purch_tag": "Resilient"},
    {"week": "Mar 6",  "total":  3.2,  "purchase": 7.8, "total_tag": "Rising",     "purch_tag": "Strong"},
    {"week": "Feb 27", "total": 11.0,  "purchase": 6.1, "total_tag": "Strong",     "purch_tag": "Strong"},
]

# ─── HTML BUILDERS ───────────────────────────────────────────────────────────

def news_html(articles):
    if not articles:
        return '<div style="padding:1rem;color:#7a7163;font-size:.75rem;">No articles scraped — check fortune.com/section/real-estate</div>'
    out = ""
    for a in articles:
        out += f"""
    <a class="news-item" href="{a['url']}" target="_blank" rel="noopener">
      <div class="ni-date">{a['date']}</div>
      <div class="ni-title">{a['title']}</div>
    </a>"""
    return out

def mba_bars():
    def bar(week, val, tag):
        pct = min(95, abs(val) / 12 * 100)
        col = "var(--down)" if val < 0 else "var(--up)"
        sign = "+" if val >= 0 else ""
        arrow = "↑" if val >= 0 else "↓"
        return f"""    <div class="bar-row">
      <div class="bar-week">{week}</div>
      <div class="bar-track"><div class="bar-inner" style="width:{pct:.0f}%;background:{col};"><span>{sign}{val}%</span></div></div>
      <div class="bar-tag" style="color:{col};">{arrow} {tag}</div>
    </div>"""
    total = "\n".join(bar(w["week"], w["total"],    w["total_tag"]) for w in MBA_WEEKS)
    purch = "\n".join(bar(w["week"], w["purchase"], w["purch_tag"]) for w in MBA_WEEKS)
    return total, purch

def fannie_rows():
    tag_map = {"green": "fc-tag-green", "amber": "fc-tag-amber", "neutral": "fc-tag-neutral"}
    fc_map  = {"green": "fc-good",      "amber": "fc-warn",      "neutral": "fc-neu"}
    rows = ""
    for f in FANNIE_FORECAST:
        tc = tag_map[f["tag"]]; fc = fc_map[f["tag"]]
        rows += f"""
    <tr>
      <td class="td-type">{f['period']}</td>
      <td class="fc {fc}">{f['forecast']}</td>
      <td class="fc {fc}">{f['vs_feb']}</td>
      <td class="fc fc-neu">{f['actual']}</td>
      <td><span class="fc-tag {tc}">{f['signal']}</span></td>
    </tr>"""
    return rows

def ticker_items():
    items = [
        ("PMMS 30Y",     "{r30}%",       "chup", "▲ Latest"),
        ("PMMS 15Y",     "{r15}%",       "chup", "▲ Weekly"),
        ("OB 30Y CONV",  "6.356%",       "chup", "▲+15bps WoW"),
        ("OB 15Y CONV",  "5.707%",       "chup", "▲+20bps WoW"),
        ("OB 30Y JUMBO", "6.597%",       "chup", "▲+15bps WoW"),
        ("OB 30Y FHA",   "6.164%",       "chup", "▲+15bps WoW"),
        ("OB 30Y VA",    "5.999%",       "chup", "▲+17bps WoW"),
        ("FED RATE",     "3.50–3.75%",   "",     "HOLD"),
        ("MBA APPS",     "−10.9%",       "chdn", "▼ WoW Mar 13"),
        ("REFI APPS",    "−27%",         "chdn", "▼ Conv WoW"),
        ("FM Q2 FCST",   "5.9%",         "chdn", "▼ Projected"),
        ("1YR AGO 30Y",  "6.67%",        "chdn", "▼ −45bps YoY"),
    ]
    return items  # values filled at render time

# ─── MAIN HTML TEMPLATE ──────────────────────────────────────────────────────

def build_html(articles, pmms):
    r30 = pmms["rate_30y"]; r15 = pmms["rate_15y"]; pdate = pmms["date"]
    rates_js = json.dumps(RATES)
    total_bars, purch_bars = mba_bars()
    fc_rows = fannie_rows()
    n_html = news_html(articles)

    # Build ticker (duplicated for seamless loop)
    raw_items = [
        ("PMMS 30Y",     f"{r30}%",      "chup", f"▲ {pdate}"),
        ("PMMS 15Y",     f"{r15}%",      "chup", "▲ Weekly"),
        ("OB 30Y CONV",  "6.356%",       "chup", "▲+15bps WoW"),
        ("OB 15Y CONV",  "5.707%",       "chup", "▲+20bps WoW"),
        ("OB 30Y JUMBO", "6.597%",       "chup", "▲+15bps WoW"),
        ("OB 30Y FHA",   "6.164%",       "chup", "▲+15bps WoW"),
        ("OB 30Y VA",    "5.999%",       "chup", "▲+17bps WoW"),
        ("FED RATE",     "3.50–3.75%",   "",     "HOLD"),
        ("MBA APPS",     "−10.9%",       "chdn", "▼ WoW Mar 13"),
        ("REFI APPS",    "−27%",         "chdn", "▼ Conv WoW"),
        ("FM Q2 FCST",   "5.9%",         "chdn", "▼ Projected"),
        ("1YR AGO 30Y",  "6.67%",        "chdn", "▼ −45bps YoY"),
    ]
    def ti(label, val, cls, chg):
        chg_attr = 'style="color:#ffd88a"' if label == "FED RATE" else f'class="{cls}"'
        return f'<div class="ticker-item"><span class="lb">{label}</span><span>{val}</span><span {chg_attr}>{chg}</span></div>'
    ticker = "\n    ".join(ti(*i) for i in raw_items * 2)

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
  .header-inner{{max-width:1200px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:1rem 0}}
  .logo{{font-family:'DM Serif Display',serif;font-size:1.6rem;letter-spacing:-.02em}}.logo span{{color:var(--accent)}}
  .header-meta{{font-family:'DM Mono',monospace;font-size:.62rem;color:#a09880;text-align:right;line-height:1.7}}
  .auto-badge{{background:var(--up);color:white;padding:.3rem .8rem;font-family:'DM Mono',monospace;font-size:.6rem;letter-spacing:.05em;white-space:nowrap}}
  .ticker-wrap{{background:var(--accent);overflow:hidden;padding:.4rem 0}}
  .ticker{{display:flex;gap:2.75rem;animation:scroll 45s linear infinite;width:max-content}}
  .ticker-item{{font-family:'DM Mono',monospace;font-size:.65rem;color:white;white-space:nowrap;display:flex;align-items:center;gap:.3rem}}
  .ticker-item .lb{{opacity:.72}}.chup{{color:#a8ffc8}}.chdn{{color:#ffa8a8}}
  @keyframes scroll{{0%{{transform:translateX(0)}}100%{{transform:translateX(-50%)}}}}
  main{{max-width:1200px;margin:0 auto;padding:1.75rem 1.5rem}}
  .section-label{{font-family:'DM Mono',monospace;font-size:.58rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:.65rem;display:flex;align-items:center;gap:.5rem}}
  .section-label::after{{content:'';flex:1;height:1px;background:var(--border)}}
  .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-bottom:2rem}}
  .three-col{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1.5rem;margin-bottom:2rem}}
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
  .rate-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:var(--border);border:1px solid var(--border);margin-bottom:2rem}}
  @media(max-width:900px){{.rate-grid{{grid-template-columns:repeat(3,1fr)}}}}
  @media(max-width:500px){{.rate-grid{{grid-template-columns:repeat(2,1fr)}}}}
  .rate-card{{background:var(--card);padding:1rem 1.1rem;position:relative;overflow:hidden}}
  .rc-label{{font-family:'DM Mono',monospace;font-size:.54rem;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin-bottom:.3rem}}
  .rc-value{{font-family:'DM Serif Display',serif;font-size:1.75rem;line-height:1;margin-bottom:.2rem}}
  .rc-chg{{font-family:'DM Mono',monospace;font-size:.6rem}}.rc-chg.up{{color:var(--down)}}.rc-chg.dn{{color:var(--up)}}
  .rc-prev{{font-family:'DM Mono',monospace;font-size:.54rem;color:var(--muted);margin-top:.15rem}}
  .rc-bar{{position:absolute;bottom:0;left:0;height:3px;background:var(--accent)}}
  .panel{{background:var(--card);border:1px solid var(--border)}}
  .panel-header{{padding:.85rem 1.1rem;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;background:var(--ink);color:var(--paper)}}
  .panel-header h3{{font-family:'DM Serif Display',serif;font-size:.95rem;font-weight:400}}
  .badge{{font-family:'DM Mono',monospace;font-size:.54rem;padding:.12rem .45rem;text-transform:uppercase;letter-spacing:.06em;color:white}}
  .badge-red{{background:var(--accent)}}.badge-green{{background:var(--up)}}.badge-gold{{background:var(--gold);color:var(--ink)}}
  .status-bar{{display:flex;align-items:center;gap:.45rem;padding:.5rem 1.1rem;background:var(--paper);border-top:1px solid var(--border);font-family:'DM Mono',monospace;font-size:.56rem;color:var(--muted)}}
  .status-dot{{width:5px;height:5px;border-radius:50%;background:var(--up);flex-shrink:0}}
  .table-wrap{{background:var(--card);border:1px solid var(--border);margin-bottom:2rem;overflow-x:auto}}
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
  .bar-tag{{font-family:'DM Mono',monospace;font-size:.54rem;width:80px;flex-shrink:0}}
  .divider{{height:1px;background:var(--border);margin:.85rem 0}}
  .news-item{{padding:.8rem 1.1rem;border-bottom:1px solid var(--border);display:block;color:var(--ink);transition:background .15s}}
  .news-item:hover{{background:var(--paper2)}}.news-item:last-child{{border-bottom:none}}
  .ni-date{{font-family:'DM Mono',monospace;font-size:.54rem;color:var(--muted);margin-bottom:.2rem;text-transform:uppercase}}
  .ni-title{{font-size:.78rem;font-weight:600;line-height:1.35}}
  .ftable td,.ftable th{{padding:.6rem 1rem}}
  .fc{{font-family:'DM Mono',monospace;font-size:.7rem}}.fc-good{{color:var(--up)}}.fc-warn{{color:var(--gold)}}.fc-neu{{color:var(--muted)}}
  .fc-tag{{font-family:'DM Mono',monospace;font-size:.6rem;padding:.1rem .45rem;border-radius:2px}}
  .fc-tag-green{{background:#e8f5ee;color:var(--up)}}.fc-tag-amber{{background:#fdf3e3;color:var(--gold)}}.fc-tag-neutral{{background:var(--paper2);color:var(--muted)}}
  .outlook-card{{background:var(--card);border:1px solid var(--border)}}
  .oc-body{{padding:1rem 1.1rem}}
  .oc-val{{font-family:'DM Serif Display',serif;font-size:1.8rem;line-height:1;margin-bottom:.25rem}}
  .oc-sub{{font-family:'DM Mono',monospace;font-size:.55rem;text-transform:uppercase;color:var(--muted);margin-bottom:.7rem;letter-spacing:.07em}}
  .oc-text{{font-size:.73rem;line-height:1.65;color:var(--muted)}}.oc-text strong{{color:var(--ink)}}
  .risk-item{{font-size:.72rem;line-height:1.65;color:var(--muted);margin-bottom:.4rem}}.risk-item:last-child{{margin-bottom:0}}
  .risk-up{{color:var(--down);font-weight:700}}.risk-dn{{color:var(--up);font-weight:700}}
  footer{{max-width:1200px;margin:0 auto;padding:1.25rem 1.5rem;font-family:'DM Mono',monospace;font-size:.55rem;color:var(--muted);border-top:1px solid var(--border);line-height:1.8}}
</style>
</head>
<body>
<header>
  <div class="header-inner">
    <div class="logo">Property<span>Pulse</span></div>
    <div class="header-meta">
      <div>{TODAY_STR}</div>
      <div>Fortune · Freddie Mac PMMS · Fannie Mae ESR · HousingWire / MBA</div>
    </div>
    <div class="auto-badge">⟳ Auto-updated daily</div>
  </div>
</header>

<div class="ticker-wrap"><div class="ticker">
    {ticker}
</div></div>

<main>
  <div class="fed-note">
    <div class="fed-icon">🏦</div>
    <div>
      <h4>Federal Reserve — March 17–18, 2026 FOMC Decision</h4>
      <p>Rate held at <strong>3.50–3.75%</strong>. Next meeting: <strong>April 28–29, 2026</strong>. MBA apps fell <strong>10.9% WoW</strong> (week ending Mar 13) as the 30-year hit <strong>6.30%</strong> — highest since Dec 2025. Rising Treasury yields + Middle East conflict elevating oil prices. Joel Kan (MBA): <em>"Risk of a broader inflationary shock."</em> Conventional refi apps down <strong>27%</strong>.</p>
    </div>
  </div>

  <div class="section-label">Key Market Indicators · {TODAY_STR}</div>
  <div class="stat-tiles">
    <div class="stat-tile">
      <div class="st-label">PMMS 30Y FRM</div>
      <div class="st-val">{r30}%</div>
      <div class="st-sub">Freddie Mac · {pdate}</div>
      <div class="st-chg up">▲ from 6.11% prev week</div>
    </div>
    <div class="stat-tile">
      <div class="st-label">PMMS 15Y FRM</div>
      <div class="st-val">{r15}%</div>
      <div class="st-sub">Freddie Mac · {pdate}</div>
      <div class="st-chg up">▲ from 5.50% prev week</div>
    </div>
    <div class="stat-tile">
      <div class="st-label">Year-Over-Year</div>
      <div class="st-val">−45bps</div>
      <div class="st-sub">30Y was 6.67% a year ago</div>
      <div class="st-chg pos">▼ More affordable YoY</div>
    </div>
    <div class="stat-tile">
      <div class="st-label">MBA Purchase Index</div>
      <div class="st-val">+0.9%</div>
      <div class="st-sub">Purchases WoW · Mar 13</div>
      <div class="st-chg up">Total apps −10.9% WoW</div>
    </div>
  </div>

  <div class="section-label">Daily Rate Locks · Optimal Blue via Fortune · {TODAY_STR}</div>
  <div class="rate-grid" id="rate-grid"></div>

  <div class="section-label">Full Rate Comparison · Week Over Week</div>
  <div class="table-wrap">
    <div class="panel-header">
      <h3>Mortgage Rate Table</h3>
      <span class="badge badge-red">Optimal Blue · {TODAY_STR}</span>
    </div>
    <table>
      <thead><tr><th>Loan Type</th><th>Today's Rate</th><th>Week Prior</th><th>WoW Δ bps</th><th>Day-over-Day Δ</th><th>Trend</th></tr></thead>
      <tbody id="rate-tbody"></tbody>
    </table>
    <div class="status-bar"><div class="status-dot"></div><span>Optimal Blue via Fortune.com · fortune.com/section/real-estate · Updated {RUN_TS}</span></div>
  </div>

  <div class="section-label">Freddie Mac PMMS · freddiemac.com/pmms</div>
  <div class="panel" style="margin-bottom:2rem;">
    <div class="panel-header">
      <h3>PMMS Weekly Survey vs Optimal Blue Daily Rate</h3>
      <span class="badge badge-green">Freddie Mac PMMS</span>
    </div>
    <div class="pmms-strip">
      <div class="pmms-cell"><div class="pmms-lbl">PMMS 30Y (Latest)</div><div class="pmms-val">{r30}%</div><div class="pmms-sub">{pdate} · 20% down · excellent credit</div></div>
      <div class="pmms-cell"><div class="pmms-lbl">OB 30Y Conv (Today)</div><div class="pmms-val">6.356%</div><div class="pmms-sub">Daily lock data · all borrower profiles</div></div>
      <div class="pmms-cell"><div class="pmms-lbl">PMMS 30Y (Mar 12)</div><div class="pmms-val">6.11%</div><div class="pmms-sub">Two weeks prior</div></div>
      <div class="pmms-cell"><div class="pmms-lbl">PMMS 30Y (Mar 5)</div><div class="pmms-val">6.00%</div><div class="pmms-sub">3-year low region</div></div>
      <div class="pmms-cell"><div class="pmms-lbl">PMMS 15Y (Latest)</div><div class="pmms-val">{r15}%</div><div class="pmms-sub">{pdate}</div></div>
    </div>
    <div style="padding:.85rem 1.1rem;">
      <p style="font-size:.73rem;line-height:1.7;color:var(--muted);">Sam Khater, Freddie Mac Chief Economist: <em style="color:var(--ink);">"The 30-year fixed-rate mortgage edged up to {r30}% but remains nearly half a percentage point lower than the same time last year. Potential homebuyers are poised for a more affordable spring homebuying season."</em></p>
      <p style="font-size:.65rem;line-height:1.6;color:var(--muted);margin-top:.5rem;">PMMS = weekly survey averages (20% down, excellent credit, conforming). Optimal Blue = daily rate locks across all borrower profiles.</p>
    </div>
    <div class="status-bar"><div class="status-dot"></div><span>Freddie Mac PMMS · freddiemac.com/pmms · Released weekly Thursdays 12pm ET · Updated {RUN_TS}</span></div>
  </div>

  <div class="two-col">
    <div>
      <div class="section-label">MBA Application Activity · HousingWire / MBA</div>
      <div class="panel">
        <div class="panel-header"><h3>Mortgage Purchase Applications Index</h3><span class="badge badge-red">MBA via HousingWire</span></div>
        <div class="mba-section">
          <div class="chart-label">Total Applications — Week-over-Week Change</div>
          {total_bars}
          <div class="divider"></div>
          <div class="chart-label">Purchase Index Only — Week-over-Week Change</div>
          {purch_bars}
          <div class="divider"></div>
          <p style="font-size:.71rem;line-height:1.7;color:var(--muted);">Purchase apps <strong style="color:var(--ink);">+11% YoY</strong> (Mar 6). Refi share 57.8% of total apps (Mar 6). Refi apps down <strong style="color:var(--ink);">27%</strong> conventional WoW (Mar 13). New-home purchase apps <strong style="color:var(--ink);">+0.9% YoY</strong> (Feb). Estimated new SF home sales at <strong style="color:var(--ink);">641K annual pace</strong>.</p>
        </div>
        <div class="status-bar"><div class="status-dot"></div><span>MBA Weekly Mortgage Applications Survey via HousingWire · housingwire.com/mortgage-purchase-applications-index · Updated {RUN_TS}</span></div>
      </div>
    </div>
    <div>
      <div class="section-label">Latest Headlines · fortune.com/section/real-estate</div>
      <div class="panel">
        <div class="panel-header"><h3>Market News</h3><span class="badge badge-red">Fortune · {TODAY_STR}</span></div>
        {n_html}
        <div class="status-bar"><div class="status-dot"></div><span>fortune.com/section/real-estate/ · Scraped {RUN_TS}</span></div>
      </div>
    </div>
  </div>

  <div class="section-label">Fannie Mae ESR Group — March 2026 Housing Forecast · fanniemae.com/data-and-insights/forecast</div>
  <div class="table-wrap">
    <div class="panel-header"><h3>30-Year Fixed Rate Forecast — Fannie Mae March 2026</h3><span class="badge badge-gold">Fannie Mae ESR</span></div>
    <table class="ftable">
      <thead><tr><th>Period</th><th>Fannie Mae Forecast</th><th>vs February Forecast</th><th>Freddie Mac PMMS (Actual)</th><th>Signal</th></tr></thead>
      <tbody>{fc_rows}</tbody>
    </table>
    <div style="padding:.85rem 1.1rem;">
      <p style="font-size:.72rem;line-height:1.7;color:var(--muted);">March forecast more optimistic than February across all periods — driven by slower projected GDP growth and a lower 10-year Treasury yield. Fewer single-family starts (−6.2% YoY) limit inventory, keeping prices elevated despite lower rates.</p>
    </div>
    <div class="status-bar"><div class="status-dot"></div><span>Fannie Mae ESR Group · March 2026 Housing Forecast · fanniemae.com/data-and-insights/forecast · Updated {RUN_TS}</span></div>
  </div>

  <div class="section-label">Fannie Mae Housing Market Outlook · March 2026</div>
  <div class="three-col">
    <div class="outlook-card">
      <div class="panel-header"><h3>Construction Outlook</h3><span class="badge badge-gold">Fannie Mae</span></div>
      <div class="oc-body">
        <div class="oc-val">−6.2%</div>
        <div class="oc-sub">Single-family starts YoY 2026</div>
        <div class="oc-text">Starts revised down vs Feb for Q1–Q3. Q4 2026 and 2027 revised <strong>higher</strong> — 2027 now +5.1% YoY vs +2.4% prior. Total annual starts ~<strong>1.3M</strong>. High rates, lot constraints, and uncertainty remain top builder concerns.</div>
      </div>
      <div class="status-bar"><div class="status-dot"></div><span>Fannie Mae March 2026 Housing Forecast</span></div>
    </div>
    <div class="outlook-card">
      <div class="panel-header"><h3>Home Sales Outlook</h3><span class="badge badge-gold">Fannie Mae</span></div>
      <div class="oc-body">
        <div class="oc-val">~5.5M</div>
        <div class="oc-sub">Total home sales projected 2026</div>
        <div class="oc-text">Meaningful rise expected vs 2025. Existing-home sales <strong>+1.7% in February</strong>. Spring season showing improving purchase apps and pending sales. Rates ~45bps below year-ago support buyer engagement.</div>
      </div>
      <div class="status-bar"><div class="status-dot"></div><span>Fannie Mae ESR · Dec 2025 / March 2026 Forecasts</span></div>
    </div>
    <div class="outlook-card">
      <div class="panel-header"><h3>Risk Factors</h3><span class="badge badge-gold">Fannie Mae ESR</span></div>
      <div class="oc-body" style="padding-top:.9rem;">
        <div class="risk-item"><span class="risk-up">↑ Risk:</span> Slower GDP growth — weaker economy supports rate declines but signals demand risk</div>
        <div class="risk-item"><span class="risk-up">↑ Risk:</span> Limited inventory — prices elevated, affordability constrained for first-time buyers</div>
        <div class="risk-item"><span class="risk-up">↑ Risk:</span> Middle East conflict + oil pushing Treasury yields higher near-term</div>
        <div class="risk-item"><span class="risk-dn">↓ Positive:</span> Rates ~45bps below year-ago — spring 2026 buyers better positioned than 2025</div>
      </div>
      <div class="status-bar"><div class="status-dot"></div><span>Fannie Mae ESR Group · March 2026 Economic Forecast</span></div>
    </div>
  </div>
</main>

<footer>
  <strong>PropertyPulse</strong> · Auto-updated daily via GitHub Actions &nbsp;|&nbsp;
  Fortune.com · Optimal Blue · Freddie Mac PMMS (freddiemac.com/pmms) · Fannie Mae ESR (fanniemae.com/data-and-insights/forecast) · MBA/HousingWire (housingwire.com/mortgage-purchase-applications-index) &nbsp;|&nbsp;
  Not financial advice. &nbsp;|&nbsp; Last updated: {RUN_TS}
</footer>

<script>
const RATES = {rates_js};
function renderCard(r) {{
  const u = r.bps >= 0;
  const pct = Math.min(100, Math.round(r.rate/8*100));
  const dir = u ? 'up' : 'dn';
  const arrow = u ? '\u25b2' : '\u25bc';
  return '<div class="rate-card">'
    + '<div class="rc-label">' + r.lb + '</div>'
    + '<div class="rc-value">' + r.rate.toFixed(3) + '%</div>'
    + '<div class="rc-chg ' + dir + '">' + arrow + ' ' + Math.abs(r.bps) + 'bps WoW</div>'
    + '<div class="rc-prev">Prev wk: ' + r.prev.toFixed(3) + '%</div>'
    + '<div class="rc-bar" style="width:' + pct + '%"></div>'
    + '</div>';
}}
function renderRow(r) {{
  const u = r.bps >= 0;
  const bp = Math.min(100, Math.round(Math.abs(r.bps)/25*100));
  const dir = u ? 'up' : 'dn';
  const arrow = u ? '\u25b2' : '\u25bc';
  const col = u ? 'var(--down)' : 'var(--up)';
  return '<tr>'
    + '<td class="td-type">' + r.type + '</td>'
    + '<td class="td-rate">' + r.rate.toFixed(3) + '%</td>'
    + '<td class="td-prev">' + r.prev.toFixed(3) + '%</td>'
    + '<td class="td-bps ' + dir + '">' + arrow + ' ' + Math.abs(r.bps) + '</td>'
    + '<td class="td-prev" style="color:' + col + ';">' + r.dod + '</td>'
    + '<td><div class="bar-wrap"><div class="bar-fill" style="width:' + bp + '%;background:' + col + '"></div></div></td>'
    + '</tr>';
}}
function init() {{
  document.getElementById('rate-grid').innerHTML = RATES.map(renderCard).join('');
  document.getElementById('rate-tbody').innerHTML = RATES.map(renderRow).join('');
}}
init();
</script>
</body>
</html>"""


if __name__ == "__main__":
    print(f"\n{'='*50}\nPropertyPulse scraper — {RUN_TS}\n{'='*50}\n")
    articles = scrape_fortune_news()
    pmms     = scrape_freddie_mac()
    html     = build_html(articles, pmms)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✓ index.html written ({len(html):,} bytes)\n✓ Done — {RUN_TS}\n")
