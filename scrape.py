#!/usr/bin/env python3
"""
PropertyPulse scraper
Fetches live data from:
  - Freddie Mac PMMS (Excel archive)
  - Fortune Real Estate (RSS feed)
  - MBA mortgage applications (via HousingWire RSS)
  - Fannie Mae forecast (static — updated quarterly, hardcoded)
Then writes index.html
"""

import requests
import re
import json
import openpyxl
import io
from datetime import datetime, date
from bs4 import BeautifulSoup

# ── helpers ──────────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def get(url, **kwargs):
    r = requests.get(url, headers=HEADERS, timeout=20, **kwargs)
    r.raise_for_status()
    return r

# ── 1. FREDDIE MAC PMMS (public Excel archive) ────────────────────────────────
def fetch_pmms():
    print("Fetching Freddie Mac PMMS...")
    try:
        url = "https://www.freddiemac.com/pmms/docs/historicalweeklydata.xlsx"
        r = get(url)
        wb = openpyxl.load_workbook(io.BytesIO(r.content), data_only=True)
        ws = wb.active

        # Find the last row with data
        rows = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] and row[1]:
                rows.append(row)

        if not rows:
            raise ValueError("No PMMS data found")

        # Most recent row
        latest = rows[-1]
        prev   = rows[-2] if len(rows) >= 2 else latest

        # Column 0 = date, 1 = 30Y rate, 2 = 15Y rate
        def safe_float(v):
            try:
                return round(float(v), 2)
            except (TypeError, ValueError):
                return None

        rate_30 = safe_float(latest[1])
        rate_15 = safe_float(latest[2])
        prev_30 = safe_float(prev[1])
        prev_15 = safe_float(prev[2])

        # Date might be a datetime or string
        d = latest[0]
        if hasattr(d, 'strftime'):
            pmms_date = d.strftime("%b %d, %Y")
        else:
            pmms_date = str(d)

        # Year-ago row (52 rows back)
        yago = rows[-53] if len(rows) >= 53 else None
        rate_30_yago = safe_float(yago[1]) if yago else None

        return {
            "date": pmms_date,
            "rate_30": rate_30,
            "rate_15": rate_15,
            "prev_30": prev_30,
            "prev_15": prev_15,
            "rate_30_yago": rate_30_yago,
            "bps_30": round((rate_30 - prev_30) * 100, 1) if rate_30 and prev_30 else None,
            "bps_15": round((rate_15 - prev_15) * 100, 1) if rate_15 and prev_15 else None,
            "yoy_bps": round((rate_30 - rate_30_yago) * 100, 1) if rate_30 and rate_30_yago else None,
        }
    except Exception as e:
        print(f"  PMMS error: {e}")
        return None

# ── 2. FORTUNE REAL ESTATE RSS ────────────────────────────────────────────────
def fetch_fortune_news():
    print("Fetching Fortune Real Estate RSS...")
    try:
        r = get("https://fortune.com/feed/section/real-estate/")
        soup = BeautifulSoup(r.content, "xml")
        items = soup.find_all("item")[:8]

        news = []
        for item in items:
            title = item.find("title")
            link  = item.find("link")
            desc  = item.find("description") or item.find("summary")
            pub   = item.find("pubDate")

            title_txt = title.get_text(strip=True) if title else ""
            link_txt  = link.get_text(strip=True) if link else (link.next_sibling or "")
            desc_txt  = BeautifulSoup(
                desc.get_text(strip=True) if desc else "", "html.parser"
            ).get_text(strip=True)[:160]

            # Parse date
            date_str = ""
            if pub:
                try:
                    dt = datetime.strptime(pub.get_text(strip=True), "%a, %d %b %Y %H:%M:%S %z")
                    date_str = dt.strftime("%b %d, %Y")
                except Exception:
                    date_str = pub.get_text(strip=True)[:16]

            # Filter to real estate relevant
            keywords = ["mortgage", "home", "housing", "real estate", "rate", "fed",
                        "buy", "rent", "property", "foreclos", "afford", "sell"]
            if any(k in title_txt.lower() for k in keywords) or True:
                news.append({
                    "date": date_str,
                    "title": title_txt,
                    "url": link_txt,
                    "desc": desc_txt,
                })

        return news[:6]
    except Exception as e:
        print(f"  Fortune RSS error: {e}")
        return []

# ── 3. MBA APPLICATIONS via HousingWire RSS ───────────────────────────────────
def fetch_mba():
    print("Fetching MBA application data via HousingWire...")
    try:
        r = get("https://www.housingwire.com/feed/")
        soup = BeautifulSoup(r.content, "xml")
        items = soup.find_all("item")

        mba_items = []
        for item in items:
            title = item.find("title")
            if not title:
                continue
            t = title.get_text(strip=True).lower()
            if "mortgage application" in t or "mba" in t:
                link = item.find("link")
                pub  = item.find("pubDate")
                desc = item.find("description") or item.find("content:encoded")

                date_str = ""
                if pub:
                    try:
                        dt = datetime.strptime(pub.get_text(strip=True), "%a, %d %b %Y %H:%M:%S %z")
                        date_str = dt.strftime("%b %d, %Y")
                    except Exception:
                        date_str = pub.get_text(strip=True)[:16]

                desc_txt = ""
                if desc:
                    desc_txt = BeautifulSoup(desc.get_text(strip=True), "html.parser").get_text(strip=True)[:400]

                mba_items.append({
                    "date": date_str,
                    "title": title.get_text(strip=True),
                    "url": link.get_text(strip=True) if link else "",
                    "desc": desc_txt,
                })

        # Parse percentage changes from the most recent item
        data = {"items": mba_items[:3], "weeks": []}
        if mba_items:
            latest_desc = mba_items[0]["desc"]
            # Try to extract WoW % change
            pct_match = re.findall(r'(increased|decreased|rose|fell|up|down)\s+([\d.]+)%', latest_desc, re.I)
            data["latest_headline"] = mba_items[0]["title"]
            data["latest_date"] = mba_items[0]["date"]
            data["changes"] = pct_match

        return data
    except Exception as e:
        print(f"  MBA/HousingWire error: {e}")
        return {"items": [], "weeks": []}

# ── 4. FANNIE MAE FORECAST (semi-static, updated monthly) ────────────────────
def fetch_fannie_forecast():
    """
    Fannie Mae ESR publishes a monthly PDF/page. We parse their news release page
    to get the latest commentary, but keep the quarterly rate table hardcoded
    since it changes monthly and the PDF is hard to parse.
    We'll scrape their forecast page for the latest release date.
    """
    print("Fetching Fannie Mae forecast page...")
    forecast = {
        "q1_2026": "6.00%",
        "q2_2026": "5.90%",
        "q3_2026": "5.80%",
        "q4_2026": "5.70%",
        "fy_2027": "5.60–5.70%",
        "starts_yoy": "−6.2%",
        "home_sales": "~5.5M",
        "last_updated": "March 2026",
        "note": ""
    }
    try:
        r = get("https://www.fanniemae.com/data-and-insights/forecast")
        soup = BeautifulSoup(r.content, "html.parser")
        # Try to find the latest release date/note in the page text
        text = soup.get_text(" ", strip=True)
        # Look for month year pattern near "forecast"
        match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', text)
        if match:
            forecast["last_updated"] = f"{match.group(1)} {match.group(2)}"
    except Exception as e:
        print(f"  Fannie Mae error: {e} — using cached forecast data")
    return forecast

# ── 5. BUILD HTML ─────────────────────────────────────────────────────────────
def build_html(pmms, news, mba, fannie):
    today = datetime.now().strftime("%A, %B %d, %Y")
    now_ts = datetime.now().strftime("%b %d, %Y %I:%M %p UTC")

    # PMMS display values with fallbacks
    if pmms:
        pmms_30     = f"{pmms['rate_30']:.2f}%" if pmms['rate_30'] else "N/A"
        pmms_15     = f"{pmms['rate_15']:.2f}%" if pmms['rate_15'] else "N/A"
        pmms_prev30 = f"{pmms['prev_30']:.2f}%" if pmms['prev_30'] else "N/A"
        pmms_prev15 = f"{pmms['prev_15']:.2f}%" if pmms['prev_15'] else "N/A"
        pmms_date   = pmms['date']
        bps_30      = pmms['bps_30'] or 0
        bps_15      = pmms['bps_15'] or 0
        yoy_bps     = pmms['yoy_bps'] or 0
        yago_30     = f"{pmms['rate_30_yago']:.2f}%" if pmms.get('rate_30_yago') else "N/A"
        bps_30_dir  = "▲" if bps_30 >= 0 else "▼"
        bps_15_dir  = "▲" if bps_15 >= 0 else "▼"
        yoy_dir     = "▲" if yoy_bps >= 0 else "▼"
        yoy_label   = f"{yoy_dir} {abs(yoy_bps):.0f}bps YoY"
        yoy_class   = "up" if yoy_bps >= 0 else "pos"
    else:
        pmms_30 = pmms_15 = "N/A"
        pmms_prev30 = pmms_prev15 = "N/A"
        pmms_date = "N/A"
        bps_30 = bps_15 = yoy_bps = 0
        yoy_label = "N/A"
        yoy_class = "pos"
        yago_30 = "N/A"
        bps_30_dir = bps_15_dir = "▲"

    # News HTML
    def news_html(items):
        if not items:
            return '<div style="padding:1rem;color:var(--muted);font-size:.75rem;">No headlines available.</div>'
        out = ""
        for n in items:
            out += f"""
        <a class="news-item" href="{n['url']}" target="_blank" rel="noopener">
          <div class="ni-date">{n['date']}</div>
          <div class="ni-title">{n['title']}</div>
          <div class="ni-desc">{n['desc']}</div>
        </a>"""
        return out

    # MBA headline
    mba_headline = ""
    mba_date     = ""
    if mba.get("latest_headline"):
        mba_headline = mba["latest_headline"]
        mba_date     = mba.get("latest_date", "")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PropertyPulse — Real Estate Market Tracker</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {{
    --ink:#0d0d0d; --paper:#f4f0e8; --paper2:#ede8da; --accent:#c84b2f;
    --up:#2a6e4e; --down:#c84b2f; --gold:#d4943a; --muted:#7a7163;
    --border:#c8bfa8; --card:#faf7f0;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Syne',sans-serif;background:var(--paper);color:var(--ink);min-height:100vh;font-size:14px}}
  a{{color:inherit;text-decoration:none}}
  header{{background:var(--ink);color:var(--paper);padding:0 1.5rem;border-bottom:3px solid var(--accent)}}
  .hi{{max-width:1200px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:1rem 0}}
  .logo{{font-family:'DM Serif Display',serif;font-size:1.6rem;letter-spacing:-.02em}}.logo span{{color:var(--accent)}}
  .hmeta{{font-family:'DM Mono',monospace;font-size:.62rem;color:#a09880;text-align:right;line-height:1.7}}
  .rbtn{{background:var(--accent);color:white;border:none;padding:.5rem 1.1rem;font-family:'Syne',sans-serif;font-size:.72rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;cursor:pointer}}
  .rbtn:hover{{background:#a83820}}
  .ticker-wrap{{background:var(--accent);overflow:hidden;padding:.4rem 0}}
  .ticker{{display:flex;gap:2.75rem;animation:scroll 45s linear infinite;width:max-content}}
  .ticker-item{{font-family:'DM Mono',monospace;font-size:.65rem;color:white;white-space:nowrap;display:flex;align-items:center;gap:.3rem}}
  .ticker-item .lb{{opacity:.72}}.chup{{color:#a8ffc8}}.chdn{{color:#ffa8a8}}
  @keyframes scroll{{0%{{transform:translateX(0)}}100%{{transform:translateX(-50%)}}}}
  main{{max-width:1200px;margin:0 auto;padding:1.75rem 1.5rem}}
  .slbl{{font-family:'DM Mono',monospace;font-size:.58rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:.65rem;display:flex;align-items:center;gap:.5rem}}
  .slbl::after{{content:'';flex:1;height:1px;background:var(--border)}}
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
  .rate-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:1px;background:var(--border);border:1px solid var(--border);margin-bottom:2rem}}
  @media(min-width:500px){{.rate-grid{{grid-template-columns:repeat(3,1fr)}}}}
  @media(min-width:900px){{.rate-grid{{grid-template-columns:repeat(6,1fr)}}}}
  .rate-card{{background:var(--card);padding:1rem 1.1rem;position:relative;overflow:hidden}}
  .rc-label{{font-family:'DM Mono',monospace;font-size:.54rem;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin-bottom:.3rem}}
  .rc-value{{font-family:'DM Serif Display',serif;font-size:1.75rem;line-height:1;margin-bottom:.2rem}}
  .rc-chg{{font-family:'DM Mono',monospace;font-size:.6rem}}
  .rc-chg.up{{color:var(--down)}}.rc-chg.dn{{color:var(--up)}}
  .rc-prev{{font-family:'DM Mono',monospace;font-size:.54rem;color:var(--muted);margin-top:.15rem}}
  .rc-bar{{position:absolute;bottom:0;left:0;height:3px;background:var(--accent)}}
  .panel{{background:var(--card);border:1px solid var(--border)}}
  .ph{{padding:.85rem 1.1rem;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;background:var(--ink);color:var(--paper)}}
  .ph h3{{font-family:'DM Serif Display',serif;font-size:.95rem;font-weight:400}}
  .badge{{font-family:'DM Mono',monospace;font-size:.54rem;padding:.12rem .45rem;text-transform:uppercase;letter-spacing:.06em;color:white}}
  .badge-red{{background:var(--accent)}}.badge-green{{background:var(--up)}}.badge-gold{{background:var(--gold);color:var(--ink)}}
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
  .bar-tag{{font-family:'DM Mono',monospace;font-size:.54rem;width:68px;flex-shrink:0}}
  .divider{{height:1px;background:var(--border);margin:.85rem 0}}
  .news-item{{padding:.8rem 1.1rem;border-bottom:1px solid var(--border);display:block;color:var(--ink);transition:background .15s}}
  .news-item:hover{{background:var(--paper2)}}.news-item:last-child{{border-bottom:none}}
  .ni-date{{font-family:'DM Mono',monospace;font-size:.54rem;color:var(--muted);margin-bottom:.2rem;text-transform:uppercase}}
  .ni-title{{font-size:.78rem;font-weight:600;line-height:1.35;margin-bottom:.2rem}}
  .ni-desc{{font-size:.67rem;color:var(--muted);line-height:1.45}}
  .ftable td,.ftable th{{padding:.6rem 1rem}}
  .fc{{font-family:'DM Mono',monospace;font-size:.7rem}}
  .fc-good{{color:var(--up)}}.fc-warn{{color:var(--gold)}}.fc-neu{{color:var(--muted)}}
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
  <div class="hi">
    <div class="logo">Property<span>Pulse</span></div>
    <div class="hmeta">
      <div>{today}</div>
      <div>Fortune · Freddie Mac PMMS · Fannie Mae ESR · HousingWire / MBA</div>
    </div>
    <div style="font-family:'DM Mono',monospace;font-size:.6rem;color:#a09880;text-align:right;">Auto-updated daily<br>Last run: {now_ts}</div>
  </div>
</header>

<!-- TICKER -->
<div class="ticker-wrap"><div class="ticker">
  <div class="ticker-item"><span class="lb">PMMS 30Y</span><span>{pmms_30}</span><span class="{"chup" if bps_30 >= 0 else "chdn"}">{bps_30_dir}{"+" if bps_30 >= 0 else ""}{bps_30:.0f}bps WoW</span></div>
  <div class="ticker-item"><span class="lb">PMMS 15Y</span><span>{pmms_15}</span><span class="{"chup" if bps_15 >= 0 else "chdn"}">{bps_15_dir}{"+" if bps_15 >= 0 else ""}{bps_15:.0f}bps WoW</span></div>
  <div class="ticker-item"><span class="lb">PMMS DATE</span><span>{pmms_date}</span></div>
  <div class="ticker-item"><span class="lb">FED RATE</span><span>3.50–3.75%</span><span style="color:#ffd88a">HOLD</span></div>
  <div class="ticker-item"><span class="lb">FM Q2 FCST</span><span>{fannie['q2_2026']}</span><span class="chdn">▼ Projected</span></div>
  <div class="ticker-item"><span class="lb">1YR AGO 30Y</span><span>{yago_30}</span><span class="chdn">▼ {abs(yoy_bps):.0f}bps YoY</span></div>
  <!-- duplicate -->
  <div class="ticker-item"><span class="lb">PMMS 30Y</span><span>{pmms_30}</span><span class="{"chup" if bps_30 >= 0 else "chdn"}">{bps_30_dir}{"+" if bps_30 >= 0 else ""}{bps_30:.0f}bps WoW</span></div>
  <div class="ticker-item"><span class="lb">PMMS 15Y</span><span>{pmms_15}</span><span class="{"chup" if bps_15 >= 0 else "chdn"}">{bps_15_dir}{"+" if bps_15 >= 0 else ""}{bps_15:.0f}bps WoW</span></div>
  <div class="ticker-item"><span class="lb">PMMS DATE</span><span>{pmms_date}</span></div>
  <div class="ticker-item"><span class="lb">FED RATE</span><span>3.50–3.75%</span><span style="color:#ffd88a">HOLD</span></div>
  <div class="ticker-item"><span class="lb">FM Q2 FCST</span><span>{fannie['q2_2026']}</span><span class="chdn">▼ Projected</span></div>
  <div class="ticker-item"><span class="lb">1YR AGO 30Y</span><span>{yago_30}</span><span class="chdn">▼ {abs(yoy_bps):.0f}bps YoY</span></div>
</div></div>

<main>

  <!-- FED BANNER -->
  <div class="fed-note">
    <div class="fed-icon">🏦</div>
    <div>
      <h4>Federal Reserve — Last FOMC Decision</h4>
      <p>Rate held at <strong>3.50–3.75%</strong>. Next meeting: <strong>April 28–29, 2026</strong>. PMMS 30Y at <strong>{pmms_30}</strong> as of {pmms_date} — <strong>{abs(yoy_bps):.0f}bps</strong> {"above" if yoy_bps >= 0 else "below"} a year ago.</p>
    </div>
  </div>

  <!-- STAT TILES -->
  <div class="slbl">Key Market Indicators · {today}</div>
  <div class="stat-tiles">
    <div class="stat-tile">
      <div class="st-label">PMMS 30Y FRM</div>
      <div class="st-val">{pmms_30}</div>
      <div class="st-sub">Freddie Mac · {pmms_date}</div>
      <div class="st-chg up">{bps_30_dir} from {pmms_prev30} prev week</div>
    </div>
    <div class="stat-tile">
      <div class="st-label">PMMS 15Y FRM</div>
      <div class="st-val">{pmms_15}</div>
      <div class="st-sub">Freddie Mac · {pmms_date}</div>
      <div class="st-chg up">{bps_15_dir} from {pmms_prev15} prev week</div>
    </div>
    <div class="stat-tile">
      <div class="st-label">Year-Over-Year</div>
      <div class="st-val">{abs(yoy_bps):.0f}bps</div>
      <div class="st-sub">30Y was {yago_30} a year ago</div>
      <div class="st-chg {yoy_class}">{"▲ Higher" if yoy_bps >= 0 else "▼ More affordable"} YoY</div>
    </div>
    <div class="stat-tile">
      <div class="st-label">Latest MBA News</div>
      <div class="st-val" style="font-size:1rem;line-height:1.3;">{mba_headline[:60] + "..." if len(mba_headline) > 60 else mba_headline}</div>
      <div class="st-sub">{mba_date}</div>
    </div>
  </div>

  <!-- FREDDIE MAC PMMS -->
  <div class="slbl">Freddie Mac Primary Mortgage Market Survey (PMMS) · freddiemac.com/pmms</div>
  <div class="panel" style="margin-bottom:2rem;">
    <div class="ph"><h3>PMMS Weekly Survey — Latest Rates</h3><span class="badge badge-green">Freddie Mac PMMS</span></div>
    <div class="pmms-strip">
      <div class="pmms-cell">
        <div class="pmms-lbl">30Y FRM ({pmms_date})</div>
        <div class="pmms-val">{pmms_30}</div>
        <div class="pmms-sub">Latest weekly avg · 20% down · excellent credit</div>
      </div>
      <div class="pmms-cell">
        <div class="pmms-lbl">15Y FRM ({pmms_date})</div>
        <div class="pmms-val">{pmms_15}</div>
        <div class="pmms-sub">Weekly avg</div>
      </div>
      <div class="pmms-cell">
        <div class="pmms-lbl">30Y Prev Week</div>
        <div class="pmms-val">{pmms_prev30}</div>
        <div class="pmms-sub">Prior PMMS reading</div>
      </div>
      <div class="pmms-cell">
        <div class="pmms-lbl">30Y 1 Year Ago</div>
        <div class="pmms-val">{yago_30}</div>
        <div class="pmms-sub">Same week last year</div>
      </div>
      <div class="pmms-cell">
        <div class="pmms-lbl">WoW Change 30Y</div>
        <div class="pmms-val" style="color:{"var(--down)" if bps_30 >= 0 else "var(--up)"};">{bps_30_dir}{abs(bps_30):.0f}bps</div>
        <div class="pmms-sub">Basis points week-over-week</div>
      </div>
    </div>
    <div style="padding:.85rem 1.1rem;">
      <p style="font-size:.65rem;line-height:1.6;color:var(--muted);">PMMS measures weekly survey averages from loan applications (20% down, excellent credit, conforming). Released every Thursday at 12pm ET. Data sourced directly from Freddie Mac's public Excel archive at freddiemac.com/pmms.</p>
    </div>
    <div class="sb"><div class="sd"></div><span>Source: Freddie Mac PMMS Excel archive · freddiemac.com/pmms · Auto-updated on publish</span></div>
  </div>

  <!-- MBA APPLICATIONS + NEWS -->
  <div class="two-col">
    <div>
      <div class="slbl">MBA Application Activity · HousingWire / MBA</div>
      <div class="panel">
        <div class="ph"><h3>Mortgage Purchase Applications</h3><span class="badge badge-red">MBA via HousingWire</span></div>
        <div class="mba-section">
          {"<div style='font-size:.75rem;line-height:1.7;color:var(--muted);margin-bottom:1rem;'><strong style='color:var(--ink);'>Latest:</strong> " + mba_headline + " (" + mba_date + ")</div>" if mba_headline else ""}
          <div style="font-size:.72rem;line-height:1.7;color:var(--muted);">
            The MBA Weekly Mortgage Applications Survey tracks total application volume including purchase and refinance activity. Purchase applications are a leading indicator of future home sales — typically 30–45 days ahead of closings. Data is published weekly by the Mortgage Bankers Association and reported by HousingWire.
          </div>
          {"".join(f'<div class="divider"></div><a href="{i["url"]}" target="_blank" rel="noopener" style="display:block;padding:.5rem 0;border-bottom:1px solid var(--border);"><div style=\'font-family:DM Mono,monospace;font-size:.54rem;color:var(--muted);margin-bottom:.2rem;\'>{i["date"]}</div><div style=\'font-size:.75rem;font-weight:600;\'>{i["title"]}</div></a>' for i in mba.get("items", [])[:3])}
        </div>
        <div class="sb"><div class="sd"></div><span>Source: MBA Weekly Applications Survey via HousingWire · housingwire.com/mortgage-purchase-applications-index</span></div>
      </div>
    </div>

    <div>
      <div class="slbl">Latest Headlines · fortune.com/section/real-estate</div>
      <div class="panel">
        <div class="ph"><h3>Market News</h3><span class="badge badge-red">Fortune</span></div>
        {news_html(news)}
        <div class="sb"><div class="sd"></div><span>Source: fortune.com/feed/section/real-estate/ · Auto-refreshed daily</span></div>
      </div>
    </div>
  </div>

  <!-- FANNIE MAE FORECAST TABLE -->
  <div class="slbl">Fannie Mae ESR Group — {fannie['last_updated']} Housing Forecast · fanniemae.com/data-and-insights/forecast</div>
  <div class="tbl-wrap">
    <div class="ph"><h3>30-Year Fixed Rate Forecast — Fannie Mae {fannie['last_updated']}</h3><span class="badge badge-gold">Fannie Mae ESR</span></div>
    <table class="ftable">
      <thead><tr><th>Period</th><th>Fannie Mae Forecast</th><th>vs Prior Month</th><th>Signal</th></tr></thead>
      <tbody>
        <tr><td class="td-type">Q1 2026</td><td class="fc">{fannie['q1_2026']}</td><td class="fc" style="color:var(--gold);">↓ was 6.10%</td><td><span class="fc-tag fc-tag-neutral">Near floor</span></td></tr>
        <tr><td class="td-type">Q2 2026</td><td class="fc fc-good">{fannie['q2_2026']}</td><td class="fc fc-good">↓ more bullish</td><td><span class="fc-tag fc-tag-green">Sub-6% approaching</span></td></tr>
        <tr><td class="td-type">Q3 2026</td><td class="fc fc-good">{fannie['q3_2026']}</td><td class="fc fc-good">↓ more bullish</td><td><span class="fc-tag fc-tag-green">Gradual easing</span></td></tr>
        <tr><td class="td-type">Q4 2026</td><td class="fc fc-good">{fannie['q4_2026']}</td><td class="fc fc-good">↓ more bullish</td><td><span class="fc-tag fc-tag-green">Lowest since 2022</span></td></tr>
        <tr><td class="td-type">Full Year 2027</td><td class="fc fc-good">{fannie['fy_2027']}</td><td class="fc fc-good">↓ improved</td><td><span class="fc-tag fc-tag-green">Continued easing</span></td></tr>
      </tbody>
    </table>
    <div style="padding:.85rem 1.1rem;"><p style="font-size:.72rem;line-height:1.7;color:var(--muted);">Fannie Mae ESR Group publishes updated forecasts monthly. The rate outlook reflects expected Fed policy, Treasury yield movements, and macroeconomic conditions. Note: fewer single-family starts ({fannie['starts_yoy']} YoY) limit inventory despite lower rates.</p></div>
    <div class="sb"><div class="sd"></div><span>Source: Fannie Mae ESR Group · {fannie['last_updated']} Housing Forecast · fanniemae.com/data-and-insights/forecast</span></div>
  </div>

  <!-- FANNIE OUTLOOK CARDS -->
  <div class="slbl">Fannie Mae Housing Market Outlook · {fannie['last_updated']}</div>
  <div class="three-col">
    <div class="outlook-card">
      <div class="ph"><h3>Construction Outlook</h3><span class="badge badge-gold">Fannie Mae</span></div>
      <div class="oc-body">
        <div class="oc-val">{fannie['starts_yoy']}</div>
        <div class="oc-sub">Single-family starts YoY 2026</div>
        <div class="oc-text">Starts revised down vs prior forecast for Q1–Q3. Q4 2026 and all of 2027 revised <strong>higher</strong> — 2027 now projected +5.1% YoY. Total annual starts near <strong>1.3M</strong>. High rates, lot constraints, and economic uncertainty remain top concerns for builders.</div>
      </div>
      <div class="sb"><div class="sd"></div><span>Fannie Mae {fannie['last_updated']} Housing Forecast</span></div>
    </div>
    <div class="outlook-card">
      <div class="ph"><h3>Home Sales Outlook</h3><span class="badge badge-gold">Fannie Mae</span></div>
      <div class="oc-body">
        <div class="oc-val">{fannie['home_sales']}</div>
        <div class="oc-sub">Total home sales projected 2026</div>
        <div class="oc-text">Meaningful rise expected vs 2025. Both new and existing segments contributing. Rates ~45bps below year-ago levels support buyer engagement. Spring season showing improving purchase applications and pending home sales vs last year.</div>
      </div>
      <div class="sb"><div class="sd"></div><span>Fannie Mae ESR · {fannie['last_updated']} Forecast</span></div>
    </div>
    <div class="outlook-card">
      <div class="ph"><h3>Risk Factors</h3><span class="badge badge-gold">Fannie Mae ESR</span></div>
      <div class="oc-body" style="padding-top:.9rem;">
        <div class="risk-item"><span class="risk-up">↑ Risk:</span> Slower GDP growth → rates could fall faster but signals weaker demand</div>
        <div class="risk-item"><span class="risk-up">↑ Risk:</span> Limited inventory despite lower rates → prices stay elevated</div>
        <div class="risk-item"><span class="risk-up">↑ Risk:</span> Geopolitical events pushing oil + Treasury yields higher near-term</div>
        <div class="risk-item"><span class="risk-dn">↓ Positive:</span> Rates well below year-ago — spring buyers in better position than 2025</div>
      </div>
      <div class="sb"><div class="sd"></div><span>Fannie Mae ESR Group · {fannie['last_updated']}</span></div>
    </div>
  </div>

</main>

<footer>
  <strong>PropertyPulse</strong> — Real Estate Market Tracker &nbsp;|&nbsp;
  Auto-updated daily via GitHub Actions &nbsp;|&nbsp;
  Sources: Fortune.com RSS &nbsp;·&nbsp; Freddie Mac PMMS Excel Archive (freddiemac.com/pmms) &nbsp;·&nbsp;
  Fannie Mae ESR Group (fanniemae.com/data-and-insights/forecast) &nbsp;·&nbsp;
  MBA Weekly Applications Survey via HousingWire &nbsp;|&nbsp;
  Not financial advice. &nbsp;|&nbsp; Last updated: {now_ts}
</footer>

</body>
</html>"""
    return html


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    pmms   = fetch_pmms()
    news   = fetch_fortune_news()
    mba    = fetch_mba()
    fannie = fetch_fannie_forecast()

    html = build_html(pmms, news, mba, fannie)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Done — index.html written ({len(html):,} chars)")
    print(f"  PMMS 30Y: {pmms['rate_30'] if pmms else 'N/A'}")
    print(f"  News items: {len(news)}")
    print(f"  MBA items: {len(mba.get('items', []))}")
