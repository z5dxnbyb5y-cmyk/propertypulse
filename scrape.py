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

LOGO_SRC = "data:image/png;base64,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"

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
