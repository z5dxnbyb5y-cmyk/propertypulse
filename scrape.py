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

# Debug: print key lengths at startup (values stay hidden, just confirms receipt)
def _debug_secrets():
    fk = (os.environ.get("FRED_API_KEY") or "").strip()
    fi = (os.environ.get("FANNIE_CLIENT_ID") or "").strip()
    fs = (os.environ.get("FANNIE_CLIENT_SECRET") or "").strip()
    print(f"  FRED key: {len(fk)} chars {'OK' if len(fk) > 10 else 'MISSING'}")
    print(f"  Fannie ID: {len(fi)} chars {'OK' if len(fi) > 5 else 'MISSING'}")
    print(f"  Fannie secret: {len(fs)} chars {'OK' if len(fs) > 5 else 'MISSING'}")
_debug_secrets()

LOGO_SRC = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iOTAiIGhlaWdodD0iMjAiIHZpZXdCb3g9IjAgMCA5MCAyMCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTE5Ljk5NzcgMC4zOTg5MDVDMTkuMzkwNiAwLjEzNDkyNCAxOC43NDY2IDAgMTguMDgxMyAwQzE3LjQyOTYgMCAxNi43OTczIDAuMTI5MDU3IDE2LjIwMTggMC4zODMyNjJDMTUuNjI3NyAwLjYyNzY4OSAxNS4xMTE3IDAuOTc5NjY0IDE0LjY2NzYgMS40MjU1QzE0LjI0NDcgMS44NTE3OCAxMy45MDcyIDIuMzQ2NSAxMy42NjY3IDIuODk1OTdMMTMuNjYyOCAyLjg4NDI0TDEzLjY1ODkgMi44OTU5N0MxMy4xNzYgMS43OTcwMyAxMi4yOTczIDAuODk1NTgxIDExLjE2MDcgMC4zOTg5MDVDMTAuNTUzNiAwLjEzNDkyNCA5LjkwOTYyIDAgOS4yNDQzMyAwQzguNTkyNjEgMCA3Ljk2MDI4IDAuMTI5MDU3IDcuMzY0ODEgMC4zODMyNjJDNi43OTA2OCAwLjYyNzY4OSA2LjI3NDc0IDAuOTc5NjY0IDUuODMwNTYgMS40MjU1QzUuNDA3NzIgMS44NTE3OCA1LjA3MDIyIDIuMzQ2NSA0LjgyOTcgMi44OTU5N0M0LjgyOTcgMi44OTU5NyAwLjQ2OTM5MyAxMy4wMzA5IDAuNDA3MzI0IDEzLjE3OTVDMC4xMzc3MTQgMTMuNzk3NCAwIDE0LjQ1NDQgMCAxNS4xMzQ5QzAgMTYuMTAyOSAwLjI4MTI0OCAxNy4wMzc1IDAuODE0NjQ5IDE3LjgzOTNDMS4zMzI1MyAxOC42MTk1IDIuMDU3OTYgMTkuMjI5NiAyLjkxMTQgMTkuNjAxMUMzLjUxODUxIDE5Ljg2NTEgNC4xNjI0NyAyMCA0LjgyNzc2IDIwQzUuNDc5NDggMjAgNi4xMTE4MSAxOS44NzA5IDYuNzA3MjggMTkuNjE2N0M3LjI4MTQxIDE5LjM3MjMgNy43OTczNSAxOS4wMjAzIDguMjQxNTMgMTguNTc0NUM4LjY2NDM3IDE4LjE0ODIgOS4wMDE4NyAxNy42NTM1IDkuMjQyMzkgMTcuMTA0TDkuMjQ2MjcgMTcuMTE1OEw5LjI1MDE0IDE3LjEwNEM5LjM2MjY0IDE3LjM1ODIgOS40OTY0OCAxNy42MDQ2IDkuNjUxNjUgMTcuODM5M0MxMC4xNjk1IDE4LjYxOTUgMTAuODk1IDE5LjIyOTYgMTEuNzQ4NCAxOS42MDExQzEyLjM1NTUgMTkuODY1MSAxMi45OTk1IDIwIDEzLjY2NDggMjBDMTQuMzE2NSAyMCAxNC45NDg4IDE5Ljg3MDkgMTUuNTQ0MyAxOS42MTY3QzE2LjExODQgMTkuMzcyMyAxNi42MzQ0IDE5LjAyMDMgMTcuMDc4NSAxOC41NzQ1QzE3LjUwMTQgMTguMTQ4MiAxNy44Mzg5IDE3LjY1MzUgMTguMDc5NCAxNy4xMDRDMTguMDc5NCAxNy4xMDQgMjIuNDM3OCA2Ljk2OTEgMjIuNTAxOCA2LjgyMDQ5QzIyLjc3MzMgNi4yMDI1OCAyMi45MDkxIDUuNTQzNjEgMjIuOTA5MSA0Ljg2MzEyQzIyLjkwNzIgMi45MjMzNSAyMS43NjQ3IDEuMTY5MzQgMTkuOTk3NyAwLjM5ODkwNVpNNS45NzAyMSA0Ljg2NTA4QzUuOTcwMjEgMy4wNDI2MyA3LjQzNjU4IDEuNTY0MzMgOS4yNDQzMyAxLjU2NDMzQzkuNzA1OTYgMS41NjQzMyAxMC4xNDQzIDEuNjYwMTUgMTAuNTQzOSAxLjgzNDE4QzExLjcwNTcgMi4zNDA2MyAxMi41MjA0IDMuNTA4MDIgMTIuNTIwNCA0Ljg2NTA4QzEyLjUyMDQgNS4zMzgyOSAxMi40MjE1IDUuNzg4MDMgMTIuMjQzIDYuMTkyOEMxMi4xOTQ1IDYuMzA2MjIgOS4yNDYyNiAxMy4xNzU2IDkuMjQ0MzMgMTMuMTc1NlYxMy4xNzM2QzkuMTk3NzcgMTMuMDY0MSA2LjM4NzIzIDYuNTE1NDUgNi4yNTE0NiA2LjIwMjU4VjYuMjAwNjNMNi4yNDU2NCA2LjE4Njk0QzYuMDY3MTkgNS43ODQxMiA1Ljk3MDIxIDUuMzM2MzMgNS45NzAyMSA0Ljg2NTA4Wk04LjEwMTg4IDE1LjEzNDlDOC4xMDE4OCAxNi45NTc0IDYuNjM1NTEgMTguNDM1NyA0LjgyNzc2IDE4LjQzNTdDNC4zNjYxMyAxOC40MzU3IDMuOTI3NzcgMTguMzM5OSAzLjUyODIxIDE4LjE2NThDMi4zNjQ0MiAxNy42NTk0IDEuNTUxNzEgMTYuNDkzOSAxLjU1MTcxIDE1LjEzNDlDMS41NTE3MSAxNC42NjE3IDEuNjUwNjMgMTQuMjEyIDEuODI5MDggMTMuODA3MkMxLjg3NzU3IDEzLjY5MzggNC44MjU4MiA2LjgyNDQgNC44MjU4MiA2LjgyNDRDNC44MjU4MiA2LjgyNDQgNy42ODI5MSAxMy40ODI2IDcuODE4NjkgMTMuNzk3NFYxMy43OTk0TDcuODI0NTEgMTMuODEzMUM4LjAwMjk2IDE0LjIxNzggOC4xMDE4OCAxNC42NjU2IDguMTAxODggMTUuMTM0OVpNMTYuOTM4OSAxNS4xMzQ5QzE2LjkzODkgMTYuOTU3NCAxNS40NzI1IDE4LjQzNTcgMTMuNjY0OCAxOC40MzU3QzEzLjIwMzEgMTguNDM1NyAxMi43NjQ4IDE4LjMzOTkgMTIuMzY1MiAxOC4xNjU4QzExLjIwMzQgMTcuNjU5NCAxMC4zODg3IDE2LjQ5MiAxMC4zODg3IDE1LjEzNDlDMTAuMzg4NyAxNC42NjE3IDEwLjQ4NzYgMTQuMjEyIDEwLjY2NjEgMTMuODA3MkMxMC43MTQ2IDEzLjY5MzggMTMuNjY0OCA2LjgyNDQgMTMuNjY0OCA2LjgyNDRDMTMuNjY0OCA2LjgyNDQgMTYuNTIxOSAxMy40ODI2IDE2LjY1NzYgMTMuNzk3NFYxMy43OTk0TDE2LjY2MzQgMTMuODEzMUMxNi44NCAxNC4yMTc4IDE2LjkzODkgMTQuNjY1NiAxNi45Mzg5IDE1LjEzNDlaTTIxLjA4IDYuMTk0NzZDMjEuMDMxNSA2LjMwODE3IDE4LjA4MzMgMTMuMTc3NiAxOC4wODEzIDEzLjE3NzZWMTMuMTc1NkMxOC4wMzQ4IDEzLjA2NjEgMTUuMjI2MiA2LjUyNTIzIDE1LjA4ODUgNi4yMDQ1NEMxNS4wODg1IDYuMjA0NTQgMTUuMDg4NSA2LjIwMjU4IDE1LjA4NjUgNi4yMDI1OEwxNS4wODA3IDYuMTg4ODlDMTQuOTA0MiA1Ljc4NDEyIDE0LjgwNTMgNS4zMzYzMyAxNC44MDUzIDQuODY3MDNDMTQuODA3MiAzLjA0MjYzIDE2LjI3MzYgMS41NjQzMyAxOC4wODEzIDEuNTY0MzNDMTguNTQzIDEuNTY0MzMgMTguOTgxMyAxLjY2MDE1IDE5LjM4MDkgMS44MzQxOEMyMC41NDI3IDIuMzQwNjMgMjEuMzU3NCAzLjUwODAyIDIxLjM1NzQgNC44NjUwOEMyMS4zNTU0IDUuMzM4MjkgMjEuMjU2NSA1Ljc4ODAzIDIxLjA4IDYuMTk0NzZaIiBmaWxsPSIjNEM2REUxIi8+CjxwYXRoIGQ9Ik0zMy4yOTY0IDUuNzI2NjJDMzQuNDc0MSA1LjcyNjYyIDM1LjQyNTggNi4xMTA2OCAzNi4xNTE0IDYuODc4ODFDMzYuODc3MSA3LjYzNDc1IDM3LjIzOTkgOC42OTU1IDM3LjIzOTkgMTAuMDYxMVYxNi4wMDQ5SDM0Ljc0MTdWMTAuNDA4NkMzNC43NDE3IDkuNjAzODUgMzQuNTQ1NSA4Ljk4ODEyIDM0LjE1MjkgOC41NjEzOEMzMy43NjAzIDguMTIyNDUgMzMuMjI1IDcuOTAyOTkgMzIuNTQ3IDcuOTAyOTlDMzEuODU3IDcuOTAyOTkgMzEuMzA5OCA4LjEyMjQ1IDMwLjkwNTMgOC41NjEzOEMzMC41MTI4IDguOTg4MTIgMzAuMzE2NSA5LjYwMzg1IDMwLjMxNjUgMTAuNDA4NlYxNi4wMDQ5SDI3LjgxODRWNS44NzI5M0gzMC4zMTY1VjcuMTM0ODZDMzAuNjQ5NiA2LjY5NTkzIDMxLjA3MTkgNi4zNTQ1MyAzMS41ODM0IDYuMTEwNjhDMzIuMTA2OCA1Ljg1NDY0IDMyLjY3NzggNS43MjY2MiAzMy4yOTY0IDUuNzI2NjJaIiBmaWxsPSIjNEM2REUxIi8+CjxwYXRoIGQ9Ik00OC44OTQyIDEwLjcxOTVDNDguODk0MiAxMS4wODUyIDQ4Ljg3MDQgMTEuNDE0NCA0OC44MjI5IDExLjcwNzFINDEuNTk2MUM0MS42NTU2IDEyLjQzODYgNDEuOTA1NCAxMy4wMTE3IDQyLjM0NTYgMTMuNDI2MkM0Mi43ODU3IDEzLjg0MDggNDMuMzI3IDE0LjA0OCA0My45Njk0IDE0LjA0OEM0NC44OTcyIDE0LjA0OCA0NS41NTc0IDEzLjYzOTYgNDUuOTUgMTIuODIyN0g0OC42NDQ0QzQ4LjM1ODkgMTMuNzk4MSA0Ny44MTE3IDE0LjYwMjggNDcuMDAyOCAxNS4yMzY4QzQ2LjE5MzkgMTUuODU4NiA0NS4yMDA2IDE2LjE2OTUgNDQuMDIyOSAxNi4xNjk1QzQzLjA3MTIgMTYuMTY5NSA0Mi4yMTQ3IDE1Ljk1NjIgNDEuNDUzNCAxNS41Mjk0QzQwLjcwMzkgMTUuMDkwNSA0MC4xMTUxIDE0LjQ3NDggMzkuNjg2OCAxMy42ODIyQzM5LjI3MDUgMTIuODg5NyAzOS4wNjIzIDExLjk3NTMgMzkuMDYyMyAxMC45Mzg5QzM5LjA2MjMgOS44OTAzNyAzOS4yNzA1IDguOTY5ODMgMzkuNjg2OCA4LjE3NzMyQzQwLjEwMzIgNy4zODQ4IDQwLjY4NjEgNi43NzUxOCA0MS40MzU1IDYuMzQ4NDRDNDIuMTg1IDUuOTIxNyA0My4wNDc0IDUuNzA4MzMgNDQuMDIyOSA1LjcwODMzQzQ0Ljk2MjcgNS43MDgzMyA0NS44MDEzIDUuOTE1NiA0Ni41Mzg5IDYuMzMwMTVDNDcuMjg4MyA2Ljc0NDY5IDQ3Ljg2NTIgNy4zMzYwMyA0OC4yNjk3IDguMTA0MTZDNDguNjg2MSA4Ljg2MDEgNDguODk0MiA5LjczMTg3IDQ4Ljg5NDIgMTAuNzE5NVpNNDYuMzA2OSA5Ljk4NzkxQzQ2LjI5NSA5LjMyOTUxIDQ2LjA2MyA4LjgwNTIzIDQ1LjYxMSA4LjQxNTA3QzQ1LjE1ODkgOC4wMTI3MiA0NC42MDU4IDcuODExNTQgNDMuOTUxNSA3LjgxMTU0QzQzLjMzMjkgNy44MTE1NCA0Mi44MDk1IDguMDA2NjIgNDIuMzgxMyA4LjM5Njc4QzQxLjk2NDkgOC43NzQ3NSA0MS43MDkxIDkuMzA1MTMgNDEuNjE0IDkuOTg3OTFINDYuMzA2OVoiIGZpbGw9IiM0QzZERTEiLz4KPHBhdGggZD0iTTY0LjUxMDkgNS44NzI5M0w2MS42MjAyIDE2LjAwNDlINTguOTI1OEw1Ny4xMjM2IDguOTI3MTZMNTUuMzIxMyAxNi4wMDQ5SDUyLjYwOTFMNDkuNzAwNiA1Ljg3MjkzSDUyLjIzNDRMNTMuOTgzMSAxMy41OTA4TDU1Ljg3NDUgNS44NzI5M0g1OC41MTU0TDYwLjM3MTEgMTMuNTcyNUw2Mi4xMTk4IDUuODcyOTNINjQuNTEwOVoiIGZpbGw9IiM0QzZERTEiLz4KPHBhdGggZD0iTTY4LjIzNTggMTMuOTAxN0g3Mi42NDMyVjE2LjAwNDlINjUuMzk4NlYxMy45MzgzTDY5LjcxNjggNy45NzYxNEg2NS40MTY1VjUuODcyOTNINzIuNTg5N1Y3LjkzOTU2TDY4LjIzNTggMTMuOTAxN1oiIGZpbGw9IiM0QzZERTEiLz4KPHBhdGggZD0iTTc1LjkzMzYgNC42NjU4N0M3NS40OTM0IDQuNjY1ODcgNzUuMTI0NiA0LjUyNTY1IDc0LjgyNzIgNC4yNDUyM0M3NC41NDE3IDMuOTUyNiA3NC4zOTkgMy41OTI5MiA3NC4zOTkgMy4xNjYxOUM3NC4zOTkgMi43Mzk0NSA3NC41NDE3IDIuMzg1ODYgNzQuODI3MiAyLjEwNTQzQzc1LjEyNDYgMS44MTI4MSA3NS40OTM0IDEuNjY2NSA3NS45MzM2IDEuNjY2NUM3Ni4zNzM3IDEuNjY2NSA3Ni43MzY1IDEuODEyODEgNzcuMDIyIDIuMTA1NDNDNzcuMzE5NCAyLjM4NTg2IDc3LjQ2ODEgMi43Mzk0NSA3Ny40NjgxIDMuMTY2MTlDNzcuNDY4MSAzLjU5MjkyIDc3LjMxOTQgMy45NTI2IDc3LjAyMiA0LjI0NTIzQzc2LjczNjUgNC41MjU2NSA3Ni4zNzM3IDQuNjY1ODcgNzUuOTMzNiA0LjY2NTg3Wk03Ny4xNjQ4IDUuODcyOTNWMTYuMDA0OUg3NC42NjY3VjUuODcyOTNINzcuMTY0OFoiIGZpbGw9IiM0QzZERTEiLz4KPHBhdGggZD0iTTgyLjIyMDMgNy4zMzYwM0M4Mi41NDE1IDYuODcyNzIgODIuOTgxNiA2LjQ4ODY1IDgzLjU0MDcgNi4xODM4NEM4NC4xMTE3IDUuODY2ODMgODQuNzYwMSA1LjcwODMzIDg1LjQ4NTcgNS43MDgzM0M4Ni4zMzAzIDUuNzA4MzMgODcuMDkxNiA1LjkyMTcgODcuNzY5NyA2LjM0ODQ0Qzg4LjQ1OTcgNi43NzUxOCA4OS4wMDA5IDcuMzg0OCA4OS4zOTM1IDguMTc3MzJDODkuNzk3OSA4Ljk1NzY0IDkwLjAwMDIgOS44NjU5OCA5MC4wMDAyIDEwLjkwMjRDOTAuMDAwMiAxMS45Mzg3IDg5Ljc5NzkgMTIuODU5MyA4OS4zOTM1IDEzLjY2NEM4OS4wMDA5IDE0LjQ1NjUgODguNDU5NyAxNS4wNzIyIDg3Ljc2OTcgMTUuNTExMUM4Ny4wOTE2IDE1Ljk1MDEgODYuMzMwMyAxNi4xNjk1IDg1LjQ4NTcgMTYuMTY5NUM4NC43NjAxIDE2LjE2OTUgODQuMTE3NyAxNi4wMTcxIDgzLjU1ODYgMTUuNzEyM0M4My4wMTE0IDE1LjQwNzUgODIuNTY1MyAxNS4wMjM0IDgyLjIyMDMgMTQuNTYwMVYxOS45OTk4SDc5LjcyMjJWNS44NzI5M0g4Mi4yMjAzVjcuMzM2MDNaTTg3LjQ0ODUgMTAuOTAyNEM4Ny40NDg1IDEwLjI5MjcgODcuMzIzNiA5Ljc2ODQ0IDg3LjA3MzggOS4zMjk1MUM4Ni44MzU5IDguODc4MzkgODYuNTE0NyA4LjUzNyA4Ni4xMTAyIDguMzA1MzRDODUuNzE3NyA4LjA3MzY4IDg1LjI4OTQgNy45NTc4NSA4NC44MjU1IDcuOTU3ODVDODQuMzczNCA3Ljk1Nzg1IDgzLjk0NTIgOC4wNzk3OCA4My41NDA3IDguMzIzNjNDODMuMTQ4MiA4LjU1NTI5IDgyLjgyNyA4Ljg5NjY4IDgyLjU3NzIgOS4zNDc4QzgyLjMzOTIgOS43OTg5MyA4Mi4yMjAzIDEwLjMyOTMgODIuMjIwMyAxMC45Mzg5QzgyLjIyMDMgMTEuNTQ4NiA4Mi4zMzkyIDEyLjA3ODkgODIuNTc3MiAxMi41MzAxQzgyLjgyNyAxMi45ODEyIDgzLjE0ODIgMTMuMzI4NyA4My41NDA3IDEzLjU3MjVDODMuOTQ1MiAxMy44MDQyIDg0LjM3MzQgMTMuOTIgODQuODI1NSAxMy45MkM4NS4yODk0IDEzLjkyIDg1LjcxNzcgMTMuNzk4MSA4Ni4xMTAyIDEzLjU1NDJDODYuNTE0NyAxMy4zMTA0IDg2LjgzNTkgMTIuOTYyOSA4Ny4wNzM4IDEyLjUxMThDODcuMzIzNiAxMi4wNjA2IDg3LjQ0ODUgMTEuNTI0MiA4Ny40NDg1IDEwLjkwMjRaIiBmaWxsPSIjNEM2REUxIi8+Cjwvc3ZnPg=="

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
    """Authenticate with Fannie Mae Exchange APIs using AWS Cognito."""
    global _fannie_token, _fannie_token_expiry
    if _fannie_token and _fannie_token_expiry and datetime.datetime.utcnow() < _fannie_token_expiry:
        return _fannie_token
    if not FANNIE_CLIENT_ID or not FANNIE_CLIENT_SECRET:
        print("  WARN: Fannie Mae credentials not set")
        return None

    print("  Authenticating with Fannie Mae Exchange (Cognito)...")

    # The Exchange by Fannie Mae uses AWS Cognito client credentials flow
    # Token endpoint: https://cognito-idp.{region}.amazonaws.com/{userPoolId}/.well-known/jwks.json
    # Auth via Cognito hosted UI token endpoint
    import base64 as _b64

    # Try the standard Cognito token endpoint with client_credentials grant
    # The Exchange uses us-east-1 region based on their infrastructure
    cognito_endpoints = [
        "https://auth.theexchange.fanniemae.com/oauth2/token",
        "https://fanniemae.auth.us-east-1.amazoncognito.com/oauth2/token",
        "https://api.fanniemae.com/v1/oauth2/token",
    ]

    # Encode client credentials as Basic Auth (standard for Cognito client_credentials)
    creds = _b64.b64encode(f"{FANNIE_CLIENT_ID}:{FANNIE_CLIENT_SECRET}".encode()).decode()

    for endpoint in cognito_endpoints:
        print(f"  Trying: {endpoint}")
        raw = post(endpoint, {"grant_type": "client_credentials"},
                   headers={"Authorization": f"Basic {creds}",
                            "Content-Type": "application/x-www-form-urlencoded"})
        if raw:
            try:
                data = json.loads(raw)
                token = data.get("access_token") or data.get("id_token")
                if token:
                    exp = int(data.get("expires_in", 3600))
                    _fannie_token = token
                    _fannie_token_expiry = datetime.datetime.utcnow() + datetime.timedelta(seconds=exp - 60)
                    print(f"  Token OK from {endpoint} (expires {exp}s)")
                    return _fannie_token
                else:
                    print(f"  No token in response from {endpoint}: {list(data.keys())}")
            except Exception as e:
                print(f"  Parse error from {endpoint}: {e}")
        else:
            print(f"  No response from {endpoint}")

    print("  All Fannie Mae token endpoints failed")
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
    key = (FRED_KEY or "").strip()
    if not key:
        print(f"  WARN: FRED_API_KEY not set, skipping {series_id}")
        return []
    params = urllib.parse.urlencode({
        "series_id": series_id, "api_key": key, "file_type": "json",
        "sort_order": "desc", "limit": limit, "observation_start": "2020-01-01",
    })
    raw = fetch(f"https://api.stlouisfed.org/fred/series/observations?{params}")
    if not raw: return []
    try:
        data = json.loads(raw)
        if "error_code" in data:
            print(f"  FRED error {series_id}: {data.get('error_message','unknown')}")
            return []
        return [o for o in data.get("observations", []) if o.get("value") not in (".", "")]
    except Exception as e:
        print(f"  FRED parse error {series_id}: {e}")
        return []

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

# ── MORTGAGE/TREASURY SPREAD ──────────────────────────────────────────────────

def fetch_spread():
    """
    Fetch 30yr mortgage vs 10yr Treasury spread via FRED.
    MORTGAGE30US (weekly) minus DGS10 (daily) = spread in basis points.
    Historically ~170bps; elevated spread (>250bps) signals lender risk premium.
    """
    print("Fetching 30yr/10yr spread from FRED...")
    r30, _, d30 = fred_two("MORTGAGE30US")
    t10, _, d10 = fred_two("DGS10")
    if r30 is None or t10 is None:
        return {"spread_bps": None, "r30": r30, "t10": t10, "date_30": d30, "date_10": d10}
    spread_bps = round((r30 - t10) * 100)
    # Historical context: pre-2022 normal ~170bps, 2023 peak ~310bps
    if spread_bps < 200:
        signal = "Tight"
        signal_cls = "nz-teal"
    elif spread_bps < 250:
        signal = "Normal"
        signal_cls = "nz-teal"
    else:
        signal = "Elevated"
        signal_cls = "nz-red"
    print(f"  30yr:{r30:.2f}% 10yr:{t10:.2f}% Spread:{spread_bps}bps ({signal})")
    return {
        "spread_bps": spread_bps,
        "r30":        round(r30, 2),
        "t10":        round(t10, 2),
        "date_30":    d30,
        "date_10":    d10,
        "signal":     signal,
        "signal_cls": signal_cls,
    }


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
    """
    Fetch housing/mortgage news. Source priority:
    1. Mortgage News Daily RSS — confirmed fresh, housing/mortgage focused, public feed
    2. Inman RSS fallback (already fetched separately, but just in case)
    """
    print("Fetching Mortgage News Daily RSS...")
    articles = []
    seen = set()

    # Primary: Mortgage News Daily industry news RSS
    for feed_url in [
        "https://www.mortgagenewsdaily.com/rss/news",
        "https://www.mortgagenewsdaily.com/rss/full",
    ]:
        if articles: break
        raw = fetch(feed_url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (compatible; NewzipBot/1.0)"})
        if not raw: continue
        for m in re.finditer(r'<item>(.*?)</item>', raw, re.DOTALL | re.IGNORECASE):
            block = m.group(1)
            title_m = re.search(r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', block, re.DOTALL)
            link_m  = re.search(r'<link>(.*?)</link>', block, re.DOTALL)
            pub_m   = re.search(r'<pubDate>(.*?)</pubDate>', block, re.DOTALL)
            if not (title_m and link_m): continue
            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
            url   = link_m.group(1).strip()
            pub   = pub_m.group(1).strip() if pub_m else ""
            if url in seen or len(title) < 10: continue
            seen.add(url)
            try:
                dt = datetime.datetime.strptime(pub[:25], "%a, %d %b %Y %H:%M")
                date_str = dt.strftime("%b %d, %Y")
            except: date_str = pub[:16]
            articles.append({"title": title, "url": url, "date": date_str, "desc": ""})
            if len(articles) >= 6: break

    # Fallback: HousingWire
    if not articles:
        raw = fetch("https://www.housingwire.com/feed/", timeout=20)
        if raw:
            for m in re.finditer(r'<item>(.*?)</item>', raw, re.DOTALL | re.IGNORECASE):
                block = m.group(1)
                title_m = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', block, re.DOTALL)
                link_m  = re.search(r'<link>(.*?)</link>', block, re.DOTALL)
                pub_m   = re.search(r'<pubDate>(.*?)</pubDate>', block, re.DOTALL)
                if not (title_m and link_m): continue
                title = title_m.group(1).strip()
                url   = link_m.group(1).strip()
                pub   = pub_m.group(1).strip() if pub_m else ""
                if url in seen or len(title) < 10: continue
                seen.add(url)
                try:
                    dt = datetime.datetime.strptime(pub[:25], "%a, %d %b %Y %H:%M")
                    date_str = dt.strftime("%b %d, %Y")
                except: date_str = pub[:16]
                articles.append({"title": title, "url": url, "date": date_str, "desc": ""})
                if len(articles) >= 6: break

    print(f"  Housing news: {len(articles)} articles")
    return articles


def fetch_pending():
    """
    Fetch NAR Existing Home Sales via FRED.
    Series: EXHOSLUSM495S (monthly, seasonally adjusted annual rate, millions of units)
    Confirmed FRED series — NAR data, released ~3-4 weeks after reference month.
    """
    print("Fetching Existing Home Sales from FRED...")
    key = (FRED_KEY or "").strip()
    if not key:
        print("  WARN: FRED_API_KEY not set, skipping EXHOSLUSM495S")
        return {"value": None, "prev": None, "date": None, "yoy": None, "mom": None}
    params = urllib.parse.urlencode({
        "series_id": "EXHOSLUSM495S", "api_key": key, "file_type": "json",
        "sort_order": "desc", "limit": 15,
    })
    raw = fetch(f"https://api.stlouisfed.org/fred/series/observations?{params}")
    obs = []
    if raw:
        try:
            data = json.loads(raw)
            obs = [o for o in data.get("observations", []) if o.get("value") not in (".", "")]
        except Exception as e:
            print(f"  FRED parse error EXHOSLUSM495S: {e}")
    if not obs:
        return {"value": None, "prev": None, "date": None, "yoy": None, "mom": None}
    valid = []
    for o in obs:
        try:
            v = float(o["value"])
            valid.append({"val": v, "date": o["date"]})
        except: pass
    if not valid:
        return {"value": None, "prev": None, "date": None, "yoy": None, "mom": None}
    current = valid[0]
    prev_mo = valid[1] if len(valid) > 1 else None
    yago    = valid[12] if len(valid) > 12 else None
    mom = round((current["val"] - prev_mo["val"]) / prev_mo["val"] * 100, 1) if prev_mo else None
    yoy = round((current["val"] - yago["val"])    / yago["val"]   * 100, 1) if yago    else None
    try:
        date_str = datetime.datetime.strptime(current["date"], "%Y-%m-%d").strftime("%b %Y")
    except:
        date_str = current["date"]
    # FRED EXHOSLUSM495S is in actual units — divide by 1,000,000 for millions
    cur_m  = round(current['val'] / 1_000_000, 2)
    prev_m = round(prev_mo['val'] / 1_000_000, 2) if prev_mo else None
    if mom is not None and yoy is not None:
        print(f"  Existing Home Sales: {cur_m:.2f}M SAAR ({date_str}) MoM:{mom:+.1f}% YoY:{yoy:+.1f}%")
    else:
        print(f"  Existing Home Sales: {cur_m:.2f}M SAAR ({date_str})")
    return {
        "value":   cur_m,
        "prev":    prev_m,
        "yoy":     yoy,
        "mom":     mom,
        "date":    date_str,
        "history": [{"val": round(o["val"] / 1_000_000, 2), "date": o["date"]} for o in valid[:6]],
    }


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


def build_pending_html(pending):
    val  = pending.get("value")
    mom  = pending.get("mom")
    yoy  = pending.get("yoy")
    date = pending.get("date") or "N/A"
    hist = pending.get("history", [])

    if val is None:
        return '<div style="padding:.5rem 0;color:var(--muted);font-size:.75rem;">Existing Home Sales data unavailable.</div>'

    mom_col   = "var(--nz-teal)" if (mom or 0) >= 0 else "var(--nz-red)"
    yoy_col   = "var(--nz-teal)" if (yoy or 0) >= 0 else "var(--nz-red)"
    mom_arrow = "&#8593;" if (mom or 0) >= 0 else "&#8595;"
    yoy_arrow = "&#8593;" if (yoy or 0) >= 0 else "&#8595;"
    mom_str   = f"{mom_arrow} {abs(mom):.1f}% MoM" if mom is not None else "MoM N/A"
    yoy_str   = f"{yoy_arrow} {abs(yoy):.1f}% YoY" if yoy is not None else "YoY N/A"

    # Labeled bar chart — each bar has the value on top and month label below
    chart = ""
    if hist:
        items = list(reversed(hist))  # oldest to newest left-to-right
        vals  = [h["val"] for h in items]
        min_v = min(vals)
        rng   = (max(vals) - min_v) or 0.01
        for i, h in enumerate(items):
            v       = h["val"]
            is_last = (i == len(items) - 1)
            h_px    = max(20, round(((v - min_v) / rng) * 60 + 20))
            bar_bg  = "var(--nz-blue)" if is_last else "var(--paper2)"
            bar_bdr = "var(--nz-blue)" if is_last else "var(--border)"
            lbl_col = "var(--nz-blue)" if is_last else "var(--muted)"
            val_col = "white" if is_last else "var(--ink)"
            try:
                mo = datetime.datetime.strptime(h["date"], "%Y-%m-%d").strftime("%b")
            except:
                mo = str(h["date"])[:3]
            chart += (
                f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;">'
                f'<div style="font-family:\'DM Mono\',monospace;font-size:.46rem;color:{val_col};font-weight:600;white-space:nowrap;">{v:.2f}M</div>'
                f'<div style="width:100%;height:{h_px}px;background:{bar_bg};border-radius:3px 3px 0 0;border:1px solid {bar_bdr};"></div>'
                f'<div style="font-family:\'DM Mono\',monospace;font-size:.48rem;color:{lbl_col};font-weight:{"600" if is_last else "400"};">{mo}</div>'
                f'</div>'
            )

    chart_block = (
        f'<div style="display:flex;align-items:flex-end;gap:5px;padding:0 .1rem;margin-top:.75rem;">{chart}</div>'
        if chart else ""
    )

    out = '<div style="padding:1rem 1.25rem;">'
    out += '<div style="display:flex;align-items:flex-end;gap:1.5rem;margin-bottom:.1rem;">'
    out += '<div>'
    out += f'<div style="font-family:\'DM Mono\',monospace;font-size:.52rem;text-transform:uppercase;color:var(--muted);margin-bottom:.2rem;">SAAR &middot; {date}</div>'
    out += f'<div style="font-size:2.2rem;font-weight:700;line-height:1;color:var(--ink);">{val:.2f}M</div>'
    out += '<div style="font-family:\'DM Mono\',monospace;font-size:.54rem;color:var(--muted);margin-top:.2rem;">Million units, seasonally adjusted annual rate</div>'
    out += '</div>'
    out += '<div style="display:flex;flex-direction:column;gap:.4rem;margin-left:auto;text-align:right;">'
    out += f'<div style="font-family:\'DM Mono\',monospace;font-size:.65rem;font-weight:600;color:{mom_col};">{mom_str}</div>'
    out += f'<div style="font-family:\'DM Mono\',monospace;font-size:.65rem;font-weight:600;color:{yoy_col};">{yoy_str}</div>'
    out += '</div></div>'
    out += chart_block
    out += '</div>'
    return out

def build_fannie_rows(housing):
    year = TODAY.year
    rates = housing.get("mortgage_rate_30y", {})
    has_live = bool(rates)

    # Fannie Mae March 2026 ESR published forecast — used when API auth is unavailable.
    # Source: Fannie Mae Economic & Strategic Research Group, March 2026 Housing Forecast
    # Update these values each month once the ESR PDF is released.
    ESR_FALLBACK = {
        f"Q1 {year}":       6.60,
        f"Q2 {year}":       6.50,
        f"Q3 {year}":       6.40,
        f"Q4 {year}":       6.30,
        f"EOY {year+1}":    6.10,
    }

    quarters = [
        (f"Q1 {year}",    f"Q1 {year}"),
        (f"Q2 {year}",    f"Q2 {year}"),
        (f"Q3 {year}",    f"Q3 {year}"),
        (f"Q4 {year}",    f"Q4 {year}"),
        (f"EOY {year+1}", f"Full Year {year+1}"),
    ]
    rows = ""
    for key, label in quarters:
        live_val = rates.get(key)
        val      = live_val if live_val else ESR_FALLBACK.get(key)
        if val:
            cls = "fc-good" if val < 6.5 else ""
            tag = "fc-tag-teal" if val < 6.5 else "fc-tag-neutral"
            sig = "Below 6.5%" if val < 6.5 else "Above 6.5%"
            if live_val:
                src = "Live · Fannie Mae API"
                badge_cls = "fc-tag-teal"
            else:
                src = "Est. · Fannie Mae Mar 2026 ESR"
                badge_cls = "fc-tag-neutral"
                sig = "Est."
            rows += (
                f'\n<tr><td class="td-type">{label}</td>'
                f'<td class="fc {cls}">{val:.2f}%</td>'
                f'<td class="fc fc-neu" style="font-size:.62rem;">{src}</td>'
                f'<td><span class="fc-tag {badge_cls}">{sig}</span></td></tr>'
            )
        else:
            rows += (
                f'\n<tr><td class="td-type">{label}</td>'
                f'<td class="fc fc-neu">—</td>'
                f'<td class="fc fc-neu">—</td>'
                f'<td><span class="fc-tag fc-tag-neutral">Pending</span></td></tr>'
            )
    return rows

def build_ticker(rates, pmms, hpsi, spread=None):
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
    if spread and spread.get("spread_bps"):
        s_cls = "chdn" if spread["spread_bps"] <= 250 else "chup"
        items.append(("30Y/10Y", f"{spread['spread_bps']}bps", s_cls, spread.get("signal","")))
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

def build_html(rates, pmms, housing, economic, hpsi, news_fortune, news_inman, pending, spread):
    rates_json     = json.dumps(rates)
    fortune_html   = build_news_items(news_fortune)
    inman_html     = build_news_items(news_inman, show_desc=True)
    pending_html_str = build_pending_html(pending)
    fannie_rows_str = build_fannie_rows(housing)
    ticker_str     = build_ticker(rates, pmms, hpsi, spread)

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
    # Use live Fannie Mae API data if available, otherwise fall back to latest known values
    # Fallbacks from Fannie Mae March 2026 ESR report
    gdp          = f"{economic.get('gdp'):.1f}%"          if economic.get("gdp")          else "~2.3%"
    unemployment = f"{economic.get('unemployment'):.1f}%"  if economic.get("unemployment")  else "~4.2%"
    cpi          = f"{economic.get('cpi'):.1f}%"           if economic.get("cpi")           else "~2.7%"
    treasury10y  = f"{economic.get('treasury_10y'):.2f}%"  if economic.get("treasury_10y")  else "~4.3%"
    hpsi_val     = f"{hpsi['value']}" if hpsi else "~73"
    hpsi_date    = hpsi["date"] if hpsi else "Feb 2026"
    # Mark as estimated if from fallback
    gdp_src      = "Live · Fannie Mae API" if economic.get("gdp") else "Est. · Fannie Mae Mar 2026"
    unemp_src    = "Live · Fannie Mae API" if economic.get("unemployment") else "Est. · Fannie Mae Mar 2026"
    cpi_src      = "Live · Fannie Mae API" if economic.get("cpi") else "Est. · Fannie Mae Mar 2026"
    tsy_src      = "Live · Fannie Mae API" if economic.get("treasury_10y") else "Est. · Fannie Mae Mar 2026"

    fannie_date = housing.get("report_date") or economic.get("report_date") or "Latest"
    try:
        fannie_date = datetime.datetime.strptime(fannie_date,"%Y-%m-%d").strftime("%B %Y")
    except: pass

    obmmi_date = rates[0]["date"] if rates else "N/A"
    try: obmmi_date = datetime.datetime.strptime(obmmi_date,"%Y-%m-%d").strftime("%b %d, %Y")
    except: pass

    # Spread calculations
    spread_bps_str    = f"{spread.get('spread_bps')}bps" if spread.get('spread_bps') else "N/A"
    spread_r30        = spread.get('r30') or "—"
    spread_t10        = spread.get('t10') or "—"
    spread_signal     = spread.get('signal') or "—"
    _spread_sig_color = spread.get('signal_cls','muted')
    spread_cls        = "pos" if _spread_sig_color == "nz-teal" else "neg"
    spread_signal_label = f"{spread_signal} · Historical norm ~170bps"


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
      <div>OBMMI · PMMS · Fannie Mae ESR · Existing Sales · Inman · Fortune</div>
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
      <div class="st-label">30Y/10Y Spread</div>
      <div class="st-val">{spread_bps_str}</div>
      <div class="st-sub">30Y {spread_r30}% · 10Y {spread_t10}% · FRED</div>
      <div class="st-chg {spread_cls}">{spread_signal_label}</div>
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
      <div class="slbl">Existing Home Sales · NAR via FRED</div>
      <div class="panel">
        <div class="ph"><h3>Existing Home Sales</h3><span class="badge badge-teal">FRED · NAR</span></div>
        {pending_html_str}
        <div class="sb"><div class="sd"></div><span>NAR Existing Home Sales via FRED · Series EXHOSLUSM495S · Millions SAAR · Released monthly</span></div>
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
        <div class="sb"><div class="sd"></div><span>Fannie Mae Housing Indicators API · Est. values from Mar 2026 ESR when API unavailable · Auto-updated monthly</span></div>
      </div>
    </div>
  </div>

  <div class="slbl">30-Year Mortgage vs 10-Year Treasury Spread · Via FRED</div>
  <div class="panel" style="margin-bottom:2rem;">
    <div class="ph"><h3>30Y Mortgage / 10Y Treasury Spread</h3><span class="badge badge-blue">FRED API</span></div>
    <div class="pmms-strip">
      <div class="pmms-cell">
        <div class="pmms-lbl">Current Spread</div>
        <div class="pmms-val" style="color:{'var(--nz-red)' if spread.get('spread_bps',0) and spread['spread_bps'] > 250 else 'var(--nz-teal)'};">{spread_bps_str}</div>
        <div class="pmms-sub">30Y minus 10Y Treasury</div>
      </div>
      <div class="pmms-cell">
        <div class="pmms-lbl">30Y Mortgage</div>
        <div class="pmms-val">{spread_r30}%</div>
        <div class="pmms-sub">PMMS weekly avg</div>
      </div>
      <div class="pmms-cell">
        <div class="pmms-lbl">10Y Treasury</div>
        <div class="pmms-val">{spread_t10}%</div>
        <div class="pmms-sub">FRED DGS10 · Daily</div>
      </div>
      <div class="pmms-cell">
        <div class="pmms-lbl">Signal</div>
        <div class="pmms-val" style="font-size:1rem;color:{'var(--nz-red)' if spread.get('signal') == 'Elevated' else 'var(--nz-teal)'};">{spread_signal}</div>
        <div class="pmms-sub">Pre-2022 norm ~170bps · 2023 peak ~310bps</div>
      </div>
    </div>
    <div class="sb"><div class="sd"></div><span>FRED API · MORTGAGE30US (weekly) minus DGS10 (daily) · Spread tracks lender risk premium above risk-free rate · Updated daily</span></div>
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
      <div class="slbl">Housing Market News · Mortgage News Daily</div>
      <div class="panel">
        <div class="ph"><h3>Housing Market News</h3><span class="badge badge-blue">Mortgage News Daily</span></div>
        {fortune_html}
        <div class="sb"><div class="sd"></div><span>mortgagenewsdaily.com · Mortgage &amp; housing industry news · Auto-refreshed daily</span></div>
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
            <div class="ec-sub">{gdp_src}</div>
          </div>
          <div class="econ-cell">
            <div class="ec-label">Unemployment</div>
            <div class="ec-val">{unemployment}</div>
            <div class="ec-sub">{unemp_src}</div>
          </div>
          <div class="econ-cell">
            <div class="ec-label">CPI Inflation</div>
            <div class="ec-val">{cpi}</div>
            <div class="ec-sub">{cpi_src}</div>
          </div>
          <div class="econ-cell">
            <div class="ec-label">10-Yr Treasury</div>
            <div class="ec-val">{treasury10y}</div>
            <div class="ec-sub">{tsy_src}</div>
          </div>
        </div>
      </div>
      <div class="sb"><div class="sd"></div><span>Fannie Mae Economic Indicators API · {fannie_date}</span></div>
    </div>
    <div class="panel">
      <div class="ph"><h3>Market Risk Factors</h3><span class="badge badge-gold">Fannie Mae ESR</span></div>
      <div style="padding:1rem 1.25rem;">
        <div style="font-size:.73rem;line-height:1.75;color:var(--muted);">
          <div style="margin-bottom:.5rem;"><span style="color:var(--nz-red);font-weight:700;">↑ Risk:</span> Slower GDP growth forecast — weaker economy supports lower rates but signals demand risk</div>
          <div style="margin-bottom:.5rem;"><span style="color:var(--nz-red);font-weight:700;">↑ Risk:</span> Limited inventory despite lower rates — prices stay elevated, affordability constrained</div>
          <div style="margin-bottom:.5rem;"><span style="color:var(--nz-red);font-weight:700;">↑ Risk:</span> Geopolitical events pushing oil &amp; Treasury yields higher near-term</div>
          <div style="margin-bottom:.5rem;"><span style="color:var(--nz-red);font-weight:700;">↑ Risk:</span> Single-family starts forecast −6.2% YoY — supply constraints persist</div>
          <div><span style="color:var(--nz-teal);font-weight:700;">↓ Positive:</span> Rates ~45bps below year-ago — spring 2026 buyers better positioned than 2025</div>
        </div>
      </div>
      <div class="sb"><div class="sd"></div><span>Fannie Mae ESR Group · {fannie_date} Economic Forecast</span></div>
    </div>
  </div>

</main>

<footer>
  <div style="font-size:.54rem;line-height:1.8;color:var(--muted);">
    Auto-updated daily via GitHub Actions &nbsp;·&nbsp;
    OBMMI: Optimal Blue via FRED &nbsp;·&nbsp;
    PMMS: Freddie Mac via FRED &nbsp;·&nbsp;
    Fannie Mae ESR APIs &nbsp;·&nbsp;
    NAR Existing Home Sales via FRED &nbsp;·&nbsp;
    Inman &amp; Calculated Risk RSS &nbsp;·&nbsp;
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
    spread       = fetch_spread()
    news_fortune = fetch_fortune_news()
    news_inman   = fetch_inman_news()
    pending      = fetch_pending()

    html = build_html(rates, pmms, housing, economic, hpsi, news_fortune, news_inman, pending, spread)
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
    print(f"  Pending Index: {pending.get('value')} ({pending.get('date')})")
    print(f"{'='*60}\n")
