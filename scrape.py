#!/usr/bin/env python3
"""
PropertyPulse / Newzip Market Tracker — scraper
Sources: FRED API, Fannie Mae APIs, Inman RSS, Fortune RSS, HousingWire/MBA RSS
"""
import os, re, json, datetime, urllib.request, urllib.parse

TODAY     = datetime.date.today()
TODAY_STR = TODAY.strftime("%B %d, %Y")
RUN_TS    = datetime.datetime.utcnow().strftime("%b %d, %Y %I:%M %p UTC")

FRED_KEY             = os.environ.get("FRED_API_KEY", "")
FANNIE_CLIENT_ID     = os.environ.get("FANNIE_CLIENT_ID", "")
FANNIE_CLIENT_SECRET = os.environ.get("FANNIE_CLIENT_SECRET", "")
FANNIE_BASE          = "https://api.fanniemae.com"

LOGO_SRC = "SVG_PLACEHOLDER" # replaced below
_LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 52" height="28">
  <g fill="#4C6DE1">
    <path d="M18.5 8C13.2 8 9 12.2 9 17.5v17C9 39.8 13.2 44 18.5 44S28 39.8 28 34.5v-4.2l-5.8 5.8c-.6.6-1.4.9-2.2.9s-1.6-.3-2.2-.9c-1.2-1.2-1.2-3.2 0-4.4l5.8-5.8H18.5c-1.7 0-3-1.3-3-3s1.3-3 3-3H28v-2.4C28 12.2 23.8 8 18.5 8z"/>
    <path d="M38.5 8C33.2 8 29 12.2 29 17.5v2.4h9.5c1.7 0 3 1.3 3 3s-1.3 3-3 3H29v4.2l5.8-5.8c1.2-1.2 3.2-1.2 4.4 0s1.2 3.2 0 4.4L33.4 35H38.5c5.3 0 9.5-4.2 9.5-9.5v-8C48 12.2 43.8 8 38.5 8z"/>
    <text x="58" y="36" font-family="Inter,Arial,sans-serif" font-size="26" font-weight="700" letter-spacing="-0.5">newzip</text>
  </g>
</svg>"""
# will be embedded as data URI
import base64 as _b64
LOGO_SRC = "data:image/svg+xml;base64," + _b64.b64encode(_LOGO_SVG.encode()).decode()

# ── HELPERS ───────────────────────────────────────────────────────────────────

def fetch(url, timeout=20, headers=None):
    h = {"User-Agent": "NewzipMarketTracker/1.0"}
    if headers: h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  WARN fetch {url}: {e}")
        return ""

def post(url, data, headers=None, timeout=20):
    h = {"Content-Type": "application/x-www-form-urlencoded"}
    if headers: h.update(headers)
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  WARN post {url}: {e}")
        return ""

# ── FANNIE MAE OAUTH ──────────────────────────────────────────────────────────

_fannie_token = None
_fannie_token_expiry = None

def get_fannie_token():
    global _fannie_token, _fannie_token_expiry
    if _fannie_token and _fannie_token_expiry and datetime.datetime.utcnow() < _fannie_token_expiry:
        return _fannie_token
    if not FANNIE_CLIENT_ID or not FANNIE_CLIENT_SECRET:
        return None
    print("  Getting Fannie Mae OAuth token...")
    raw = post("https://api.fanniemae.com/v1/oauth2/token", {
        "grant_type": "client_credentials",
        "client_id": FANNIE_CLIENT_ID,
        "client_secret": FANNIE_CLIENT_SECRET,
    })
    if not raw: return None
    try:
        data = json.loads(raw)
        _fannie_token = data.get("access_token")
        exp = int(data.get("expires_in", 3600))
        _fannie_token_expiry = datetime.datetime.utcnow() + datetime.timedelta(seconds=exp-60)
        print(f"  Token OK, expires {exp}s")
        return _fannie_token
    except Exception as e:
        print(f"  WARN token: {e}")
        return None

def fannie_get(path):
    token = get_fannie_token()
    if not token: return None
    raw = fetch(FANNIE_BASE + path, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    if not raw: return None
    try:
        return json.loads(raw)
    except Exception as e:
        print(f"  WARN FM JSON {path}: {e}")
        return None

# ── FRED ──────────────────────────────────────────────────────────────────────

def fred(series_id, limit=5):
    if not FRED_KEY: return []
    params = urllib.parse.urlencode({
        "series_id": series_id, "api_key": FRED_KEY, "file_type": "json",
        "sort_order": "desc", "limit": limit, "observation_start": "2020-01-01",
    })
    raw = fetch(f"https://api.stlouisfed.org/fred/series/observations?{params}")
    if not raw: return []
    try:
        return [o for o in json.loads(raw).get("observations",[]) if o.get("value") not in (".",)]
    except: return []

def fred_two(series_id):
    obs = fred(series_id, limit=10)
    valid = []
    for o in obs:
        try:
            v = float(o["value"])
            if v > 0: valid.append((v, o["date"]))
        except: pass
    if len(valid) >= 2: return valid[0][0], valid[1][0], valid[0][1]
    elif len(valid) == 1: return valid[0][0], valid[0][0], valid[0][1]
    return None, None, None

# ── OBMMI ─────────────────────────────────────────────────────────────────────

OBMMI_SERIES = [
    ("30-Year Conventional","30Y CONV","OBMMIC30YF"),
    ("15-Year Conventional","15Y CONV","OBMMIC15YF"),
    ("30-Year Jumbo","30Y JUMBO","OBMMIJUMBO30YF"),
    ("30-Year FHA","30Y FHA","OBMMIFHA30YF"),
    ("30-Year VA","30Y VA","OBMMIVA30YF"),
    ("30-Year USDA","30Y USDA","OBMMIUSDA30YF"),
]
OBMMI_FB = {
    "OBMMIC30YF":(6.356,6.214),"OBMMIC15YF":(5.707,5.507),
    "OBMMIJUMBO30YF":(6.597,6.454),"OBMMIFHA30YF":(6.164,6.014),
    "OBMMIVA30YF":(5.999,5.830),"OBMMIUSDA30YF":(6.033,5.968),
}

def fetch_obmmi():
    print("Fetching OBMMI from FRED...")
    rates = []
    for type_name, lb, series in OBMMI_SERIES:
        cur, prev, date = fred_two(series)
        if cur is None:
            cur, prev = OBMMI_FB.get(series,(6.00,6.00)); date="N/A"
        bps = round((cur-prev)*100,1)
        rates.append({"type":type_name,"lb":lb,"rate":round(cur,3),"prev":round(prev,3),
                       "bps":int(round(bps)),"dod":f"{''if bps>=0 else ''}{bps:+.0f}bps","date":date})
        print(f"  {lb}: {cur:.3f}% ({bps:+.0f}bps)")
    return rates

# ── PMMS ──────────────────────────────────────────────────────────────────────

def fetch_pmms():
    print("Fetching PMMS from FRED...")
    r30,p30,d30 = fred_two("MORTGAGE30US")
    r15,p15,_   = fred_two("MORTGAGE15US")
    obs_yago = fred("MORTGAGE30US", limit=60)
    r30_yago = None
    if len(obs_yago) >= 52:
        try: r30_yago = float(obs_yago[51]["value"])
        except: pass
    if r30 is None:
        return {"rate_30y":6.22,"rate_15y":5.54,"prev_30y":6.11,"prev_15y":5.50,"date":"N/A","yago_30y":6.67}
    try:
        dt = datetime.datetime.strptime(d30,"%Y-%m-%d")
        date_str = dt.strftime("%b %d, %Y")
    except: date_str = d30
    print(f"  PMMS 30Y:{r30:.2f}% 15Y:{r15:.2f}% ({date_str})")
    return {"rate_30y":round(r30,2),"rate_15y":round(r15,2) if r15 else None,
            "prev_30y":round(p30,2) if p30 else None,"prev_15y":round(p15,2) if p15 else None,
            "date":date_str,"yago_30y":round(r30_yago,2) if r30_yago else None}

# ── FANNIE HOUSING ────────────────────────────────────────────────────────────

def fetch_fannie_housing():
    print("Fetching Fannie Mae Housing Indicators...")
    year = TODAY.year
    result = {"mortgage_rate_30y":{},"total_home_sales":None,"sf_starts":None,"report_date":None}

    data = fannie_get("/v1/housing-indicators/indicators/30-year-fixed-rate-mortgage")
    if data and "indicators" in data:
        inds = sorted(data["indicators"],key=lambda x:x.get("effectiveDate",""),reverse=True)
        if inds:
            result["report_date"] = inds[0].get("effectiveDate","")[:10]
            pts = inds[0].get("points") or inds[0].get("timeSeries") or []
            for p in pts:
                if p.get("forecast") and p.get("year") in (year, year+1):
                    key = f"{p.get('quarter','')} {p.get('year','')}"
                    result["mortgage_rate_30y"][key] = round(float(p.get("value",0)),2)

    data = fannie_get("/v1/housing-indicators/indicators/total-home-sales")
    if data and "indicators" in data:
        inds = sorted(data["indicators"],key=lambda x:x.get("effectiveDate",""),reverse=True)
        if inds:
            pts = inds[0].get("points") or inds[0].get("timeSeries") or []
            for p in pts:
                if p.get("forecast") and p.get("year")==year and p.get("quarter")=="EOY":
                    result["total_home_sales"] = round(float(p.get("value",0))/1000,2); break

    data = fannie_get("/v1/housing-indicators/indicators/single-family-1-unit-housing-starts")
    if data and "indicators" in data:
        inds = sorted(data["indicators"],key=lambda x:x.get("effectiveDate",""),reverse=True)
        if len(inds) >= 2:
            cur_pts  = {p.get("quarter"):p.get("value") for p in (inds[0].get("points") or []) if p.get("year")==year}
            prev_pts = {p.get("quarter"):p.get("value") for p in (inds[1].get("points") or []) if p.get("year")==year-1}
            if cur_pts.get("EOY") and prev_pts.get("EOY"):
                pct = (float(cur_pts["EOY"])-float(prev_pts["EOY"]))/float(prev_pts["EOY"])*100
                result["sf_starts"] = round(pct,1)

    print(f"  FM rates:{result['mortgage_rate_30y']} sales:{result['total_home_sales']} starts:{result['sf_starts']}")
    return result

# ── FANNIE ECONOMIC ───────────────────────────────────────────────────────────

def fetch_fannie_economic():
    print("Fetching Fannie Mae Economic Indicators...")
    result = {"fed_funds":None,"treasury_10y":None,"unemployment":None,"cpi":None,"gdp":None,"report_date":None}
    year = TODAY.year
    for indicator,key in [
        ("federal-funds-rate","fed_funds"),("10-year-treasury-note-yield","treasury_10y"),
        ("unemployment-rate","unemployment"),("consumer-price-index","cpi"),("gross-domestic-product","gdp"),
    ]:
        data = fannie_get(f"/v1/economic-forecasts/indicators/{indicator}")
        if not data or "indicators" not in data: continue
        inds = sorted(data["indicators"],key=lambda x:x.get("effectiveDate",""),reverse=True)
        if not inds: continue
        if not result["report_date"]: result["report_date"] = inds[0].get("effectiveDate","")[:10]
        pts = inds[0].get("points") or inds[0].get("timeSeries") or []
        for p in pts:
            if p.get("year")==year and p.get("forecast") and p.get("quarter") in ("EOY","Q4"):
                result[key] = round(float(p.get("value",0)),2); break
        print(f"  {indicator}: {result[key]}")
    return result

# ── FANNIE HPSI ───────────────────────────────────────────────────────────────

def fetch_fannie_hpsi():
    print("Fetching Fannie Mae HPSI...")
    data = fannie_get("/v1/nhs/hpsi")
    if not data or not isinstance(data,list): return None
    try:
        latest = sorted(data,key=lambda x:x.get("date",""),reverse=True)[0]
        val = round(float(latest.get("hpsiValue",0)),1)
        date = latest.get("date","")[:10]
        try: date = datetime.datetime.strptime(date,"%Y-%m-%d").strftime("%b %Y")
        except: pass
        print(f"  HPSI:{val} ({date})")
        return {"value":val,"date":date}
    except Exception as e:
        print(f"  WARN HPSI:{e}"); return None

# ── INMAN RSS ─────────────────────────────────────────────────────────────────

def fetch_inman_news():
    print("Fetching Inman News RSS...")
    raw = fetch("https://feeds.feedburner.com/inmannews")
    articles = []
    seen = set()

    # CDATA title pattern
    for m in re.finditer(
        r'<item>.*?<title><!\[CDATA\[(.*?)\]\]></title>.*?<link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>.*?<description><!\[CDATA\[(.*?)\]\]></description>',
        raw, re.DOTALL
    ):
        title = m.group(1).strip()
        url   = m.group(2).strip()
        pub   = m.group(3).strip()
        desc  = re.sub(r'<[^>]+>','',m.group(4).strip())[:160]
        if url in seen or len(title) < 10: continue
        seen.add(url)
        try:
            dt = datetime.datetime.strptime(pub[:25], "%a, %d %b %Y %H:%M")
            date_str = dt.strftime("%b %d, %Y")
        except: date_str = pub[:16]
        articles.append({"title":title,"url":url,"date":date_str,"desc":desc})
        if len(articles) >= 6: break

    # Fallback: plain title tags
    if not articles:
        for m in re.finditer(r'<title>(.*?)</title>.*?<link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>', raw, re.DOTALL):
            title = re.sub(r'<[^>]+>','',m.group(1)).strip()
            url   = m.group(2).strip()
            pub   = m.group(3).strip()
            if url in seen or 'inman.com' not in url or len(title)<10: continue
            seen.add(url)
            try:
                dt = datetime.datetime.strptime(pub[:25],"%a, %d %b %Y %H:%M")
                date_str = dt.strftime("%b %d, %Y")
            except: date_str = pub[:16]
            articles.append({"title":title,"url":url,"date":date_str,"desc":""})
            if len(articles) >= 6: break

    print(f"  Inman: {len(articles)} articles")
    return articles

# ── FORTUNE RSS ───────────────────────────────────────────────────────────────

def fetch_fortune_news():
    print("Fetching Fortune Real Estate RSS...")
    raw = fetch("https://fortune.com/feed/section/real-estate/")
    articles = []
    seen = set()
    for m in re.finditer(
        r'<item>.*?<title><!\[CDATA\[(.*?)\]\]></title>.*?<link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>',
        raw, re.DOTALL
    ):
        title,url,pub = m.group(1).strip(),m.group(2).strip(),m.group(3).strip()
        if url in seen or len(title)<15: continue
        seen.add(url)
        try:
            dt = datetime.datetime.strptime(pub[:25],"%a, %d %b %Y %H:%M")
            date_str = dt.strftime("%b %d, %Y")
        except: date_str = pub[:16]
        articles.append({"title":title,"url":url,"date":date_str,"desc":""})
        if len(articles) >= 6: break
    if not articles:
        html = fetch("https://fortune.com/section/real-estate/")
        for m in re.finditer(r'href="(https://fortune\.com/(?:article/)?20\d\d/\d\d/\d\d/[^"]+?)"[^>]*?>([^<]{20,200})</a>',html,re.IGNORECASE):
            url,title = m.group(1),re.sub(r'\s+',' ',m.group(2).strip())
            if url not in seen and len(title)>20 and '<' not in title:
                seen.add(url)
                dm = re.search(r'/(\d{4})/(\d{2})/(\d{2})/',url)
                date_str = ""
                if dm:
                    try: date_str = datetime.date(int(dm.group(1)),int(dm.group(2)),int(dm.group(3))).strftime("%b %d, %Y")
                    except: pass
                articles.append({"title":title,"url":url,"date":date_str,"desc":""})
            if len(articles) >= 6: break
    print(f"  Fortune: {len(articles)} articles")
    return articles

# ── MBA / HOUSINGWIRE ─────────────────────────────────────────────────────────

def fetch_mba():
    print("Fetching MBA via HousingWire RSS...")
    rss = fetch("https://www.housingwire.com/feed/")
    weeks,items = [],[]
    for m in re.finditer(
        r'<item>.*?<title><!\[CDATA\[(.*?)\]\]></title>.*?<link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>',
        rss, re.DOTALL|re.IGNORECASE
    ):
        title,url,pub = m.group(1).strip(),m.group(2).strip(),m.group(3).strip()
        if "application" not in title.lower() and "mba" not in title.lower(): continue
        try:
            dt = datetime.datetime.strptime(pub[:25],"%a, %d %b %Y %H:%M")
            date_str = dt.strftime("%b %d, %Y")
        except: date_str = pub[:16]
        pct = re.search(r'(increased|decreased|rose|fell|up|down)\s+([\d.]+)%',title,re.I)
        val = None
        if pct:
            val = float(pct.group(2))
            if pct.group(1).lower() in ("decreased","fell","down"): val=-val
        items.append({"title":title,"url":url,"date":date_str})
        if val is not None: weeks.append({"title":title,"url":url,"date":date_str,"val":val})
    print(f"  MBA: {len(weeks)} weeks, {len(items)} items")
    return {"weeks":weeks[:3],"items":items[:3]}

# ── HTML BUILDERS ─────────────────────────────────────────────────────────────

def build_news_items(articles, show_desc=False):
    if not articles:
        return '<div style="padding:1rem;color:var(--muted);font-size:.75rem;">No articles available.</div>'
    out = ""
    for a in articles:
        desc_html = f'\n      <div class="ni-desc">{a["desc"]}</div>' if show_desc and a.get("desc") else ""
        out += (
            f'\n    <a class="news-item" href="{a["url"]}" target="_blank" rel="noopener">'
            f'\n      <div class="ni-date">{a["date"]}</div>'
            f'\n      <div class="ni-title">{a["title"]}</div>'
            f'{desc_html}'
            f'\n    </a>'
        )
    return out

def build_mba_html(mba):
    weeks = mba.get("weeks",[])
    items = mba.get("items",[])
    if weeks:
        bars = ""
        for w in weeks:
            val = w["val"]
            pct = min(95,abs(val)/12*100)
            col = "var(--nz-teal)" if val >= 0 else "var(--nz-red)"
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
                f'\n<a href="{item["url"]}" target="_blank" rel="noopener" class="mba-link">'
                f'<div class="ni-date">{item["date"]}</div>'
                f'<div style="font-size:.75rem;font-weight:600;">{item["title"]}</div></a>'
            )
        return out
    return '<div style="padding:.5rem 0;color:var(--muted);font-size:.75rem;">MBA data temporarily unavailable.</div>'

def build_fannie_rows(housing):
    year = TODAY.year
    rates = housing.get("mortgage_rate_30y",{})
    quarters = [
        (f"Q1 {year}", f"Q1 {year}"),
        (f"Q2 {year}", f"Q2 {year}"),
        (f"Q3 {year}", f"Q3 {year}"),
        (f"Q4 {year}", f"Q4 {year}"),
        (f"EOY {year+1}", f"Full Year {year+1}"),
    ]
    rows = ""
    for key,label in quarters:
        val = rates.get(key)
        if val:
            cls = "fc-good" if val < 6.0 else ""
            tag = "fc-tag-teal" if val < 6.0 else "fc-tag-neutral"
            sig = "Sub-6%" if val < 6.0 else "Above 6%"
            rows += (f'\n<tr><td class="td-type">{label}</td><td class="fc {cls}">{val:.2f}%</td>'
                     f'<td class="fc fc-neu">Live · Fannie Mae API</td>'
                     f'<td><span class="fc-tag {tag}">{sig}</span></td></tr>')
        else:
            rows += (f'\n<tr><td class="td-type">{label}</td><td class="fc fc-neu">—</td>'
                     f'<td class="fc fc-neu">—</td><td><span class="fc-tag fc-tag-neutral">Pending</span></td></tr>')
    return rows

def build_ticker(rates, pmms, hpsi):
    r30   = pmms.get("rate_30y") or 0
    r15   = pmms.get("rate_15y") or 0
    pdate = pmms.get("date","")
    yago  = pmms.get("yago_30y") or 0
    yoy   = round((r30-yago)*100) if yago else 0
    p30   = pmms.get("prev_30y") or r30
    bps30 = round((r30-p30)*100,1)

    items = [
        ("PMMS 30Y", f"{r30:.2f}%", "chup" if bps30<=0 else "chdn", f"{'▲' if bps30>0 else '▼'} {pdate}"),
        ("PMMS 15Y", f"{r15:.2f}%", "chup", "Weekly avg"),
        ("FED RATE",  "3.50–3.75%", "", "HOLD"),
    ]
    if hpsi: items.append(("HPSI", f"{hpsi['value']}", "chup", f"Sentiment · {hpsi['date']}"))
    items.append(("1YR AGO", f"{yago:.2f}%", "chdn", f"{'▼' if yoy<=0 else '▲'} {abs(yoy):.0f}bps YoY"))
    for r in rates:
        d = "chup" if r["bps"]>=0 else "chdn"
        a = "▲" if r["bps"]>=0 else "▼"
        items.append((f"OB {r['lb']}", f"{r['rate']:.3f}%", d, f"{a}{abs(r['bps'])}bps"))

    def ti(label,val,cls,chg):
        if label == "FED RATE":
            chg_s = f'<span style="color:#ffd88a">{chg}</span>'
        else:
            chg_s = f'<span class="{cls}">{chg}</span>'
        return f'<div class="ticker-item"><span class="lb">{label}</span><span>{val}</span>{chg_s}</div>'

    single = "\n    ".join(ti(*i) for i in items)
    return single + "\n    " + single

# ── MAIN HTML ─────────────────────────────────────────────────────────────────

def build_html(rates, pmms, housing, economic, hpsi, news_fortune, news_inman, mba):
    rates_json     = json.dumps(rates)
    fortune_html   = build_news_items(news_fortune)
    inman_html     = build_news_items(news_inman, show_desc=True)
    mba_html_str   = build_mba_html(mba)
    fannie_rows_str = build_fannie_rows(housing)
    ticker_str     = build_ticker(rates, pmms, hpsi)

    r30   = pmms.get("rate_30y") or 0
    r15   = pmms.get("rate_15y") or 0
    p30   = pmms.get("prev_30y") or r30
    p15   = pmms.get("prev_15y") or r15
    pdate = pmms.get("date","N/A")
    yago  = pmms.get("yago_30y") or 0
    yoy   = round((r30-yago)*100) if yago else 0
    bps30 = round((r30-p30)*100,1)
    bps15 = round((r15-p15)*100,1)
    dir30 = "▲" if bps30>=0 else "▼"
    dir15 = "▲" if bps15>=0 else "▼"
    yoy_label = "▼ More affordable YoY" if yoy<=0 else "▲ Higher YoY"
    yoy_cls   = "pos" if yoy<=0 else "neg"

    home_sales   = f"~{housing.get('total_home_sales')}M" if housing.get("total_home_sales") else "~5.5M"
    sf_starts    = f"{housing.get('sf_starts'):+.1f}%" if housing.get("sf_starts") is not None else "−6.2%"
    gdp          = f"{economic.get('gdp'):.1f}%" if economic.get("gdp") else "N/A"
    unemployment = f"{economic.get('unemployment'):.1f}%" if economic.get("unemployment") else "N/A"
    cpi          = f"{economic.get('cpi'):.1f}%" if economic.get("cpi") else "N/A"
    treasury10y  = f"{economic.get('treasury_10y'):.2f}%" if economic.get("treasury_10y") else "N/A"
    hpsi_val     = f"{hpsi['value']}" if hpsi else "N/A"
    hpsi_date    = hpsi["date"] if hpsi else ""

    fannie_date = housing.get("report_date") or economic.get("report_date") or "Latest"
    try:
        fannie_date = datetime.datetime.strptime(fannie_date,"%Y-%m-%d").strftime("%B %Y")
    except: pass

    obmmi_date = rates[0]["date"] if rates else "N/A"
    try: obmmi_date = datetime.datetime.strptime(obmmi_date,"%Y-%m-%d").strftime("%b %d, %Y")
    except: pass

    mba_headline,mba_date = "","" 
    for src in [mba.get("weeks",[]), mba.get("items",[])]:
        if src: mba_headline,mba_date = src[0].get("title",""),src[0].get("date",""); break
    mba_short = (mba_headline[:65]+"...") if len(mba_headline)>65 else mba_headline

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Newzip Market Tracker</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root{{
    --nz-blue:#4C6DE1;
    --nz-blue-light:#EEF1FC;
    --nz-blue-mid:#7B93E8;
    --nz-teal:#005E53;
    --nz-teal-light:#E6F2F0;
    --nz-teal-mid:#3D8C84;
    --ink:#1a1a2e;
    --paper:#F8F9FC;
    --paper2:#EFF1F8;
    --card:#FFFFFF;
    --border:#E2E5F0;
    --muted:#6B7280;
    --nz-red:#D64045;
    --nz-red-light:#FDF0F0;
    --gold:#D4943A;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Inter',sans-serif;background:var(--paper);color:var(--ink);min-height:100vh;font-size:14px}}
  a{{color:inherit;text-decoration:none}}

  /* HEADER */
  header{{background:white;border-bottom:1px solid var(--border);padding:0 1.5rem;box-shadow:0 1px 4px rgba(76,109,225,.08)}}
  .hi{{max-width:1280px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.9rem 0}}
  .logo-wrap img{{height:28px;display:block}}
  .header-title{{font-size:.78rem;font-weight:600;color:var(--nz-blue);letter-spacing:.04em;text-transform:uppercase}}
  .hmeta{{font-family:'DM Mono',monospace;font-size:.58rem;color:var(--muted);text-align:right;line-height:1.7}}

  /* TICKER */
  .ticker-wrap{{background:var(--nz-blue);overflow:hidden;padding:.38rem 0}}
  .ticker{{display:flex;gap:3rem;animation:scroll 55s linear infinite;width:max-content}}
  .ticker-item{{font-family:'DM Mono',monospace;font-size:.62rem;color:rgba(255,255,255,.9);white-space:nowrap;display:flex;align-items:center;gap:.3rem}}
  .ticker-item .lb{{opacity:.65}}.chup{{color:#a8ffc8}}.chdn{{color:#ffa8a8}}
  @keyframes scroll{{0%{{transform:translateX(0)}}100%{{transform:translateX(-50%)}}}}

  /* LAYOUT */
  main{{max-width:1280px;margin:0 auto;padding:1.75rem 1.5rem}}
  .slbl{{font-family:'DM Mono',monospace;font-size:.58rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:.65rem;display:flex;align-items:center;gap:.5rem}}
  .slbl::after{{content:'';flex:1;height:1px;background:var(--border)}}
  .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-bottom:2rem}}
  .three-col{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1.5rem;margin-bottom:2rem}}
  @media(max-width:860px){{.two-col,.three-col{{grid-template-columns:1fr}}}}

  /* ALERT BANNER */
  .fed-note{{background:var(--nz-blue);color:white;padding:1rem 1.5rem;margin-bottom:2rem;border-radius:8px;display:flex;gap:1.25rem;align-items:flex-start}}
  .fed-icon{{font-size:1.5rem;flex-shrink:0;opacity:.85}}
  .fed-note h4{{font-family:'DM Mono',monospace;font-size:.58rem;letter-spacing:.1em;text-transform:uppercase;color:rgba(255,255,255,.7);margin-bottom:.3rem}}
  .fed-note p{{font-size:.75rem;line-height:1.65;color:rgba(255,255,255,.9)}}.fed-note strong{{color:white}}

  /* STAT TILES */
  .stat-tiles{{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:2rem}}
  @media(max-width:700px){{.stat-tiles{{grid-template-columns:repeat(2,1fr)}}}}
  .stat-tile{{background:white;border:1px solid var(--border);border-radius:8px;padding:1.1rem 1.25rem;position:relative;overflow:hidden}}
  .stat-tile::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--nz-blue)}}
  .st-label{{font-family:'DM Mono',monospace;font-size:.55rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:.35rem}}
  .st-val{{font-size:1.9rem;font-weight:700;line-height:1;margin-bottom:.2rem;color:var(--ink)}}
  .st-sub{{font-family:'DM Mono',monospace;font-size:.55rem;color:var(--muted)}}
  .st-chg{{font-family:'DM Mono',monospace;font-size:.6rem;margin-top:.25rem}}
  .st-chg.neg{{color:var(--nz-red)}}.st-chg.pos{{color:var(--nz-teal)}}

  /* RATE CARDS */
  .rate-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:1rem;margin-bottom:2rem}}
  @media(min-width:500px){{.rate-grid{{grid-template-columns:repeat(3,1fr)}}}}
  @media(min-width:900px){{.rate-grid{{grid-template-columns:repeat(6,1fr)}}}}
  .rate-card{{background:white;border:1px solid var(--border);border-radius:8px;padding:1rem 1.1rem;position:relative;overflow:hidden;transition:box-shadow .2s}}
  .rate-card:hover{{box-shadow:0 4px 16px rgba(76,109,225,.12)}}
  .rate-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--nz-teal)}}
  .rc-label{{font-family:'DM Mono',monospace;font-size:.52rem;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin-bottom:.3rem}}
  .rc-value{{font-size:1.65rem;font-weight:700;line-height:1;margin-bottom:.2rem;color:var(--ink)}}
  .rc-chg{{font-family:'DM Mono',monospace;font-size:.58rem}}.rc-chg.up{{color:var(--nz-red)}}.rc-chg.dn{{color:var(--nz-teal)}}
  .rc-prev{{font-family:'DM Mono',monospace;font-size:.52rem;color:var(--muted);margin-top:.15rem}}

  /* PANELS */
  .panel{{background:white;border:1px solid var(--border);border-radius:8px;overflow:hidden}}
  .ph{{padding:.85rem 1.25rem;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;background:var(--paper)}}
  .ph h3{{font-size:.88rem;font-weight:600;color:var(--ink)}}
  .badge{{font-family:'DM Mono',monospace;font-size:.52rem;padding:.15rem .5rem;text-transform:uppercase;letter-spacing:.06em;border-radius:4px;font-weight:500}}
  .badge-blue{{background:var(--nz-blue-light);color:var(--nz-blue)}}
  .badge-teal{{background:var(--nz-teal-light);color:var(--nz-teal)}}
  .badge-gold{{background:#FDF3E3;color:var(--gold)}}
  .badge-red{{background:var(--nz-red-light);color:var(--nz-red)}}
  .sb{{display:flex;align-items:center;gap:.4rem;padding:.5rem 1.25rem;background:var(--paper);border-top:1px solid var(--border);font-family:'DM Mono',monospace;font-size:.54rem;color:var(--muted)}}
  .sd{{width:5px;height:5px;border-radius:50%;background:var(--nz-teal);flex-shrink:0}}

  /* TABLES */
  .tbl-wrap{{background:white;border:1px solid var(--border);border-radius:8px;margin-bottom:2rem;overflow:hidden}}
  table{{width:100%;border-collapse:collapse;font-size:.78rem}}
  thead th{{font-family:'DM Mono',monospace;font-size:.52rem;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);padding:.65rem 1.25rem;text-align:left;border-bottom:1px solid var(--border);background:var(--paper);white-space:nowrap}}
  tbody tr{{border-bottom:1px solid var(--border);transition:background .15s}}
  tbody tr:hover{{background:var(--paper2)}}tbody tr:last-child{{border-bottom:none}}
  tbody td{{padding:.7rem 1.25rem;vertical-align:middle}}
  .td-type{{font-weight:600;font-size:.78rem}}
  .td-rate{{font-size:1.1rem;font-weight:700;color:var(--ink)}}
  .td-prev{{font-family:'DM Mono',monospace;font-size:.65rem;color:var(--muted)}}
  .td-bps{{font-family:'DM Mono',monospace;font-size:.68rem;font-weight:500}}
  .td-bps.up{{color:var(--nz-red)}}.td-bps.dn{{color:var(--nz-teal)}}
  .bar-wrap{{width:60px;height:4px;background:var(--paper2);border-radius:2px;overflow:hidden}}
  .bar-fill{{height:100%;border-radius:2px}}

  /* PMMS STRIP */
  .pmms-strip{{display:flex;gap:1px;background:var(--border)}}
  .pmms-cell{{flex:1;background:white;padding:.85rem 1rem}}
  .pmms-lbl{{font-family:'DM Mono',monospace;font-size:.52rem;text-transform:uppercase;color:var(--muted);margin-bottom:.2rem}}
  .pmms-val{{font-size:1.3rem;font-weight:700;line-height:1;color:var(--ink)}}
  .pmms-sub{{font-family:'DM Mono',monospace;font-size:.5rem;color:var(--muted);margin-top:.15rem}}

  /* MBA */
  .mba-section{{padding:1rem 1.25rem}}
  .chart-label{{font-family:'DM Mono',monospace;font-size:.54rem;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:.65rem}}
  .bar-row{{display:flex;align-items:center;gap:.6rem;margin-bottom:.5rem}}
  .bar-week{{font-family:'DM Mono',monospace;font-size:.56rem;color:var(--muted);width:50px;flex-shrink:0;text-align:right}}
  .bar-track{{flex:1;height:20px;background:var(--paper2);border-radius:4px;overflow:hidden}}
  .bar-inner{{height:100%;border-radius:4px;display:flex;align-items:center;justify-content:flex-end;padding-right:6px}}
  .bar-inner span{{font-family:'DM Mono',monospace;font-size:.54rem;color:white;font-weight:500}}
  .bar-tag{{font-family:'DM Mono',monospace;font-size:.52rem;width:68px;flex-shrink:0}}
  .mba-link{{display:block;padding:.5rem 0;border-bottom:1px solid var(--border)}}
  .mba-link:last-child{{border-bottom:none}}

  /* NEWS */
  .news-item{{padding:.8rem 1.25rem;border-bottom:1px solid var(--border);display:block;color:var(--ink);transition:background .15s}}
  .news-item:hover{{background:var(--paper2)}}.news-item:last-child{{border-bottom:none}}
  .ni-date{{font-family:'DM Mono',monospace;font-size:.52rem;color:var(--muted);margin-bottom:.2rem;text-transform:uppercase}}
  .ni-title{{font-size:.78rem;font-weight:600;line-height:1.35;margin-bottom:.2rem}}
  .ni-desc{{font-size:.68rem;color:var(--muted);line-height:1.45}}

  /* FORECAST */
  .ftable td,.ftable th{{padding:.65rem 1.25rem}}
  .fc{{font-family:'DM Mono',monospace;font-size:.7rem}}.fc-good{{color:var(--nz-teal);font-weight:600}}.fc-neu{{color:var(--muted)}}
  .fc-tag{{font-family:'DM Mono',monospace;font-size:.58rem;padding:.15rem .5rem;border-radius:4px}}
  .fc-tag-teal{{background:var(--nz-teal-light);color:var(--nz-teal)}}
  .fc-tag-neutral{{background:var(--paper2);color:var(--muted)}}

  /* ECON CARDS */
  .econ-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:1px;background:var(--border);border-radius:0 0 8px 8px;overflow:hidden}}
  .econ-cell{{background:white;padding:.85rem 1.1rem}}
  .ec-label{{font-family:'DM Mono',monospace;font-size:.52rem;text-transform:uppercase;color:var(--muted);margin-bottom:.25rem;letter-spacing:.06em}}
  .ec-val{{font-size:1.4rem;font-weight:700;color:var(--ink);line-height:1;margin-bottom:.15rem}}
  .ec-sub{{font-family:'DM Mono',monospace;font-size:.5rem;color:var(--muted)}}

  footer{{max-width:1280px;margin:0 auto;padding:1.5rem;font-family:'DM Mono',monospace;font-size:.54rem;color:var(--muted);border-top:1px solid var(--border);line-height:1.8;display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap}}
  .footer-logo img{{height:18px;opacity:.5}}
</style>
</head>
<body>

<header>
  <div class="hi">
    <div style="display:flex;align-items:center;gap:1.5rem;">
      <div class="logo-wrap"><img src="{{LOGO_SRC}}" alt="Newzip"></div>
      <div class="header-title">Market Tracker</div>
    </div>
    <div class="hmeta">
      <div>{TODAY_STR}</div>
      <div>OBMMI · PMMS · Fannie Mae ESR · MBA · Inman · Fortune</div>
    </div>
    <div style="font-family:'DM Mono',monospace;font-size:.58rem;color:var(--muted);text-align:right;">
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
      <p>PMMS 30Y at <strong>{r30:.2f}%</strong> as of {pdate} — <strong>{abs(yoy):.0f}bps</strong> {"below" if yoy<=0 else "above"} a year ago ({yago:.2f}%). 10-Year Treasury forecast: <strong>{treasury10y}</strong>. Fannie Mae ESR report: <strong>{fannie_date}</strong>. OBMMI data as of <strong>{obmmi_date}</strong>.</p>
    </div>
  </div>

  <div class="slbl">Key Indicators · {TODAY_STR}</div>
  <div class="stat-tiles">
    <div class="stat-tile">
      <div class="st-label">PMMS 30Y FRM</div>
      <div class="st-val">{r30:.2f}%</div>
      <div class="st-sub">Freddie Mac · {pdate}</div>
      <div class="st-chg neg">{dir30} from {p30:.2f}% prev week</div>
    </div>
    <div class="stat-tile">
      <div class="st-label">PMMS 15Y FRM</div>
      <div class="st-val">{r15:.2f}%</div>
      <div class="st-sub">Freddie Mac · {pdate}</div>
      <div class="st-chg neg">{dir15} from {p15:.2f}% prev week</div>
    </div>
    <div class="stat-tile">
      <div class="st-label">YoY Change</div>
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

  <div class="slbl">Full OBMMI Rate Comparison</div>
  <div class="tbl-wrap">
    <div class="ph"><h3>Optimal Blue Mortgage Market Indices (OBMMI)</h3><span class="badge badge-blue">FRED API · OBMMI</span></div>
    <table>
      <thead><tr><th>Loan Type</th><th>Current Rate</th><th>Prior Period</th><th>Change (bps)</th><th>Trend</th></tr></thead>
      <tbody id="rate-tbody"></tbody>
    </table>
    <div class="sb"><div class="sd"></div><span>Optimal Blue OBMMI via FRED API · Actual locked rates from ~35% of US mortgage transactions · Updated nightly</span></div>
  </div>

  <div class="slbl">Freddie Mac PMMS · Via FRED API</div>
  <div class="panel" style="margin-bottom:2rem;">
    <div class="ph"><h3>Primary Mortgage Market Survey — Weekly Rates</h3><span class="badge badge-teal">Freddie Mac · FRED</span></div>
    <div class="pmms-strip">
      <div class="pmms-cell">
        <div class="pmms-lbl">30Y FRM · {pdate}</div>
        <div class="pmms-val">{r30:.2f}%</div>
        <div class="pmms-sub">Weekly avg · 20% down · excellent credit</div>
      </div>
      <div class="pmms-cell">
        <div class="pmms-lbl">15Y FRM · {pdate}</div>
        <div class="pmms-val">{r15:.2f}%</div>
        <div class="pmms-sub">Weekly survey avg</div>
      </div>
      <div class="pmms-cell">
        <div class="pmms-lbl">30Y Prev Week</div>
        <div class="pmms-val">{p30:.2f}%</div>
        <div class="pmms-sub">Prior PMMS reading</div>
      </div>
      <div class="pmms-cell">
        <div class="pmms-lbl">30Y One Year Ago</div>
        <div class="pmms-val">{yago:.2f}%</div>
        <div class="pmms-sub">Same week prior year</div>
      </div>
      <div class="pmms-cell">
        <div class="pmms-lbl">WoW Change 30Y</div>
        <div class="pmms-val" style="color:{'var(--nz-red)' if bps30>=0 else 'var(--nz-teal)'};">{dir30}{abs(bps30):.0f}bps</div>
        <div class="pmms-sub">Basis points week-over-week</div>
      </div>
    </div>
    <div class="sb"><div class="sd"></div><span>Freddie Mac PMMS via FRED API · Series MORTGAGE30US / MORTGAGE15US · Released Thursdays 12pm ET</span></div>
  </div>

  <div class="two-col">
    <div>
      <div class="slbl">MBA Application Activity · HousingWire / MBA</div>
      <div class="panel">
        <div class="ph"><h3>Mortgage Purchase Applications</h3><span class="badge badge-blue">MBA via HousingWire</span></div>
        <div class="mba-section">{mba_html_str}</div>
        <div class="sb"><div class="sd"></div><span>MBA Weekly Mortgage Applications Survey via HousingWire · Updated Wednesdays</span></div>
      </div>
    </div>
    <div>
      <div class="slbl">Fannie Mae ESR Forecast · {fannie_date} · Live via API</div>
      <div class="tbl-wrap" style="margin-bottom:0;">
        <div class="ph"><h3>30-Year Fixed Rate Forecast</h3><span class="badge badge-gold">Fannie Mae API</span></div>
        <table class="ftable">
          <thead><tr><th>Period</th><th>Forecast</th><th>Source</th><th>Signal</th></tr></thead>
          <tbody>{fannie_rows_str}</tbody>
        </table>
        <div class="sb"><div class="sd"></div><span>Fannie Mae Housing Indicators API · Auto-updated monthly</span></div>
      </div>
    </div>
  </div>

  <div class="two-col">
    <div>
      <div class="slbl">Industry News · Inman</div>
      <div class="panel">
        <div class="ph"><h3>Inman Real Estate News</h3><span class="badge badge-blue">Inman</span></div>
        {inman_html}
        <div class="sb"><div class="sd"></div><span>feeds.feedburner.com/inmannews · Auto-refreshed daily</span></div>
      </div>
    </div>
    <div>
      <div class="slbl">Market News · Fortune</div>
      <div class="panel">
        <div class="ph"><h3>Fortune Real Estate</h3><span class="badge badge-blue">Fortune</span></div>
        {fortune_html}
        <div class="sb"><div class="sd"></div><span>fortune.com/feed/section/real-estate/ · Auto-refreshed daily</span></div>
      </div>
    </div>
  </div>

  <div class="slbl">Fannie Mae ESR · Economic & Housing Outlook · {fannie_date}</div>
  <div class="three-col">
    <div class="panel">
      <div class="ph"><h3>Housing Market Outlook</h3><span class="badge badge-gold">Fannie Mae API</span></div>
      <div style="padding:1rem 1.25rem;">
        <div class="econ-grid" style="margin-bottom:.85rem;border:1px solid var(--border);border-radius:6px;">
          <div class="econ-cell">
            <div class="ec-label">Total Home Sales</div>
            <div class="ec-val">{home_sales}</div>
            <div class="ec-sub">ESR Forecast {TODAY.year}</div>
          </div>
          <div class="econ-cell">
            <div class="ec-label">SF Starts YoY</div>
            <div class="ec-val">{sf_starts}</div>
            <div class="ec-sub">Single-family {TODAY.year}</div>
          </div>
        </div>
        <p style="font-size:.72rem;line-height:1.65;color:var(--muted);">Both new and existing segments contributing to sales growth. Limited inventory despite lower rates keeps prices elevated. Spring season showing improving purchase applications vs last year.</p>
      </div>
      <div class="sb"><div class="sd"></div><span>Fannie Mae Housing Indicators API · {fannie_date}</span></div>
    </div>
    <div class="panel">
      <div class="ph"><h3>Economic Indicators</h3><span class="badge badge-gold">Fannie Mae API</span></div>
      <div style="padding:1rem 1.25rem;">
        <div class="econ-grid" style="border:1px solid var(--border);border-radius:6px;">
          <div class="econ-cell">
            <div class="ec-label">GDP Growth</div>
            <div class="ec-val">{gdp}</div>
            <div class="ec-sub">EOY {TODAY.year} Forecast</div>
          </div>
          <div class="econ-cell">
            <div class="ec-label">Unemployment</div>
            <div class="ec-val">{unemployment}</div>
            <div class="ec-sub">EOY {TODAY.year} Forecast</div>
          </div>
          <div class="econ-cell">
            <div class="ec-label">CPI Inflation</div>
            <div class="ec-val">{cpi}</div>
            <div class="ec-sub">EOY {TODAY.year} Forecast</div>
          </div>
          <div class="econ-cell">
            <div class="ec-label">10-Yr Treasury</div>
            <div class="ec-val">{treasury10y}</div>
            <div class="ec-sub">EOY {TODAY.year} Forecast</div>
          </div>
        </div>
      </div>
      <div class="sb"><div class="sd"></div><span>Fannie Mae Economic Indicators API · {fannie_date}</span></div>
    </div>
    <div class="panel">
      <div class="ph"><h3>Consumer Sentiment · HPSI</h3><span class="badge badge-gold">Fannie Mae API</span></div>
      <div style="padding:1.25rem;">
        <div style="font-size:3.5rem;font-weight:800;line-height:1;margin-bottom:.35rem;color:var(--nz-blue);">{hpsi_val}</div>
        <div style="font-family:'DM Mono',monospace;font-size:.54rem;text-transform:uppercase;color:var(--muted);margin-bottom:.75rem;letter-spacing:.07em;">Home Purchase Sentiment · {hpsi_date}</div>
        <p style="font-size:.72rem;line-height:1.65;color:var(--muted);">Monthly National Housing Survey of 1,000 consumers distilled into a single forward-looking indicator. Higher = more positive sentiment toward buying a home.</p>
      </div>
      <div class="sb"><div class="sd"></div><span>Fannie Mae NHS API · /v1/nhs/hpsi · Monthly</span></div>
    </div>
  </div>

</main>

<footer>
  <div style="font-size:.54rem;line-height:1.8;color:var(--muted);">
    Auto-updated daily via GitHub Actions &nbsp;·&nbsp;
    OBMMI: Optimal Blue via FRED &nbsp;·&nbsp;
    PMMS: Freddie Mac via FRED &nbsp;·&nbsp;
    Fannie Mae ESR APIs &nbsp;·&nbsp;
    MBA via HousingWire &nbsp;·&nbsp;
    Inman &amp; Fortune RSS &nbsp;·&nbsp;
    Not financial advice &nbsp;·&nbsp; {RUN_TS}
  </div>
  <div class="footer-logo"><img src="{{LOGO_SRC}}" alt="Newzip"></div>
</footer>

<script>
const RATES = {rates_json};
function renderCard(r) {{
  var u = r.bps >= 0;
  var pct = Math.min(100, Math.round(r.rate/8*100));
  var dir = u ? 'up' : 'dn';
  var arrow = u ? '\u25b2' : '\u25bc';
  var col = u ? 'var(--nz-red)' : 'var(--nz-teal)';
  return '<div class="rate-card">'
    + '<div class="rc-label">' + r.lb + '</div>'
    + '<div class="rc-value">' + r.rate.toFixed(3) + '%</div>'
    + '<div class="rc-chg ' + dir + '">' + arrow + ' ' + Math.abs(r.bps) + 'bps</div>'
    + '<div class="rc-prev">Prev: ' + r.prev.toFixed(3) + '%</div>'
    + '</div>';
}}
function renderRow(r) {{
  var u = r.bps >= 0;
  var bp = Math.min(100, Math.round(Math.abs(r.bps)/25*100));
  var dir = u ? 'up' : 'dn';
  var arrow = u ? '\u25b2' : '\u25bc';
  var col = u ? 'var(--nz-red)' : 'var(--nz-teal)';
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
    print(f"\n{'='*60}\nNewzip Market Tracker — {RUN_TS}\n{'='*60}\n")
    if not FRED_KEY: print("WARNING: FRED_API_KEY not set\n")
    if not FANNIE_CLIENT_ID or not FANNIE_CLIENT_SECRET: print("WARNING: Fannie Mae creds not set\n")

    rates    = fetch_obmmi()
    pmms     = fetch_pmms()
    housing  = fetch_fannie_housing()
    economic = fetch_fannie_economic()
    hpsi     = fetch_fannie_hpsi()
    news_fortune = fetch_fortune_news()
    news_inman   = fetch_inman_news()
    mba          = fetch_mba()

    html = build_html(rates, pmms, housing, economic, hpsi, news_fortune, news_inman, mba)
    html = html.replace("{LOGO_SRC}", LOGO_SRC)

    with open("index.html","w",encoding="utf-8") as f:
        f.write(html)

    print(f"\n{'='*60}")
    print(f"Done — index.html written ({len(html):,} bytes)")
    print(f"  OBMMI 30Y    : {rates[0]['rate'] if rates else 'N/A'}%")
    print(f"  PMMS 30Y     : {pmms.get('rate_30y')}%")
    print(f"  HPSI         : {hpsi['value'] if hpsi else 'N/A'}")
    print(f"  Fortune news : {len(news_fortune)} articles")
    print(f"  Inman news   : {len(news_inman)} articles")
    print(f"  MBA weeks    : {len(mba.get('weeks',[]))}")
    print(f"{'='*60}\n")
