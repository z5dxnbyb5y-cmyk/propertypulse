#!/usr/bin/env python3
"""
PropertyPulse / Newzip Market Tracker — scraper
Sources: FRED API, Fannie Mae APIs, Inman RSS, Fortune RSS, HousingWire/MBA RSS
"""
import os, re, json, datetime, gzip, csv, io, urllib.request, urllib.parse

TODAY     = datetime.date.today()
TODAY_STR = TODAY.strftime("%B %d, %Y")
RUN_TS    = datetime.datetime.utcnow().strftime("%b %d, %Y %I:%M %p UTC")

FRED_KEY             = os.environ.get("FRED_API_KEY", "")
FANNIE_CLIENT_ID     = os.environ.get("FANNIE_CLIENT_ID", "")
FANNIE_CLIENT_SECRET = os.environ.get("FANNIE_CLIENT_SECRET", "")
FANNIE_BASE          = "https://api.fanniemae.com"
ANTHROPIC_API_KEY    = os.environ.get("ANTHROPIC_API_KEY", "")

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
_fannie_token_failed = False  # set True after first complete failure; skip retries

def get_fannie_token():
    """Authenticate with Fannie Mae Exchange APIs using AWS Cognito."""
    global _fannie_token, _fannie_token_expiry, _fannie_token_failed
    if _fannie_token_failed:
        return None  # already tried this run — don't retry
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
    _fannie_token_failed = True
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
    if _fannie_token_failed:
        print("Fetching Fannie Mae Housing Indicators... skipped (auth failed earlier, using ESR fallback)")
        return {"mortgage_rate_30y":{},"total_home_sales":None,"sf_starts":None,"report_date":None}
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
    if _fannie_token_failed:
        print("Fetching Fannie Mae Economic Indicators... skipped (auth failed earlier, using ESR fallback)")
        return {"fed_funds":None,"treasury_10y":None,"unemployment":None,"cpi":None,"gdp":None,"report_date":None}
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
    if _fannie_token_failed:
        print("Fetching Fannie Mae HPSI... skipped (auth failed earlier)")
        return None
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
    Fetch housing/mortgage news. Merges MND + HousingWire by date so that
    stale MND weeks get supplemented by HW articles, keeping the panel fresh.
    Sources tried:
      1. Mortgage News Daily RSS (rss/news, rss/full)
      2. HousingWire RSS (merged in, not just a fallback)
    """
    print("Fetching housing/mortgage news (MND + HousingWire merged)...")
    all_articles = []
    seen = set()

    def _parse_items(raw, cdata_titles=False):
        """Parse <item> blocks from RSS raw text. Returns list of dicts with dt key."""
        out = []
        for m in re.finditer(r'<item>(.*?)</item>', raw, re.DOTALL | re.IGNORECASE):
            block = m.group(1)
            if cdata_titles:
                title_m = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', block, re.DOTALL)
            else:
                title_m = re.search(r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', block, re.DOTALL)
            link_m = re.search(r'<link>(.*?)</link>', block, re.DOTALL)
            pub_m  = re.search(r'<pubDate>(.*?)</pubDate>', block, re.DOTALL)
            if not (title_m and link_m): continue
            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
            url   = link_m.group(1).strip()
            pub   = pub_m.group(1).strip() if pub_m else ""
            if not url or len(title) < 10: continue
            try:
                dt = datetime.datetime.strptime(pub[:25], "%a, %d %b %Y %H:%M")
            except:
                try:
                    dt = datetime.datetime.strptime(pub[:16], "%a, %d %b %Y")
                except:
                    dt = datetime.datetime.min
            date_str = dt.strftime("%b %d, %Y") if dt != datetime.datetime.min else pub[:16]
            out.append({"title": title, "url": url, "date": date_str, "desc": "", "dt": dt})
        return out

    # Source 1: Mortgage News Daily
    for feed_url in [
        "https://www.mortgagenewsdaily.com/rss/news",
        "https://www.mortgagenewsdaily.com/rss/full",
    ]:
        raw = fetch(feed_url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (compatible; NewzipBot/1.0)"})
        if not raw: continue
        items = _parse_items(raw, cdata_titles=False)
        for a in items:
            if a["url"] not in seen:
                seen.add(a["url"])
                all_articles.append(a)
        if items:
            print(f"  MND ({feed_url.split('/')[-1]}): {len(items)} items, newest: {items[0]['date'] if items else '?'}")
            break  # got MND articles, no need for second MND endpoint

    # Source 2: HousingWire — always attempt, merge by date
    raw = fetch("https://www.housingwire.com/feed/", timeout=20)
    if raw:
        items = _parse_items(raw, cdata_titles=True)
        added = 0
        for a in items:
            if a["url"] not in seen:
                seen.add(a["url"])
                all_articles.append(a)
                added += 1
        print(f"  HousingWire: {added} new items merged")
    else:
        print("  HousingWire: no response (403 or timeout)")

    # Sort all by date descending, take top 6
    all_articles.sort(key=lambda x: x["dt"], reverse=True)
    articles = [{"title": a["title"], "url": a["url"], "date": a["date"], "desc": a["desc"]}
                for a in all_articles[:6]]

    print(f"  Housing news final: {len(articles)} articles")
    return articles


# ── REDFIN HOUSING MARKET DATA ────────────────────────────────────────────────

def fetch_redfin_market():
    """
    Pull national housing market data from Redfin's public S3 data center.
    URL: redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/
    File: national_market_tracker.tsv000.gz — updated weekly (Wednesdays).
    Free to use with citation to Redfin.
    Key fields: inventory, median_dom, months_of_supply, new_listings,
                median_sale_price, homes_sold, pct_homes_with_price_drops,
                avg_sale_to_list, pending_sales
    """
    print("Fetching Redfin national housing market data...")
    url = "https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/national_market_tracker.tsv000.gz"
    fallback = {
        "period_begin": "2026-02-01", "period_end": "2026-02-28",
        "inventory": 1726907, "inventory_yoy": -0.04,
        "median_dom": 66, "median_dom_yoy": 9,
        "months_of_supply": 4.0, "months_of_supply_yoy": 0.0,
        "new_listings": 472951, "new_listings_yoy": -4.8,
        "median_sale_price": 429189, "median_sale_price_yoy": 0.9,
        "homes_sold": 318107, "homes_sold_yoy": -3.7,
        "pct_price_drops": 16.5, "pct_price_drops_yoy": 1.5,
        "avg_sale_to_list": 98.2, "avg_sale_to_list_yoy": -0.27,
        "pct_sold_above_list": 22.5, "pct_sold_above_list_yoy": -2.2,
        "source": "fallback",
    }
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; NewzipBot/1.0)"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = gzip.decompress(resp.read())
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8")), delimiter="\t")
        rows = list(reader)
        if not rows:
            print("  Redfin: empty file, using fallback")
            return fallback
        # Last row = most recent period
        row = rows[-1]
        def _f(key, divisor=1):
            try: return round(float(row[key]) / divisor, 2)
            except: return None
        result = {
            "period_begin":        row.get("period_begin", ""),
            "period_end":          row.get("period_end", ""),
            "inventory":           _f("inventory"),
            "inventory_yoy":       _f("inventory_yoy") and round(_f("inventory_yoy") * 100, 1),
            "median_dom":          _f("median_dom"),
            "median_dom_yoy":      _f("median_dom_yoy"),
            "months_of_supply":    _f("months_of_supply"),
            "months_of_supply_yoy":_f("months_of_supply_yoy"),
            "new_listings":        _f("new_listings"),
            "new_listings_yoy":    _f("new_listings_yoy") and round(_f("new_listings_yoy") * 100, 1),
            "median_sale_price":   _f("median_sale_price"),
            "median_sale_price_yoy":_f("median_sale_price_yoy") and round(_f("median_sale_price_yoy") * 100, 1),
            "homes_sold":          _f("homes_sold"),
            "homes_sold_yoy":      _f("homes_sold_yoy") and round(_f("homes_sold_yoy") * 100, 1),
            "pct_price_drops":     _f("pct_homes_with_price_drops") and round(_f("pct_homes_with_price_drops") * 100, 1),
            "pct_price_drops_yoy": _f("pct_homes_with_price_drops_yoy") and round(_f("pct_homes_with_price_drops_yoy") * 100, 1),
            "avg_sale_to_list":    _f("avg_sale_to_list") and round(_f("avg_sale_to_list") * 100, 1),
            "pct_sold_above_list": _f("pct_homes_sold_above_list") and round(_f("pct_homes_sold_above_list") * 100, 1),
            "source": "redfin",
        }
        print(f"  Redfin: {result['period_begin']} → {result['period_end']} | inventory {result['inventory']} | DOM {result['median_dom']}d | supply {result['months_of_supply']}mo")
        return result
    except Exception as e:
        print(f"  Redfin: fetch failed ({e}), using Feb 2026 fallback")
        return fallback


def fetch_zillow_market():
    """
    Pull Zillow Home Value Index (ZHVI) — national + all 50 state values.
    File: State_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv
    Returns national dict plus state_data dict keyed by 2-letter abbreviation.
    Updated monthly on the 16th.
    """
    print("Fetching Zillow ZHVI national + state home values...")
    # State-level ZHVI (also contains national row)
    url_state = "https://files.zillowstatic.com/research/public_csvs/zhvi/State_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
    fallback = {
        "zhvi": 359000, "zhvi_mom": 0.3, "zhvi_yoy": 3.2,
        "period": "2026-01", "source": "fallback",
        "state_data": {},
    }

    # State name → abbreviation mapping
    STATE_ABBR = {
        "Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA",
        "Colorado":"CO","Connecticut":"CT","Delaware":"DE","Florida":"FL","Georgia":"GA",
        "Hawaii":"HI","Idaho":"ID","Illinois":"IL","Indiana":"IN","Iowa":"IA",
        "Kansas":"KS","Kentucky":"KY","Louisiana":"LA","Maine":"ME","Maryland":"MD",
        "Massachusetts":"MA","Michigan":"MI","Minnesota":"MN","Mississippi":"MS",
        "Missouri":"MO","Montana":"MT","Nebraska":"NE","Nevada":"NV","New Hampshire":"NH",
        "New Jersey":"NJ","New Mexico":"NM","New York":"NY","North Carolina":"NC",
        "North Dakota":"ND","Ohio":"OH","Oklahoma":"OK","Oregon":"OR","Pennsylvania":"PA",
        "Rhode Island":"RI","South Carolina":"SC","South Dakota":"SD","Tennessee":"TN",
        "Texas":"TX","Utah":"UT","Vermont":"VT","Virginia":"VA","Washington":"WA",
        "West Virginia":"WV","Wisconsin":"WI","Wyoming":"WY","District of Columbia":"DC",
    }

    def _parse_zhvi_row(row, date_cols):
        try:
            v_now  = float(row[date_cols[-1]])
            v_prev = float(row[date_cols[-2]])
            v_yago = float(row[date_cols[-13]])
            mom = round((v_now - v_prev) / v_prev * 100, 2)
            yoy = round((v_now - v_yago) / v_yago * 100, 1)
            return {"zhvi": round(v_now), "zhvi_mom": mom, "zhvi_yoy": yoy, "period": date_cols[-1][:7]}
        except:
            return None

    try:
        req = urllib.request.Request(url_state, headers={"User-Agent": "Mozilla/5.0 (compatible; NewzipBot/1.0)"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(raw))
        rows = list(reader)
        if not rows:
            print("  Zillow: empty CSV, using fallback")
            return fallback

        date_cols = sorted([k for k in rows[0].keys() if re.match(r'\d{4}-\d{2}-\d{2}', k)])
        if len(date_cols) < 13:
            return fallback

        national_data = None
        state_data = {}

        for row in rows:
            name = row.get("RegionName", "").strip()
            parsed = _parse_zhvi_row(row, date_cols)
            if not parsed:
                continue
            if name.lower() == "united states":
                national_data = parsed
            abbr = STATE_ABBR.get(name)
            if abbr:
                state_data[abbr] = {**parsed, "name": name}

        if not national_data:
            # Fall back to metro CSV for national row
            print("  Zillow: no national row in state CSV, trying metro CSV...")
            url_nat = "https://files.zillowstatic.com/research/public_csvs/zhvi/Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
            req2 = urllib.request.Request(url_nat, headers={"User-Agent": "Mozilla/5.0 (compatible; NewzipBot/1.0)"})
            with urllib.request.urlopen(req2, timeout=25) as resp2:
                raw2 = resp2.read().decode("utf-8")
            for row in csv.DictReader(io.StringIO(raw2)):
                if row.get("RegionName", "").lower() == "united states":
                    dcols2 = sorted([k for k in row.keys() if re.match(r'\d{4}-\d{2}-\d{2}', k)])
                    national_data = _parse_zhvi_row(row, dcols2) if len(dcols2) >= 13 else None
                    break

        if not national_data:
            return {**fallback, "state_data": state_data}

        period = national_data["period"]
        print(f"  Zillow ZHVI: ${national_data['zhvi']:,} ({national_data['zhvi_yoy']:+.1f}% YoY) as of {period} · {len(state_data)} states")
        return {**national_data, "source": "zillow", "state_data": state_data}

    except Exception as e:
        print(f"  Zillow: fetch failed ({e}), using fallback")
        return fallback


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


# ── HOUSING MARKET PULSE BUILDER ──────────────────────────────────────────────

def build_housing_pulse_html(redfin, zillow):
    """
    Render the Housing Market Pulse panel from Redfin + Zillow data.
    Returns an HTML string for the pulse-grid div.
    """
    def _yoy_badge(val, invert=False):
        """Return a styled badge for YoY change. invert=True means up is bad (e.g. DOM)."""
        if val is None: return '<span class="hp-badge hp-neu">N/A</span>'
        good = (val < 0) if invert else (val > 0)
        cls  = "hp-good" if good else ("hp-bad" if not good else "hp-neu")
        sign = "+" if val > 0 else ""
        return f'<span class="hp-badge {cls}">{sign}{val:g}% YoY</span>'

    def _dom_badge(val, yoy):
        if val is None: return '<span class="hp-badge hp-neu">N/A</span>'
        good = yoy is not None and yoy < 0
        cls  = "hp-good" if good else "hp-bad"
        sign = "+" if (yoy or 0) > 0 else ""
        suffix = f' ({sign}{yoy:g}d YoY)' if yoy is not None else ""
        return f'<span class="hp-badge {cls}">{int(val)}d{suffix}</span>'

    # Market signal: months of supply determines buyer vs seller
    supply = redfin.get("months_of_supply") or 4.0
    if supply < 3:
        signal_label, signal_cls, signal_desc = "Seller's Market", "hp-signal-hot", "Under 3 months supply — sellers have pricing power"
    elif supply < 5:
        signal_label, signal_cls, signal_desc = "Balanced Market", "hp-signal-balanced", f"{supply:.1f} months supply — roughly balanced conditions"
    else:
        signal_label, signal_cls, signal_desc = "Buyer's Market", "hp-signal-cool", f"{supply:.1f} months supply — buyers have negotiating room"

    inv       = redfin.get("inventory")
    inv_yoy   = redfin.get("inventory_yoy")
    dom       = redfin.get("median_dom")
    dom_yoy   = redfin.get("median_dom_yoy")
    price     = redfin.get("median_sale_price")
    price_yoy = redfin.get("median_sale_price_yoy")
    drops     = redfin.get("pct_price_drops")
    drops_yoy = redfin.get("pct_price_drops_yoy")
    nl        = redfin.get("new_listings")
    nl_yoy    = redfin.get("new_listings_yoy")
    stl       = redfin.get("avg_sale_to_list")
    sold_above= redfin.get("pct_sold_above_list")
    period    = redfin.get("period_end", "")
    try:
        pd_str = datetime.datetime.strptime(period, "%Y-%m-%d").strftime("%b %Y")
    except:
        pd_str = period or "Latest"

    zhvi      = zillow.get("zhvi")
    zhvi_yoy  = zillow.get("zhvi_yoy")
    zhvi_mom  = zillow.get("zhvi_mom")
    zhvi_per  = zillow.get("period", "")

    price_str = f"${price:,.0f}" if price else (f"${zhvi:,.0f} (ZHVI)" if zhvi else "N/A")
    price_yoy_val = price_yoy if price_yoy is not None else zhvi_yoy

    return f"""
    <div class="hp-signal {signal_cls}">
      <div class="hp-signal-label">{signal_label}</div>
      <div class="hp-signal-desc">{signal_desc}</div>
    </div>
    <div class="hp-grid">
      <div class="hp-cell">
        <div class="hp-metric">Median Home Price</div>
        <div class="hp-val">{price_str}</div>
        {_yoy_badge(price_yoy_val)}
      </div>
      <div class="hp-cell">
        <div class="hp-metric">Active Inventory</div>
        <div class="hp-val">{f"{inv:,.0f}" if inv else "N/A"}</div>
        {_yoy_badge(inv_yoy)}
      </div>
      <div class="hp-cell">
        <div class="hp-metric">Median Days on Market</div>
        <div class="hp-val">{int(dom) if dom else "N/A"} days</div>
        {_dom_badge(dom, dom_yoy)}
      </div>
      <div class="hp-cell">
        <div class="hp-metric">Months of Supply</div>
        <div class="hp-val">{supply:.1f} mo</div>
        <div style="font-size:.6rem;color:var(--muted);margin-top:.2rem">&lt;3 seller · 3–5 balanced · 5+ buyer</div>
      </div>
      <div class="hp-cell">
        <div class="hp-metric">New Listings</div>
        <div class="hp-val">{f"{nl:,.0f}" if nl else "N/A"}</div>
        {_yoy_badge(nl_yoy)}
      </div>
      <div class="hp-cell">
        <div class="hp-metric">Homes w/ Price Drops</div>
        <div class="hp-val">{f"{drops:.1f}%" if drops else "N/A"}</div>
        {_yoy_badge(drops_yoy, invert=True) if drops_yoy else '<span class="hp-badge hp-neu">N/A</span>'}
      </div>
      <div class="hp-cell">
        <div class="hp-metric">Sale-to-List Ratio</div>
        <div class="hp-val">{f"{stl:.1f}%" if stl else "N/A"}</div>
        <div style="font-size:.6rem;color:var(--muted);margin-top:.2rem">100% = full price · &gt;100% = bidding wars</div>
      </div>
      <div class="hp-cell">
        <div class="hp-metric">Sold Above List</div>
        <div class="hp-val">{f"{sold_above:.1f}%" if sold_above else "N/A"}</div>
        <div style="font-size:.6rem;color:var(--muted);margin-top:.2rem">Share of homes sold over ask</div>
      </div>
    </div>
    <div class="sb"><div class="sd"></div><span>Redfin Data Center · redfin.com/news/data-center · {pd_str} · Updated weekly Wednesdays · Cite Redfin when sharing</span></div>
"""


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

    TICKER_TIPS = {
        "PMMS 30Y":  f"Freddie Mac Primary Mortgage Market Survey · 30Y fixed · Weekly · As of {pdate}",
        "PMMS 15Y":  f"Freddie Mac PMMS · 15Y fixed · Weekly avg · As of {pdate}",
        "FED RATE":  "Federal Reserve target rate · Currently on hold · Next meeting Apr 28–29, 2026",
        "30Y/10Y":   "Spread between 30Y mortgage & 10Y Treasury · Tracks lender risk premium · Norm ~170bps",
        "HPSI":      "Fannie Mae Home Purchase Sentiment Index · Consumer housing confidence survey",
        "1YR AGO":   f"PMMS 30Y rate one year ago · Year-over-year comparison",
    }
    for r in rates:
        TICKER_TIPS[f"OB {r['lb']}"] = f"Optimal Blue OBMMI · Actual locked rates from ~35% of US transactions · Daily"

    def ti(label, val, cls, chg):
        tip = TICKER_TIPS.get(label, label)
        if label == "FED RATE":
            chg_s = f'<span style="color:#ffd88a">{chg}</span>'
        else:
            chg_s = f'<span class="{cls}">{chg}</span>'
        return (f'<div class="ticker-item" data-tip="{tip}">'
                f'<span class="lb">{label}</span><span>{val}</span>{chg_s}</div>')

    single = "\n    ".join(ti(*i) for i in items)
    return single + "\n    " + single

# ── AI SUMMARY ────────────────────────────────────────────────────────────────

def build_summary(rates, pmms, spread, pending, housing, economic, redfin_market=None, zillow_market=None):
    """
    Call Claude API to generate a 1-minute market briefing from live data.
    Returns an HTML string. Falls back to a static summary if API key missing or call fails.
    """
    key = (ANTHROPIC_API_KEY or "").strip()
    if not key:
        print("  Summary: ANTHROPIC_API_KEY not set, using fallback")
        return _summary_fallback(rates, pmms, spread, pending, redfin_market=redfin_market)

    r30   = pmms.get("rate_30y") or 0
    p30   = pmms.get("prev_30y") or r30
    yago  = pmms.get("yago_30y") or 0
    pdate = pmms.get("date", "N/A")
    bps30 = round((r30 - p30) * 100, 1)
    yoy   = round((r30 - yago) * 100) if yago else 0

    obmmi_30y = next((r for r in rates if "30Y CONV" in r.get("lb", "")), None)
    obmmi_line = ""
    if obmmi_30y:
        obmmi_line = f"OBMMI 30Y Conv locked rate: {obmmi_30y['rate']:.3f}% ({obmmi_30y['bps']:+d}bps day-over-day, as of {obmmi_30y['date']})"

    spread_bps = spread.get("spread_bps") or "N/A"
    spread_sig = spread.get("signal") or "N/A"

    pending_val  = pending.get("value")
    pending_date = pending.get("date", "")
    pending_mom  = pending.get("mom")
    pending_yoy  = pending.get("yoy")
    sales_line = ""
    if pending_val:
        sales_line = f"Existing Home Sales: {pending_val:.2f}M SAAR as of {pending_date}"
        if pending_mom: sales_line += f" (MoM {pending_mom:+.1f}%)"
        if pending_yoy: sales_line += f" (YoY {pending_yoy:+.1f}%)"

    gdp   = economic.get("gdp")
    unemp = economic.get("unemployment")
    cpi   = economic.get("cpi")
    econ_line = f"Fannie Mae ESR: GDP {gdp:.1f}%, UE {unemp:.1f}%, CPI {cpi:.1f}%" if gdp else "Fannie Mae Mar 2026 ESR: GDP ~2.3%, UE ~4.2%, CPI ~2.7%"

    home_sales = housing.get("total_home_sales")
    sf_starts  = housing.get("sf_starts")
    housing_line = ""
    if home_sales: housing_line += f"Fannie Mae forecasts ~{home_sales}M total home sales this year"
    if sf_starts is not None: housing_line += f", SF starts {sf_starts:+.1f}% YoY"

    # Build real estate market context from Redfin/Zillow
    rf = redfin_market or {}
    zl = zillow_market or {}
    supply     = rf.get("months_of_supply") or 4.0
    dom        = rf.get("median_dom")
    dom_yoy    = rf.get("median_dom_yoy")
    inv_yoy    = rf.get("inventory_yoy")
    price_drop = rf.get("pct_price_drops")
    stl        = rf.get("avg_sale_to_list")
    re_price   = rf.get("median_sale_price")
    re_price_yoy = rf.get("median_sale_price_yoy")
    zhvi       = zl.get("zhvi")
    zhvi_yoy   = zl.get("zhvi_yoy")

    if supply < 3:   market_cond = "a seller's market (under 3 months supply)"
    elif supply < 5: market_cond = f"a balanced market ({supply:.1f} months supply)"
    else:            market_cond = f"a buyer's market ({supply:.1f} months supply)"

    re_lines = []
    if supply: re_lines.append(f"Market conditions: {market_cond}")
    if dom and dom_yoy is not None: re_lines.append(f"Median days on market: {int(dom)} days ({dom_yoy:+g}d YoY — homes {'sitting longer' if dom_yoy > 0 else 'moving faster'} than last year)")
    if inv_yoy is not None: re_lines.append(f"Active inventory: {inv_yoy:+g}% YoY ({'more' if inv_yoy > 0 else 'less'} homes available than a year ago)")
    if price_drop: re_lines.append(f"Price drops: {price_drop:.1f}% of homes have had price reductions")
    if stl: re_lines.append(f"Sale-to-list ratio: {stl:.1f}% ({'buyers getting discounts' if stl < 99 else 'homes selling near or above ask'})")
    if re_price and re_price_yoy: re_lines.append(f"Median sale price: ${re_price:,.0f} ({re_price_yoy:+.1f}% YoY)")
    elif zhvi and zhvi_yoy: re_lines.append(f"Zillow Home Value Index: ${zhvi:,.0f} ({zhvi_yoy:+.1f}% YoY)")
    re_context = "\n".join(f"- {l}" for l in re_lines) if re_lines else "- Real estate data unavailable"

    prompt = f"""You are a market strategist writing a daily briefing for loan officers (LOs) at a real estate company.

Your audience is LOs who need to know: what is the market doing, and what should they DO about it today — whether that's a talking point with a client, a reason to call a buyer who's been sitting on the fence, or context for why now is or isn't a good time to act.

Today's data ({TODAY_STR}):

MORTGAGE RATES:
- PMMS 30Y fixed: {r30:.2f}% ({bps30:+.1f}bps week-over-week, {yoy:+d}bps vs one year ago at {yago:.2f}%)
- {obmmi_line}
- 30Y/10Y spread: {spread_bps}bps ({spread_sig}) — norm ~170bps

REAL ESTATE MARKET (Redfin national data):
{re_context}

Write a "1-minute briefing" with exactly these three parts, each on its own line with the label in caps:

THE SIGNAL: The single most actionable thing happening across rates AND the real estate market right now. Lead with what matters most to an LO today — inventory shift, rate trend, buyer opportunity, or seller leverage. Be specific with numbers.

WHAT IT MEANS FOR LOs: One concrete sentence on how an LO should use this. Think: talking point with a hesitant buyer, reason to call a fence-sitter, context for a rate conversation, or market timing angle. Plain language, no jargon.

WATCH FOR: One specific data point or event this week that could shift the picture (data release, Fed commentary, rate level to watch, seasonal pattern).

Be direct. Use the actual numbers. No preamble, no sign-off. Total length: 3 sentences."""

    print("  Summary: calling Claude API...")
    try:
        body = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}]
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["content"][0]["text"].strip()
        print(f"  Summary: got {len(text)} chars")
        return _format_summary_html(text)
    except Exception as e:
        print(f"  Summary: API call failed ({e}), using fallback")
        return _summary_fallback(rates, pmms, spread, pending, redfin_market=redfin_market)


def _format_summary_html(text):
    """Parse Claude's 3-line response into styled HTML."""
    signal = what = watch = ""
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("THE SIGNAL:"):
            signal = line[len("THE SIGNAL:"):].strip()
        elif line.upper().startswith("WHAT IT MEANS FOR LOS:") or line.upper().startswith("WHAT IT MEANS:"):
            what = line.split(":", 1)[1].strip() if ":" in line else line
        elif line.upper().startswith("WATCH FOR:"):
            watch = line[len("WATCH FOR:"):].strip()
    # Fallback: just split into three chunks if labels weren't found
    if not signal:
        parts = [l.strip() for l in text.splitlines() if l.strip()]
        signal = parts[0] if len(parts) > 0 else text
        what   = parts[1] if len(parts) > 1 else ""
        watch  = parts[2] if len(parts) > 2 else ""
    rows = ""
    if signal:
        rows += f'<div class="brief-row"><span class="brief-lbl">The Signal</span><span class="brief-val">{signal}</span></div>'
    if what:
        rows += f'<div class="brief-row"><span class="brief-lbl">What It Means for LOs</span><span class="brief-val">{what}</span></div>'
    if watch:
        rows += f'<div class="brief-row brief-row-last"><span class="brief-lbl">Watch For</span><span class="brief-val">{watch}</span></div>'
    return rows


def _summary_fallback(rates, pmms, spread, pending, redfin_market=None):
    """Static fallback when API unavailable — includes real estate context."""
    r30  = pmms.get("rate_30y") or 0
    p30  = pmms.get("prev_30y") or r30
    yago = pmms.get("yago_30y") or 0
    bps  = round((r30 - p30) * 100, 1)
    yoy  = round((r30 - yago) * 100) if yago else 0
    dir_ = "up" if bps >= 0 else "down"
    sp   = spread.get("spread_bps")
    rf   = redfin_market or {}
    supply = rf.get("months_of_supply")
    dom    = rf.get("median_dom")
    dom_yoy = rf.get("median_dom_yoy")
    inv_yoy = rf.get("inventory_yoy")

    # Build signal from most notable data point
    re_note = ""
    if supply and dom and dom_yoy is not None:
        if supply < 3:
            re_note = f" Seller's market ({supply:.1f}mo supply) — homes moving in {int(dom)}d."
        elif supply >= 5:
            re_note = f" Buyer's market ({supply:.1f}mo supply) — inventory up {inv_yoy:+g}% YoY."
        else:
            re_note = f" Balanced market ({supply:.1f}mo supply), {int(dom)} days on market."

    signal = f"30Y fixed {r30:.2f}% — {abs(bps):.0f}bps {dir_} WoW, {abs(yoy)}bps {'below' if yoy <= 0 else 'above'} last year.{re_note}"
    what   = f"{'Rates are cheaper than a year ago — use the YoY comparison as a buyer talking point.' if yoy < 0 else 'Rates are higher than a year ago — focus conversation on market conditions and negotiating power.'}"
    watch  = "Thursday: Freddie Mac PMMS. Track whether inventory and days-on-market trends continue shifting toward buyers."
    rows = f'<div class="brief-row"><span class="brief-lbl">The Signal</span><span class="brief-val">{signal}</span></div>'
    rows += f'<div class="brief-row"><span class="brief-lbl">What It Means for LOs</span><span class="brief-val">{what}</span></div>'
    rows += f'<div class="brief-row brief-row-last"><span class="brief-lbl">Watch For</span><span class="brief-val">{watch}</span></div>'
    return rows


# ── MAIN HTML ─────────────────────────────────────────────────────────────────

def build_html(rates, pmms, housing, economic, hpsi, news_fortune, news_inman, pending, spread, redfin_market=None, zillow_market=None, state_data=None):
    rates_json     = json.dumps(rates)
    fortune_html   = build_news_items(news_fortune)
    inman_html     = build_news_items(news_inman, show_desc=True)
    pending_html_str = build_pending_html(pending)
    fannie_rows_str = build_fannie_rows(housing)
    summary_html   = build_summary(rates, pmms, spread, pending, housing, economic,
                                       redfin_market=redfin_market, zillow_market=zillow_market)
    redfin_market  = redfin_market or {}
    zillow_market  = zillow_market or {}
    pulse_html     = build_housing_pulse_html(redfin_market, zillow_market)
    map_html       = build_us_map_html(state_data or {})

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
    --nz-teal-bright:#3EB4A5;
    --nz-teal-bright-light:#E8F7F5;
    --nz-yellow:#FAC515;
    --nz-yellow-light:#FEF7DC;
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
  body{{font-family:'Inter',sans-serif;background:var(--paper);color:var(--ink);min-height:100vh;font-size:clamp(13px,1.5vw,15px)}}
  a{{color:inherit;text-decoration:none}}

  /* HEADER + NAV — merged into one sticky bar */
  .topbar{{background:white;border-bottom:2px solid var(--border);padding:0 1.5rem;position:sticky;top:0;z-index:100;box-shadow:0 2px 12px rgba(76,109,225,.08)}}
  .topbar-inner{{max-width:1280px;margin:0 auto;display:grid;grid-template-columns:auto 1fr auto;align-items:stretch;gap:0}}
  .logo-wrap{{display:flex;align-items:center;padding:.75rem 1.5rem .75rem 0;border-right:1px solid var(--border);gap:.75rem}}
  .logo-wrap img{{height:24px;display:block}}
  .header-title{{font-size:.68rem;font-weight:600;color:var(--nz-blue);letter-spacing:.05em;text-transform:uppercase;white-space:nowrap}}
  .nav-inner{{display:flex;align-items:stretch;gap:0;overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none;padding:0 .5rem}}
  .nav-inner::-webkit-scrollbar{{display:none}}
  .nav-link{{font-family:'DM Mono',monospace;font-size:.6rem;font-weight:500;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);padding:0 .9rem;white-space:nowrap;display:flex;align-items:center;border-bottom:3px solid transparent;border-top:3px solid transparent;transition:color .15s,border-color .15s}}
  .nav-link:hover{{color:var(--nz-blue);border-bottom-color:var(--nz-blue)}}
  .nav-re:hover,.nav-pulse:hover,.nav-sales:hover{{color:var(--nz-blue)!important;border-bottom-color:var(--nz-blue)!important}}
  .nav-mort:hover,.nav-obmmi:hover,.nav-pmms:hover,.nav-spread:hover,.nav-forecast:hover{{color:var(--nz-teal-bright)!important;border-bottom-color:var(--nz-teal-bright)!important}}
  .nav-news:hover{{color:#9A7800!important;border-bottom-color:var(--nz-yellow)!important}}
  .topbar-meta{{display:flex;align-items:center;padding:.75rem 0 .75rem 1.5rem;border-left:1px solid var(--border)}}
  .hmeta{{font-family:'DM Mono',monospace;font-size:.52rem;color:var(--muted);text-align:right;line-height:1.7}}

  /* TOOLTIP */
  .tip-wrap{{position:relative;display:inline-flex;align-items:center}}
  .tip-wrap .tip{{display:none;position:absolute;left:50%;bottom:calc(100% + 6px);transform:translateX(-50%);background:var(--ink);color:white;font-family:'DM Mono',monospace;font-size:.56rem;line-height:1.5;padding:.4rem .65rem;border-radius:5px;white-space:nowrap;z-index:200;pointer-events:none}}
  .tip-wrap .tip::after{{content:'';position:absolute;top:100%;left:50%;transform:translateX(-50%);border:5px solid transparent;border-top-color:var(--ink)}}
  .tip-wrap:hover .tip{{display:block}}

  /* chup/chdn still used elsewhere */
  .chup{{color:var(--nz-teal)}}.chdn{{color:var(--nz-red)}}

  main{{max-width:1280px;margin:0 auto;padding:clamp(1rem,3vw,1.75rem) clamp(.75rem,2vw,1.5rem)}}
  .section-hd{{display:flex;align-items:center;gap:1rem;margin:2.5rem 0 1.25rem;padding:.9rem 1.25rem;border-radius:8px;border-left:4px solid var(--nz-blue);background:var(--nz-blue-light)}}
  .section-hd-label{{font-family:'Inter',sans-serif;font-size:clamp(.75rem,1.2vw,.85rem);font-weight:700;color:var(--nz-blue);letter-spacing:.01em}}
  .section-hd-blue{{border-left-color:var(--nz-blue);background:var(--nz-blue-light)}}
  .section-hd-blue .section-hd-label{{color:var(--nz-blue)}}
  .section-hd-teal{{border-left-color:var(--nz-teal-bright);background:var(--nz-teal-bright-light)}}
  .section-hd-teal .section-hd-label{{color:var(--nz-teal-bright)}}
  .section-hd-yellow{{border-left-color:var(--nz-yellow);background:var(--nz-yellow-light)}}
  .section-hd-yellow .section-hd-label{{color:#9A7800}}
  .slbl{{font-family:'DM Mono',monospace;font-size:clamp(.52rem,.8vw,.6rem);letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:.65rem;display:flex;align-items:center;gap:.5rem}}
  .slbl::after{{content:'';flex:1;height:1px;background:var(--border)}}
  .slbl-blue{{color:var(--nz-blue)}}.slbl-blue::before{{content:'';width:6px;height:6px;border-radius:50%;background:var(--nz-blue);flex-shrink:0}}
  .slbl-teal{{color:var(--nz-teal-bright)}}.slbl-teal::before{{content:'';width:6px;height:6px;border-radius:50%;background:var(--nz-teal-bright);flex-shrink:0}}
  .slbl-yellow{{color:#9A7800}}.slbl-yellow::before{{content:'';width:6px;height:6px;border-radius:50%;background:var(--nz-yellow);flex-shrink:0}}
  .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-bottom:2rem}}
  .three-col{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1.5rem;margin-bottom:2rem}}
  @media(max-width:860px){{.two-col,.three-col{{grid-template-columns:1fr}}}}
  @media(max-width:480px){{.two-col{{gap:1rem}}}}

  /* ALERT BANNER */
  .fed-note{{background:var(--nz-blue);color:white;padding:1rem 1.5rem;margin-bottom:2rem;border-radius:8px;display:flex;gap:1.25rem;align-items:flex-start}}
  .fed-icon{{font-size:1.5rem;flex-shrink:0;opacity:.85}}
  .fed-note h4{{font-family:'DM Mono',monospace;font-size:.58rem;letter-spacing:.1em;text-transform:uppercase;color:rgba(255,255,255,.7);margin-bottom:.3rem}}
  .fed-note p{{font-size:.75rem;line-height:1.65;color:rgba(255,255,255,.9)}}.fed-note strong{{color:white}}

  /* 1-MIN BRIEFING */
  .brief-card{{background:linear-gradient(135deg,#4C6DE1 0%,#005E53 100%);border-radius:14px;margin-bottom:2rem;overflow:hidden;box-shadow:0 6px 32px rgba(76,109,225,.28);max-width:900px;margin-left:auto;margin-right:auto}}
  .brief-head{{padding:1rem 2rem .75rem;display:flex;align-items:center;gap:.75rem;border-bottom:1px solid rgba(255,255,255,.12)}}
  .brief-head-label{{font-family:'Inter',sans-serif;font-size:.65rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:rgba(255,255,255,.6)}}
  .brief-head-sub{{font-family:'DM Mono',monospace;font-size:.52rem;color:rgba(255,255,255,.35);margin-left:auto}}
  .brief-pulse{{width:7px;height:7px;border-radius:50%;background:rgba(255,255,255,.85);flex-shrink:0;animation:pulse 2s ease-in-out infinite}}
  @keyframes pulse{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.3;transform:scale(.8)}}}}
  .brief-body{{padding:.5rem 0 1rem}}
  .brief-row{{display:grid;grid-template-columns:200px 1fr;gap:1.75rem;padding:1.1rem 2rem;border-bottom:1px solid rgba(255,255,255,.08);align-items:baseline}}
  .brief-row-last{{border-bottom:none}}
  .brief-lbl{{font-family:'Inter',sans-serif;font-size:.95rem;font-weight:700;letter-spacing:.01em;text-transform:uppercase;color:white;line-height:1.4}}
  .brief-val{{font-family:'Inter',sans-serif;font-size:.95rem;font-weight:400;line-height:1.65;color:rgba(255,255,255,.85)}}
  .brief-row:first-child .brief-val{{font-weight:400;color:rgba(255,255,255,.85)}}

  /* HOUSING PULSE */
  .hp-signal{{border-radius:8px;padding:.85rem 1.25rem;margin:.75rem 1.25rem;}}
  .hp-signal-hot{{background:#FDF3E7;border-left:4px solid var(--gold)}}
  .hp-signal-balanced{{background:var(--nz-teal-light);border-left:4px solid var(--nz-teal)}}
  .hp-signal-cool{{background:var(--nz-blue-light);border-left:4px solid var(--nz-blue)}}
  .hp-signal-label{{font-family:'DM Mono',monospace;font-size:.62rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin-bottom:.2rem}}
  .hp-signal-hot .hp-signal-label{{color:var(--gold)}}
  .hp-signal-balanced .hp-signal-label{{color:var(--nz-teal)}}
  .hp-signal-cool .hp-signal-label{{color:var(--nz-blue)}}
  .hp-signal-desc{{font-size:.72rem;color:var(--ink);line-height:1.5}}
  .hp-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--border);margin:0 0 0 0}}
  @media(max-width:800px){{.hp-grid{{grid-template-columns:repeat(2,1fr)}}}}
  @media(max-width:400px){{.hp-grid{{grid-template-columns:1fr}}}}
  .hp-cell{{background:white;padding:.85rem 1.25rem}}
  .hp-metric{{font-family:'DM Mono',monospace;font-size:.52rem;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:.3rem}}
  .hp-val{{font-size:clamp(.9rem,1.5vw,1.05rem);font-weight:700;color:var(--ink);line-height:1.2;margin-bottom:.3rem}}
  .hp-badge{{font-family:'DM Mono',monospace;font-size:.54rem;padding:.15rem .45rem;border-radius:4px;font-weight:500}}
  .hp-good{{background:var(--nz-teal-light);color:var(--nz-teal)}}
  .hp-bad{{background:var(--nz-red-light);color:var(--nz-red)}}
  .hp-neu{{background:var(--paper2);color:var(--muted)}}

  /* STAT TILES */
  .stat-tiles{{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:2rem}}
  @media(max-width:900px){{.stat-tiles{{grid-template-columns:repeat(2,1fr)}}}}
  @media(max-width:480px){{.stat-tiles{{grid-template-columns:1fr}}}}
  .stat-tile{{background:white;border:1px solid var(--border);border-radius:8px;padding:1.1rem 1.25rem;position:relative;overflow:hidden}}
  .stat-tile::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--nz-teal-bright)}}
  .st-label{{font-family:'DM Mono',monospace;font-size:.55rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:.35rem}}
  .st-val{{font-size:clamp(1.4rem,2.5vw,1.9rem);font-weight:700;line-height:1;margin-bottom:.2rem;color:var(--ink)}}
  .st-sub{{font-family:'DM Mono',monospace;font-size:.55rem;color:var(--muted)}}
  .st-chg{{font-family:'DM Mono',monospace;font-size:.6rem;margin-top:.25rem}}
  .st-chg.neg{{color:var(--nz-red)}}.st-chg.pos{{color:var(--nz-teal)}}

  /* RATE CARDS */
  .rate-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:1rem;margin-bottom:2rem}}
  @media(min-width:600px){{.rate-grid{{grid-template-columns:repeat(3,1fr)}}}}
  @media(min-width:1000px){{.rate-grid{{grid-template-columns:repeat(6,1fr)}}}}
  .rate-card{{background:white;border:1px solid var(--border);border-radius:8px;padding:1rem 1.1rem;position:relative;overflow:hidden;transition:box-shadow .2s}}
  .rate-card:hover{{box-shadow:0 4px 16px rgba(76,109,225,.12)}}
  .rate-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--nz-teal)}}
  .rc-label{{font-family:'DM Mono',monospace;font-size:.52rem;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin-bottom:.3rem}}
  .rc-value{{font-size:clamp(1.2rem,2vw,1.65rem);font-weight:700;line-height:1;margin-bottom:.2rem;color:var(--ink)}}
  .rc-chg{{font-family:'DM Mono',monospace;font-size:.58rem}}.rc-chg.up{{color:var(--nz-red)}}.rc-chg.dn{{color:var(--nz-teal)}}
  .rc-prev{{font-family:'DM Mono',monospace;font-size:.52rem;color:var(--muted);margin-top:.15rem}}

  /* PANELS */
  .panel{{background:white;border:1px solid var(--border);border-radius:8px;overflow:hidden;position:relative}}
  .panel::before{{content:'';display:block;height:4px;background:var(--nz-blue)}}
  .panel-teal::before{{background:var(--nz-teal-bright)}}
  .panel-yellow::before{{background:var(--nz-yellow)}}
  .panel-blue::before{{background:var(--nz-blue)}}
  .ph{{padding:.85rem 1.25rem;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;background:var(--nz-blue-light)}}
  .panel-teal .ph{{background:var(--nz-teal-bright-light)}}
  .panel-yellow .ph{{background:var(--nz-yellow-light)}}
  .ph h3{{font-size:clamp(.8rem,1.1vw,.9rem);font-weight:600;color:var(--ink)}}
  .badge{{font-family:'DM Mono',monospace;font-size:.52rem;padding:.15rem .5rem;text-transform:uppercase;letter-spacing:.06em;border-radius:4px;font-weight:500}}
  .badge-blue{{background:rgba(76,109,225,.15);color:var(--nz-blue)}}
  .badge-teal{{background:rgba(62,180,165,.15);color:var(--nz-teal)}}
  .badge-gold{{background:#FDF3E3;color:var(--gold)}}
  .badge-red{{background:var(--nz-red-light);color:var(--nz-red)}}
  .sb{{display:flex;align-items:center;gap:.4rem;padding:.5rem 1.25rem;background:var(--paper);border-top:1px solid var(--border);font-family:'DM Mono',monospace;font-size:.54rem;color:var(--muted)}}
  .sd{{width:5px;height:5px;border-radius:50%;background:var(--nz-teal);flex-shrink:0}}

  /* TABLES */
  .tbl-wrap{{background:white;border:1px solid var(--border);border-radius:8px;margin-bottom:2rem;overflow:hidden;position:relative}}
  .tbl-wrap::before{{content:'';display:block;height:4px;background:var(--nz-blue)}}
  .tbl-wrap-teal::before{{background:var(--nz-teal-bright)}}
  .tbl-wrap .ph{{background:var(--nz-blue-light)}}
  .tbl-wrap-teal .ph{{background:var(--nz-teal-bright-light)}}
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
  .pmms-val{{font-size:clamp(1rem,2vw,1.3rem);font-weight:700;line-height:1;color:var(--ink)}}
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
  .ec-val{{font-size:clamp(1.1rem,2vw,1.4rem);font-weight:700;color:var(--ink);line-height:1;margin-bottom:.15rem}}
  .ec-sub{{font-family:'DM Mono',monospace;font-size:.5rem;color:var(--muted)}}

  footer{{max-width:1280px;margin:0 auto;padding:1.5rem;font-family:'DM Mono',monospace;font-size:.54rem;color:var(--muted);border-top:1px solid var(--border);line-height:1.8;display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap}}
  .footer-logo img{{height:18px;opacity:.5}}
</style>
</head>
<body id="top">

<div class="topbar">
  <div class="topbar-inner">
    <div class="logo-wrap">
      <a href="#top" style="display:flex;align-items:center;gap:.75rem;text-decoration:none;">
        <img src="{{LOGO_SRC}}" alt="Newzip">
        <div class="header-title">Market Tracker</div>
      </a>
    </div>
    <nav class="nav-inner">
      <a class="nav-link nav-re" href="#real-estate">RE Market</a>
      <a class="nav-link nav-pulse" href="#housing-pulse">Housing Pulse</a>
      <a class="nav-link nav-sales" href="#home-sales">Home Sales</a>
      <a class="nav-link nav-mort" href="#mortgage-insights">Mortgage</a>
      <a class="nav-link nav-obmmi" href="#rates">OBMMI</a>
      <a class="nav-link nav-pmms" href="#pmms">PMMS</a>
      <a class="nav-link nav-spread" href="#spread">Spread</a>
      <a class="nav-link nav-forecast" href="#forecast">Forecast</a>
      <a class="nav-link nav-news" href="#industry-news">News</a>
    </nav>
    <div class="topbar-meta">
      <div class="hmeta">
        <div>{TODAY_STR} · Auto-updated daily</div>
        <div>Last run: {RUN_TS}</div>
      </div>
    </div>
  </div>
</div>

<main>

  <!-- ── FED NOTE ─────────────────────────────────────────────────────── -->
  <div class="fed-note">
    <div class="fed-icon">🏦</div>
    <div>
      <h4>Federal Reserve — Rate Held at 3.50–3.75% · Next Meeting April 28–29, 2026</h4>
      <p>PMMS 30Y at <strong>{r30:.2f}%</strong> as of {pdate} — <strong>{abs(yoy):.0f}bps</strong> {"below" if yoy<=0 else "above"} a year ago ({yago:.2f}%). 10-Year Treasury forecast: <strong>{treasury10y}</strong>. Fannie Mae ESR report: <strong>{fannie_date}</strong>. OBMMI data as of <strong>{obmmi_date}</strong>.</p>
    </div>
  </div>

  <!-- ── 1-MINUTE BRIEFING ──────────────────────────────────────────────── -->
  <div class="brief-card">
    <div class="brief-head">
      <div class="brief-pulse"></div>
      <div class="brief-head-label">1-Minute Briefing</div>
      <div class="brief-head-sub">AI · {RUN_TS}</div>
    </div>
    <div class="brief-body">
      {summary_html}
    </div>
  </div>

  <!-- ── STATE MAP ──────────────────────────────────────────────────────────── -->
  {map_html}

  <!-- ══════════════════════════════════════════════════════════════════════
       SECTION 1 — REAL ESTATE MARKET TRENDS
       Redfin/Zillow pulse · Existing Sales · Housing Outlook · Econ · Risk
  ═══════════════════════════════════════════════════════════════════════ -->
  <div class="section-hd section-hd-blue" id="real-estate">
    <span class="section-hd-label">Real Estate Market Trends</span>
  </div>

  <div class="slbl slbl-blue" id="housing-pulse">Housing Market Pulse · Redfin &amp; Zillow Data</div>
  <div class="panel panel-blue" style="margin-bottom:2rem;overflow:hidden;padding:0;">
    <div class="ph"><h3>National Housing Market Conditions</h3><span class="badge badge-teal">Redfin · Zillow</span></div>
    {pulse_html}
  </div>

  <div class="two-col">
    <div>
      <div class="slbl slbl-blue" id="home-sales">Existing Home Sales · NAR via FRED</div>
      <div class="panel panel-blue">
        <div class="ph"><h3>Existing Home Sales</h3><span class="badge badge-teal">FRED · NAR</span></div>
        {pending_html_str}
        <div class="sb"><div class="sd"></div><span>NAR Existing Home Sales via FRED · Series EXHOSLUSM495S · Millions SAAR · Released monthly</span></div>
      </div>
    </div>
    <div>
      <div class="slbl slbl-blue" id="outlook">Fannie Mae ESR · Housing &amp; Economic Outlook · {fannie_date}</div>
      <div class="panel panel-blue" style="height:100%;box-sizing:border-box;">
        <div class="ph"><h3>Housing Market Outlook</h3><span class="badge badge-gold">Fannie Mae ESR</span></div>
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
        <div class="sb"><div class="sd"></div><span>Fannie Mae ESR APIs · {fannie_date}</span></div>
      </div>
    </div>
  </div>

  <div class="slbl slbl-blue">Market Risk Factors · Fannie Mae ESR · {fannie_date}</div>
  <div class="panel panel-blue" style="margin-bottom:2rem;">
    <div class="ph"><h3>Market Risk Factors</h3><span class="badge badge-gold">Fannie Mae ESR</span></div>
    <div style="padding:1rem 1.5rem;display:grid;grid-template-columns:1fr 1fr;gap:.5rem 2rem;">
      <div style="font-size:.73rem;line-height:1.75;color:var(--muted);"><span style="color:var(--nz-red);font-weight:700;">↑ Risk:</span> Slower GDP growth forecast — weaker economy supports lower rates but signals demand risk</div>
      <div style="font-size:.73rem;line-height:1.75;color:var(--muted);"><span style="color:var(--nz-red);font-weight:700;">↑ Risk:</span> Limited inventory despite lower rates — prices stay elevated, affordability constrained</div>
      <div style="font-size:.73rem;line-height:1.75;color:var(--muted);"><span style="color:var(--nz-red);font-weight:700;">↑ Risk:</span> Geopolitical events pushing oil &amp; Treasury yields higher near-term</div>
      <div style="font-size:.73rem;line-height:1.75;color:var(--muted);"><span style="color:var(--nz-red);font-weight:700;">↑ Risk:</span> Single-family starts forecast −6.2% YoY — supply constraints persist</div>
      <div style="font-size:.73rem;line-height:1.75;color:var(--muted);"><span style="color:var(--nz-teal);font-weight:700;">↓ Positive:</span> Rates ~45bps below year-ago — spring 2026 buyers better positioned than 2025</div>
    </div>
    <div class="sb"><div class="sd"></div><span>Fannie Mae ESR Group · {fannie_date} Economic Forecast</span></div>
  </div>

  <!-- ══════════════════════════════════════════════════════════════════════
       SECTION 2 — MORTGAGE & MARKET INSIGHTS
       Key Indicators · OBMMI · PMMS · Fannie Forecast · Spread
  ═══════════════════════════════════════════════════════════════════════ -->
  <div class="section-hd section-hd-teal" id="mortgage-insights">
    <span class="section-hd-label">Mortgage &amp; Market Insights</span>
  </div>

  <div class="slbl slbl-teal">Key Indicators · {TODAY_STR}</div>
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

  <div class="slbl slbl-teal" id="rates">OBMMI Daily Rate Locks · Optimal Blue via FRED API · {obmmi_date}</div>
  <div class="rate-grid" id="rate-grid"></div>

  <div class="slbl slbl-teal">Full OBMMI Rate Comparison · {obmmi_date}</div>
  <div class="tbl-wrap tbl-wrap-teal">
    <div class="ph"><h3>Optimal Blue Mortgage Market Indices (OBMMI)</h3><span class="badge badge-blue">FRED API · OBMMI</span></div>
    <table>
      <thead><tr><th>Loan Type</th><th>Current Rate</th><th>Prior Period</th><th>Change (bps)</th><th>Trend</th></tr></thead>
      <tbody id="rate-tbody"></tbody>
    </table>
    <div class="sb"><div class="sd"></div><span>Optimal Blue OBMMI via FRED API · Actual locked rates from ~35% of US mortgage transactions · Updated nightly</span></div>
  </div>

  <div class="slbl slbl-teal" id="pmms">Freddie Mac PMMS · Via FRED API</div>
  <div class="panel panel-teal" style="margin-bottom:2rem;">
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
      <div class="slbl slbl-teal" id="forecast">Fannie Mae ESR Forecast · {fannie_date} · Live via API</div>
      <div class="tbl-wrap tbl-wrap-teal" style="margin-bottom:0;">
        <div class="ph"><h3>30-Year Fixed Rate Forecast</h3><span class="badge badge-gold">Fannie Mae API</span></div>
        <table class="ftable">
          <thead><tr><th>Period</th><th>Forecast</th><th>Source</th><th>Signal</th></tr></thead>
          <tbody>{fannie_rows_str}</tbody>
        </table>
        <div class="sb"><div class="sd"></div><span>Fannie Mae Housing Indicators API · Est. values from Mar 2026 ESR when API unavailable · Auto-updated monthly</span></div>
      </div>
    </div>
    <div>
      <div class="slbl slbl-teal" id="spread">30-Year Mortgage vs 10-Year Treasury Spread · Via FRED</div>
      <div class="panel panel-teal" style="margin-bottom:0;">
        <div class="ph"><h3>30Y Mortgage / 10Y Treasury Spread</h3><span class="badge badge-blue">FRED API</span></div>
        <div class="pmms-strip" style="flex-wrap:wrap;">
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
        <div class="sb"><div class="sd"></div><span>FRED API · MORTGAGE30US (weekly) minus DGS10 (daily) · Spread tracks lender risk premium · Updated daily</span></div>
      </div>
    </div>
  </div>

  <!-- ══════════════════════════════════════════════════════════════════════
       SECTION 3 — INDUSTRY NEWS
  ═══════════════════════════════════════════════════════════════════════ -->
  <div class="section-hd section-hd-yellow" id="industry-news">
    <span class="section-hd-label">Industry News</span>
  </div>

  <div class="two-col">
    <div>
      <div class="slbl slbl-yellow">Inman Real Estate News</div>
      <div class="panel panel-yellow">
        <div class="ph"><h3>Inman Real Estate News</h3><span class="badge badge-blue">Inman</span></div>
        {inman_html}
        <div class="sb"><div class="sd"></div><span>feeds.feedburner.com/inmannews · Auto-refreshed daily</span></div>
      </div>
    </div>
    <div>
      <div class="slbl slbl-yellow" id="housing-news">Housing Market News · Mortgage News Daily</div>
      <div class="panel panel-yellow">
        <div class="ph"><h3>Housing Market News</h3><span class="badge badge-blue">Mortgage News Daily</span></div>
        {fortune_html}
        <div class="sb"><div class="sd"></div><span>mortgagenewsdaily.com · Mortgage &amp; housing industry news · Auto-refreshed daily</span></div>
      </div>
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
    Redfin &amp; Zillow Housing Market Data &nbsp;·&nbsp;
    Inman &amp; Mortgage News Daily RSS &nbsp;·&nbsp;
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
  var tipText = (u ? '\u25b2 Rate up ' : '\u25bc Rate down ') + Math.abs(r.bps) + 'bps<br>vs prior business day lock rate<br>Source: Optimal Blue OBMMI \u00b7 FRED';
  return '<div class="rate-card">'
    + '<div class="rc-label">' + r.lb + '</div>'
    + '<div class="rc-value">' + r.rate.toFixed(3) + '%</div>'
    + '<div class="tip-wrap"><div class="rc-chg ' + dir + '">' + arrow + ' ' + Math.abs(r.bps) + 'bps</div><div class="tip">' + tipText + '</div></div>'
    + '<div class="rc-prev">Prev: ' + r.prev.toFixed(3) + '%</div>'
    + '</div>';
}}
function renderRow(r) {{
  var u = r.bps >= 0;
  var bp = Math.min(100, Math.round(Math.abs(r.bps)/25*100));
  var dir = u ? 'up' : 'dn';
  var arrow = u ? '\u25b2' : '\u25bc';
  var col = u ? 'var(--nz-red)' : 'var(--nz-teal)';
  var intensity = Math.abs(r.bps) <= 5 ? 'Minimal move' : Math.abs(r.bps) <= 15 ? 'Moderate move' : 'Large move';
  var tipText = (u ? '\u25b2 Rate up ' : '\u25bc Rate down ') + Math.abs(r.bps) + 'bps vs prior lock day \u00b7 ' + intensity + '<br>Bar fills fully at 25bps+ \u00b7 Source: Optimal Blue OBMMI \u00b7 FRED';
  return '<tr>'
    + '<td class="td-type">' + r.type + '</td>'
    + '<td class="td-rate">' + r.rate.toFixed(3) + '%</td>'
    + '<td class="td-prev">' + r.prev.toFixed(3) + '%</td>'
    + '<td class="td-bps ' + dir + '">' + arrow + ' ' + Math.abs(r.bps) + '</td>'
    + '<td><div class="tip-wrap"><div class="bar-wrap"><div class="bar-fill" style="width:' + bp + '%;background:' + col + '"></div></div><div class="tip">' + tipText + '</div></div></td>'
    + '</tr>';
}}
document.getElementById('rate-grid').innerHTML = RATES.map(renderCard).join('');
document.getElementById('rate-tbody').innerHTML = RATES.map(renderRow).join('');

</script>
</body>
</html>"""

# ── US SVG MAP ────────────────────────────────────────────────────────────────

def build_us_map_html(state_data):
    """
    Build a compact clickable SVG map of the US for the national page.
    States with ZHVI data are colored by YoY change; clicking navigates to state page.
    """
    # State paths use a simplified Albers USA projection layout
    # Each state: (abbr, cx, cy) for label placement, path is simplified
    STATE_POSITIONS = {
        "AL":(520,310),"AK":(140,390),"AZ":(200,290),"AR":(490,290),"CA":(120,240),
        "CO":(280,240),"CT":(680,165),"DE":(665,200),"FL":(570,360),"GA":(555,310),
        "HI":(240,410),"ID":(195,165),"IL":(510,215),"IN":(535,210),"IA":(465,195),
        "KS":(400,255),"KY":(545,245),"LA":(490,335),"ME":(700,135),"MD":(650,210),
        "MA":(690,160),"MI":(540,175),"MN":(455,155),"MS":(510,320),"MO":(480,245),
        "MT":(245,140),"NE":(390,215),"NV":(165,225),"NH":(688,148),"NJ":(668,190),
        "NM":(265,295),"NY":(645,165),"NC":(590,270),"ND":(385,140),"OH":(565,205),
        "OK":(415,290),"OR":(145,170),"PA":(625,190),"RI":(693,168),"SC":(575,300),
        "SD":(390,170),"TN":(530,275),"TX":(390,340),"UT":(220,240),"VT":(672,143),
        "VA":(615,235),"WA":(160,135),"WV":(590,220),"WI":(500,170),"WY":(265,195),
        "DC":(648,218),
    }

    def _color(yoy):
        if yoy is None: return "#D1D5DB"
        if yoy >= 6:    return "#005E53"
        if yoy >= 4:    return "#3EB4A5"
        if yoy >= 2:    return "#A7D9D4"
        if yoy >= 0:    return "#D4EAE8"
        if yoy >= -2:   return "#FAE8E8"
        return "#D64045"

    # Build state circles + labels
    circles = []
    for abbr, (cx, cy) in STATE_POSITIONS.items():
        sd = state_data.get(abbr, {})
        zhvi = sd.get("zhvi")
        yoy  = sd.get("zhvi_yoy")
        color = _color(yoy)
        has_data = zhvi is not None
        href = f"states/{abbr}.html" if has_data else "#"
        cursor = "pointer" if has_data else "default"
        tip = f"{abbr}: ${zhvi:,} ({yoy:+.1f}% YoY)" if has_data else abbr
        circles.append(
            f'<a href="{href}" title="{tip}">'
            f'<circle cx="{cx}" cy="{cy}" r="14" fill="{color}" stroke="white" stroke-width="1.5" '
            f'style="cursor:{cursor}" class="state-dot"/>'
            f'<text x="{cx}" y="{cy+4}" text-anchor="middle" '
            f'font-family="DM Mono,monospace" font-size="7" font-weight="600" fill="{"white" if yoy is not None and (yoy >= 2 or yoy < -2) else "#374151"}" '
            f'style="pointer-events:none">{abbr}</text>'
            f'</a>'
        )

    # Legend
    legend_items = [
        ("#005E53","≥6% YoY"),("#3EB4A5","4–6%"),("#A7D9D4","2–4%"),
        ("#D4EAE8","0–2%"),("#FAE8E8","0 to −2%"),("#D64045","<−2%"),("#D1D5DB","No data"),
    ]
    legend_els = []
    for i,(col,lbl) in enumerate(legend_items):
        lx = 50 + i*95
        legend_els.append(
            f'<rect x="{lx}" y="445" width="12" height="12" rx="2" fill="{col}" stroke="white" stroke-width="0.5"/>'
            f'<text x="{lx+16}" y="455" font-family="DM Mono,monospace" font-size="8" fill="#6B7280">{lbl}</text>'
        )

    return f"""
<div class="panel" style="margin-bottom:2rem;overflow:hidden;padding:0;" id="state-map">
  <div class="ph" style="background:linear-gradient(135deg,#EEF1FC,#E8F7F5);">
    <div>
      <h3 style="color:#1a1a2e;">Explore by State</h3>
      <div style="font-family:'DM Mono',monospace;font-size:.55rem;color:#6B7280;margin-top:.2rem;">Click any state to view local market data · Zillow ZHVI YoY change</div>
    </div>
    <span class="badge badge-blue">Zillow ZHVI</span>
  </div>
  <div style="background:white;padding:1rem 1.5rem;">
    <svg viewBox="0 50 760 430" xmlns="http://www.w3.org/2000/svg"
         style="width:100%;max-width:760px;display:block;margin:0 auto;">
      {''.join(circles)}
      {''.join(legend_els)}
    </svg>
  </div>
  <div class="sb"><div class="sd" style="background:#4C6DE1;"></div><span>Zillow ZHVI · State-level home values · Click a state to view detailed local data</span></div>
</div>"""


# ── STATE PAGE BUILDER ────────────────────────────────────────────────────────

def build_state_page(abbr, state_zhvi, pmms, rates, spread):
    """Generate a standalone state page HTML for states/{abbr}.html"""
    name      = state_zhvi.get("name", abbr)
    zhvi      = state_zhvi.get("zhvi")
    zhvi_yoy  = state_zhvi.get("zhvi_yoy")
    zhvi_mom  = state_zhvi.get("zhvi_mom")
    period    = state_zhvi.get("period", "")
    r30       = pmms.get("rate_30y") or 0
    pdate     = pmms.get("date", "N/A")
    yago      = pmms.get("yago_30y") or 0
    yoy_bps   = round((r30 - yago) * 100) if yago else 0
    spread_bps = spread.get("spread_bps", "N/A")

    zhvi_fmt     = f"${zhvi:,}" if zhvi else "N/A"
    yoy_str      = f"{zhvi_yoy:+.1f}% YoY" if zhvi_yoy is not None else ""
    mom_str      = f"{zhvi_mom:+.2f}% MoM" if zhvi_mom is not None else ""
    yoy_col      = "#3EB4A5" if (zhvi_yoy or 0) >= 0 else "#D64045"
    period_label = ""
    try:
        period_label = datetime.datetime.strptime(period + "-01", "%Y-%m-%d").strftime("%B %Y")
    except:
        period_label = period

    # Try to format period nicely
    try:
        period_label = datetime.datetime.strptime(period, "%Y-%m").strftime("%B %Y")
    except:
        pass

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} Housing Market · Newzip Market Tracker</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root{{
    --nz-blue:#4C6DE1;--nz-blue-light:#EEF1FC;
    --nz-teal:#005E53;--nz-teal-light:#E6F2F0;
    --nz-teal-bright:#3EB4A5;--nz-teal-bright-light:#E8F7F5;
    --nz-yellow:#FAC515;--nz-yellow-light:#FEF7DC;
    --ink:#1a1a2e;--paper:#F8F9FC;--paper2:#EFF1F8;
    --border:#E2E5F0;--muted:#6B7280;--card:#FFFFFF;
    --nz-red:#D64045;--nz-red-light:#FDF0F0;--gold:#D4943A;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Inter',sans-serif;background:var(--paper);color:var(--ink);font-size:clamp(13px,1.5vw,15px)}}
  a{{color:inherit;text-decoration:none}}
  .topbar{{background:white;border-bottom:2px solid var(--border);padding:0 1.5rem;position:sticky;top:0;z-index:100;box-shadow:0 2px 12px rgba(76,109,225,.08)}}
  .topbar-inner{{max-width:1280px;margin:0 auto;display:flex;align-items:center;gap:1rem;padding:.75rem 0}}
  .logo-wrap{{display:flex;align-items:center;gap:.75rem;text-decoration:none}}
  .logo-wrap img{{height:22px}}
  .header-title{{font-size:clamp(.6rem,.8vw,.72rem);font-weight:600;color:var(--nz-blue);letter-spacing:.05em;text-transform:uppercase}}
  .back-link{{font-family:'DM Mono',monospace;font-size:clamp(.55rem,.7vw,.62rem);color:var(--muted);padding:.3rem .7rem;border:1px solid var(--border);border-radius:5px;margin-left:auto;transition:color .15s,border-color .15s}}
  .back-link:hover{{color:var(--nz-blue);border-color:var(--nz-blue)}}
  main{{max-width:1280px;margin:0 auto;padding:clamp(1rem,3vw,1.75rem) clamp(.75rem,2vw,1.5rem)}}
  .state-hero{{background:linear-gradient(135deg,#4C6DE1 0%,#005E53 100%);border-radius:14px;padding:clamp(1.25rem,3vw,2rem);margin-bottom:2rem;color:white}}
  .state-name{{font-size:clamp(1.4rem,4vw,2.5rem);font-weight:700;margin-bottom:.25rem}}
  .state-sub{{font-family:'DM Mono',monospace;font-size:clamp(.55rem,.8vw,.65rem);opacity:.7;margin-bottom:1.25rem}}
  .hero-stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem}}
  .hero-stat-val{{font-size:clamp(1.3rem,3vw,2rem);font-weight:700;line-height:1}}
  .hero-stat-lbl{{font-family:'DM Mono',monospace;font-size:clamp(.48rem,.6vw,.55rem);opacity:.6;text-transform:uppercase;letter-spacing:.08em;margin-top:.2rem}}
  .hero-stat-chg{{font-family:'DM Mono',monospace;font-size:clamp(.55rem,.7vw,.62rem);margin-top:.3rem;opacity:.85}}
  .section-hd{{display:flex;align-items:center;gap:1rem;margin:2rem 0 1.25rem;padding:.9rem 1.25rem;border-radius:8px;border-left:4px solid var(--nz-blue);background:var(--nz-blue-light)}}
  .section-hd-label{{font-size:clamp(.72rem,1vw,.82rem);font-weight:700;color:var(--nz-blue)}}
  .panel{{background:white;border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-bottom:1.5rem}}
  .ph{{padding:.85rem 1.25rem;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}}
  .ph h3{{font-size:clamp(.78rem,1.1vw,.9rem);font-weight:600}}
  .badge{{font-family:'DM Mono',monospace;font-size:.52rem;padding:.15rem .5rem;text-transform:uppercase;letter-spacing:.06em;border-radius:4px;font-weight:500}}
  .badge-blue{{background:var(--nz-blue-light);color:var(--nz-blue)}}
  .badge-teal{{background:var(--nz-teal-light);color:var(--nz-teal)}}
  .sb{{display:flex;align-items:center;gap:.4rem;padding:.5rem 1.25rem;background:var(--paper);border-top:1px solid var(--border);font-family:'DM Mono',monospace;font-size:.54rem;color:var(--muted)}}
  .sd{{width:5px;height:5px;border-radius:50%;background:var(--nz-teal);flex-shrink:0}}
  .stat-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;padding:1.25rem}}
  .stat-item{{background:var(--paper);border-radius:8px;padding:1rem 1.25rem;border-left:3px solid var(--nz-blue)}}
  .si-label{{font-family:'DM Mono',monospace;font-size:.52rem;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:.3rem}}
  .si-val{{font-size:clamp(1.1rem,2vw,1.5rem);font-weight:700;color:var(--ink)}}
  .si-chg{{font-family:'DM Mono',monospace;font-size:.55rem;margin-top:.2rem}}
  .rate-strip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:1px;background:var(--border)}}
  .rate-cell{{background:white;padding:.85rem 1rem}}
  .rc-lbl{{font-family:'DM Mono',monospace;font-size:.52rem;text-transform:uppercase;color:var(--muted);margin-bottom:.2rem}}
  .rc-val{{font-size:clamp(1rem,1.8vw,1.3rem);font-weight:700;color:var(--ink)}}
  .rc-sub{{font-family:'DM Mono',monospace;font-size:.5rem;color:var(--muted);margin-top:.15rem}}
  footer{{max-width:1280px;margin:0 auto;padding:1.5rem;font-family:'DM Mono',monospace;font-size:.54rem;color:var(--muted);border-top:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem}}
</style>
</head>
<body>
<div class="topbar">
  <div class="topbar-inner">
    <a class="logo-wrap" href="../index.html#top">
      <img src="../index_files/logo.svg" alt="Newzip" onerror="this.style.display='none'">
      <div class="header-title">Market Tracker</div>
    </a>
    <a class="back-link" href="../index.html">← National Overview</a>
  </div>
</div>

<main>
  <div class="state-hero">
    <div class="state-name">{name}</div>
    <div class="state-sub">Local Housing Market · Zillow ZHVI · {period_label}</div>
    <div class="hero-stats">
      <div>
        <div class="hero-stat-val">{zhvi_fmt}</div>
        <div class="hero-stat-lbl">Typical Home Value</div>
        <div class="hero-stat-chg" style="color:{yoy_col};">{yoy_str} &nbsp;{mom_str}</div>
      </div>
      <div>
        <div class="hero-stat-val">{r30:.2f}%</div>
        <div class="hero-stat-lbl">30Y Mortgage Rate</div>
        <div class="hero-stat-chg">PMMS · {pdate}</div>
      </div>
      <div>
        <div class="hero-stat-val">{abs(yoy_bps)}bps</div>
        <div class="hero-stat-lbl">YoY Rate Change</div>
        <div class="hero-stat-chg">{'▼ Lower' if yoy_bps <= 0 else '▲ Higher'} than 1yr ago</div>
      </div>
      <div>
        <div class="hero-stat-val">{spread_bps}bps</div>
        <div class="hero-stat-lbl">30Y/10Y Spread</div>
        <div class="hero-stat-chg">Norm ~170bps</div>
      </div>
    </div>
  </div>

  <div class="section-hd">
    <span class="section-hd-label">🏘 {name} Home Values</span>
  </div>

  <div class="panel">
    <div class="ph"><h3>Zillow Home Value Index (ZHVI)</h3><span class="badge badge-blue">Zillow</span></div>
    <div class="stat-grid">
      <div class="stat-item">
        <div class="si-label">Typical Home Value</div>
        <div class="si-val">{zhvi_fmt}</div>
        <div class="si-chg" style="color:{yoy_col};">{yoy_str}</div>
      </div>
      <div class="stat-item">
        <div class="si-label">Month-over-Month</div>
        <div class="si-val">{mom_str or 'N/A'}</div>
        <div class="si-chg" style="color:var(--muted);">{period_label}</div>
      </div>
      <div class="stat-item" style="border-left-color:var(--muted);background:var(--paper2);">
        <div class="si-label">Data Period</div>
        <div class="si-val" style="font-size:1rem;">{period_label}</div>
        <div class="si-chg" style="color:var(--muted);">Updated monthly</div>
      </div>
    </div>
    <div class="sb"><div class="sd"></div><span>Zillow ZHVI · State-level · Smoothed, seasonally adjusted · Updated monthly</span></div>
  </div>

  <div class="section-hd" style="border-left-color:var(--nz-teal-bright);background:var(--nz-teal-bright-light);">
    <span class="section-hd-label" style="color:var(--nz-teal-bright);">📊 National Mortgage Rates</span>
  </div>

  <div class="panel">
    <div class="ph"><h3>Current Mortgage Rates</h3><span class="badge badge-teal">Freddie Mac PMMS</span></div>
    <div class="rate-strip">
      <div class="rate-cell">
        <div class="rc-lbl">30Y Fixed</div>
        <div class="rc-val">{r30:.2f}%</div>
        <div class="rc-sub">PMMS · {pdate}</div>
      </div>
      <div class="rate-cell">
        <div class="rc-lbl">15Y Fixed</div>
        <div class="rc-val">{pmms.get('rate_15y', 0):.2f}%</div>
        <div class="rc-sub">PMMS · {pdate}</div>
      </div>
      <div class="rate-cell">
        <div class="rc-lbl">1yr Ago 30Y</div>
        <div class="rc-val">{yago:.2f}%</div>
        <div class="rc-sub">{"▼ Rates lower now" if yoy_bps <= 0 else "▲ Rates higher now"}</div>
      </div>
      <div class="rate-cell">
        <div class="rc-lbl">30Y/10Y Spread</div>
        <div class="rc-val">{spread_bps}bps</div>
        <div class="rc-sub">{spread.get('signal','—')} · norm ~170bps</div>
      </div>
    </div>
    <div class="sb"><div class="sd"></div><span>Freddie Mac PMMS via FRED · National rates · State-specific rates may vary slightly</span></div>
  </div>

  <div class="panel" style="background:linear-gradient(135deg,#EEF1FC,#E8F7F5);border:1px solid var(--border);">
    <div style="padding:1.5rem;text-align:center;">
      <div style="font-size:clamp(.8rem,1.5vw,1rem);font-weight:600;color:var(--ink);margin-bottom:.5rem;">More local data coming soon</div>
      <div style="font-family:'DM Mono',monospace;font-size:clamp(.55rem,.8vw,.65rem);color:var(--muted);max-width:500px;margin:0 auto;line-height:1.7;">
        We're adding Redfin metro-level data, FRED state housing indicators, and permit activity for {name}.
        <br>Check back soon — or <a href="../index.html" style="color:var(--nz-blue);text-decoration:underline;">return to the national overview</a>.
      </div>
    </div>
  </div>

</main>

<footer>
  <div>Newzip Market Tracker · {name} · {RUN_TS} · Not financial advice</div>
  <a href="../index.html" style="color:var(--nz-blue);">← National Overview</a>
</footer>
</body>
</html>"""


# ── ENTRY POINT ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{'='*60}\nNewzip Market Tracker — {RUN_TS}\n{'='*60}\n")
    if not FRED_KEY: print("WARNING: FRED_API_KEY not set\n")
    if not FANNIE_CLIENT_ID or not FANNIE_CLIENT_SECRET: print("WARNING: Fannie Mae creds not set\n")
    if not ANTHROPIC_API_KEY: print("WARNING: ANTHROPIC_API_KEY not set — summary will use static fallback\n")

    rates    = fetch_obmmi()
    pmms     = fetch_pmms()
    housing  = fetch_fannie_housing()
    economic = fetch_fannie_economic()
    hpsi     = fetch_fannie_hpsi()
    spread       = fetch_spread()
    news_fortune = fetch_fortune_news()
    news_inman   = fetch_inman_news()
    pending      = fetch_pending()
    redfin_market = fetch_redfin_market()
    zillow_market = fetch_zillow_market()

    # Extract state-level data from Zillow result
    state_data = zillow_market.pop("state_data", {})

    html = build_html(rates, pmms, housing, economic, hpsi, news_fortune, news_inman, pending, spread,
                      redfin_market=redfin_market, zillow_market=zillow_market, state_data=state_data)
    html = html.replace("{LOGO_SRC}", LOGO_SRC)

    with open("index.html","w",encoding="utf-8") as f:
        f.write(html)
    print(f"Done — index.html written ({len(html):,} bytes)")

    # ── Write state pages ──────────────────────────────────────────────────────
    if state_data:
        import os as _os
        _os.makedirs("states", exist_ok=True)
        written = 0
        for abbr, sd in state_data.items():
            try:
                state_html = build_state_page(abbr, sd, pmms, rates, spread)
                state_html = state_html.replace("{LOGO_SRC}", LOGO_SRC)
                with open(f"states/{abbr}.html","w",encoding="utf-8") as f:
                    f.write(state_html)
                written += 1
            except Exception as e:
                print(f"  WARN: failed to write states/{abbr}.html: {e}")
        print(f"Done — {written} state pages written to states/")
    else:
        print("  No state data — state pages skipped")

    print(f"\n{'='*60}")
    print(f"  OBMMI 30Y    : {rates[0]['rate'] if rates else 'N/A'}%")
    print(f"  PMMS 30Y     : {pmms.get('rate_30y')}%")
    print(f"  HPSI         : {hpsi['value'] if hpsi else 'N/A'}")
    print(f"  Fortune news : {len(news_fortune)} articles")
    print(f"  Inman news   : {len(news_inman)} articles")
    print(f"  Pending Index: {pending.get('value')} ({pending.get('date')})")
    print(f"  Redfin market: DOM {redfin_market.get('median_dom')}d · supply {redfin_market.get('months_of_supply')}mo · inv {redfin_market.get('inventory')}")
    print(f"  Zillow ZHVI  : ${zillow_market.get('zhvi'):,} ({zillow_market.get('zhvi_yoy'):+}% YoY)")
    print(f"  State pages  : {len(state_data)} states")
    print(f"{'='*60}\n")

