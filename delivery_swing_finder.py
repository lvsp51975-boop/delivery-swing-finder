#!/usr/bin/env python3
"""
=============================================================================
  DELIVERY SWING TRADE FINDER  |  ScanX + yfinance
  ─────────────────────────────────────────────────
  Scrapes https://scanx.trade/insight/top-deliveries for Daily / Weekly /
  Monthly delivery data, merges the three timeframes into a confluence score,
  then layers technical confirmation (EMA, RSI, MACD, Volume) via yfinance
  to surface the best swing-trade candidates.

  REQUIREMENTS (run once):
      pip install playwright yfinance pandas tabulate colorama
      playwright install chromium

  USAGE:
      python delivery_swing_finder.py               # full run, Nifty 50
      python delivery_swing_finder.py --index "Nifty 100"
      python delivery_swing_finder.py --index "Nifty 500" --top 20
      python delivery_swing_finder.py --no-tech      # skip yfinance (faster)
      python delivery_swing_finder.py --csv result.csv
=============================================================================
"""

import argparse
import sys
import time
import json
import warnings
import math
from datetime import datetime

import pandas as pd

warnings.filterwarnings("ignore")

# ─── Colour helpers ───────────────────────────────────────────────────────────
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    GREEN  = Fore.GREEN
    YELLOW = Fore.YELLOW
    RED    = Fore.RED
    CYAN   = Fore.CYAN
    BOLD   = Style.BRIGHT
    RESET  = Style.RESET_ALL
except ImportError:
    GREEN = YELLOW = RED = CYAN = BOLD = RESET = ""

# ─── CONSTANTS ────────────────────────────────────────────────────────────────
SCANX_URL  = "https://scanx.trade/insight/top-deliveries"
WAIT_MS    = 7000        # ms to wait after page load for JS to render
HEADLESS   = True

# Delivery % thresholds for scoring
DELIV_HIGH   = 60        # ≥ this → strong conviction
DELIV_MEDIUM = 40        # ≥ this → moderate

# Technical filters
RSI_MIN = 40
RSI_MAX = 70
EMA_FAST = 20
EMA_SLOW = 50

# ─── SCRAPER ──────────────────────────────────────────────────────────────────

def scrape_scanx(index_name: str = "Nifty 50") -> dict:
    """
    Returns dict:
        {
          'daily':   [{ symbol, name, ltp, change_pct, traded, delivered, delivery_pct }, ...],
          'weekly':  [...],
          'monthly': [...]
        }
    Uses Playwright (headless Chromium) to render JS and click each tab.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(RED + "✗ playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    results = {}
    tab_labels = ["Daily", "Weekly", "Monthly"]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        print(CYAN + f"⟳ Loading {SCANX_URL} …")
        page.goto(SCANX_URL, wait_until="networkidle", timeout=60_000)
        page.wait_for_timeout(WAIT_MS)

        # ── Select index from dropdown ────────────────────────────────────────
        _set_index(page, index_name)

        for tab_label in tab_labels:
            print(CYAN + f"  ↳ Scraping tab: {tab_label}")
            _click_tab(page, tab_label)
            page.wait_for_timeout(3000)
            rows = _parse_table(page)
            results[tab_label.lower()] = rows
            print(f"     → {len(rows)} rows")

        browser.close()

    return results


def _set_index(page, index_name: str):
    """Try to select the given index from the dropdown."""
    try:
        # Look for select or custom dropdown
        selects = page.query_selector_all("select")
        for sel in selects:
            options = sel.query_selector_all("option")
            for opt in options:
                if index_name.lower() in (opt.inner_text() or "").lower():
                    sel.select_option(label=opt.inner_text())
                    page.wait_for_timeout(2000)
                    return
        # Custom dropdown (div-based)
        dropdowns = page.query_selector_all("[class*='dropdown'], [class*='select']")
        for dd in dropdowns:
            text = dd.inner_text() or ""
            if any(x in text for x in ["Nifty", "Sensex", "Bank"]):
                dd.click()
                page.wait_for_timeout(500)
                items = page.query_selector_all("[class*='option'], [class*='item'], li")
                for item in items:
                    if index_name.lower() in (item.inner_text() or "").lower():
                        item.click()
                        page.wait_for_timeout(2000)
                        return
    except Exception:
        pass  # Default index is fine


def _click_tab(page, label: str):
    """Click a Daily / Weekly / Monthly tab button."""
    try:
        # Strategy 1: button / span containing exact text
        for selector in ["button", "span", "div[role='tab']", "li", "a"]:
            els = page.query_selector_all(selector)
            for el in els:
                txt = (el.inner_text() or "").strip()
                if txt.lower() == label.lower():
                    el.click()
                    return
        # Strategy 2: text-contains selector
        page.click(f"text={label}", timeout=5000)
    except Exception:
        pass


def _parse_table(page) -> list:
    """Extract rows from the main delivery table."""
    rows_data = []
    try:
        # Extract via JS evaluation for robustness
        rows_data = page.evaluate("""
        () => {
            const rows = [];
            const table = document.querySelector('table');
            if (!table) return rows;
            const trs = table.querySelectorAll('tbody tr');
            trs.forEach(tr => {
                const tds = tr.querySelectorAll('td');
                if (tds.length < 6) return;
                const name_el = tds[0].querySelector('a') || tds[0];
                const sym_img = tds[0].querySelector('img');
                let symbol = '';
                if (sym_img) {
                    const src = sym_img.src || sym_img.getAttribute('src') || '';
                    symbol = src.split('/').pop().replace('.png','').replace('.svg','');
                }
                rows.push({
                    name:         (name_el.innerText || '').trim().split('\\n')[0],
                    symbol:       symbol,
                    ltp:          (tds[1].innerText || '').trim().replace(/,/g,''),
                    change:       (tds[2].innerText || '').trim().replace(/,/g,''),
                    change_pct:   (tds[3].innerText || '').trim().replace('%',''),
                    traded:       (tds[4].innerText || '').trim().replace(/,/g,''),
                    delivered:    (tds[5].innerText || '').trim().replace(/,/g,''),
                    delivery_pct: (tds[6] ? tds[6].innerText || tds[5].innerText : tds[5].innerText || '').trim().replace('%','')
                });
            });
            return rows;
        }
        """)
    except Exception as e:
        print(YELLOW + f"  ⚠ Table parse error: {e}")

    # If JS eval got nothing, try Python-side parsing
    if not rows_data:
        rows_data = _parse_table_python(page)

    return _clean_rows(rows_data)


def _parse_table_python(page) -> list:
    """Python fallback: parse via BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return []
        rows_data = []
        for tr in table.find_all("tr")[1:]:  # skip header
            tds = tr.find_all("td")
            if len(tds) < 6:
                continue
            img = tds[0].find("img")
            symbol = ""
            if img:
                src = img.get("src", "")
                symbol = src.split("/")[-1].replace(".png", "")
            rows_data.append({
                "name":         tds[0].get_text(strip=True).split("\n")[0],
                "symbol":       symbol,
                "ltp":          tds[1].get_text(strip=True).replace(",", ""),
                "change":       tds[2].get_text(strip=True).replace(",", ""),
                "change_pct":   tds[3].get_text(strip=True).replace("%", ""),
                "traded":       tds[4].get_text(strip=True).replace(",", ""),
                "delivered":    tds[5].get_text(strip=True).replace(",", ""),
                "delivery_pct": tds[6].get_text(strip=True).replace("%", "") if len(tds) > 6 else "",
            })
        return rows_data
    except Exception:
        return []


def _clean_rows(rows: list) -> list:
    """Convert strings to numerics, filter garbage rows."""
    clean = []
    for r in rows:
        try:
            r["ltp"]          = float(str(r.get("ltp", 0)).replace(",", "") or 0)
            r["change_pct"]   = float(str(r.get("change_pct", 0)).replace(",", "").replace("+", "") or 0)
            r["traded"]       = float(str(r.get("traded", 0)).replace(",", "") or 0)
            r["delivered"]    = float(str(r.get("delivered", 0)).replace(",", "") or 0)
            r["delivery_pct"] = float(str(r.get("delivery_pct", 0)).replace(",", "").replace("%", "") or 0)
            if r["ltp"] > 0 and r["delivery_pct"] > 0:
                clean.append(r)
        except Exception:
            continue
    return clean


# ─── CONFLUENCE SCORING ───────────────────────────────────────────────────────

def build_confluence(data: dict) -> pd.DataFrame:
    """
    Merge daily / weekly / monthly delivery data.
    Delivery Confluence Score (0–10):
        - Daily   delivery %  → 0–3.5 pts  (weight 35%)
        - Weekly  delivery %  → 0–3.5 pts  (weight 35%)
        - Monthly delivery %  → 0–3.0 pts  (weight 30%)
    Higher weight on weekly (sustained buying vs one-day spike).
    """
    daily_map   = {r["name"]: r for r in data.get("daily",   [])}
    weekly_map  = {r["name"]: r for r in data.get("weekly",  [])}
    monthly_map = {r["name"]: r for r in data.get("monthly", [])}

    all_names = set(daily_map) | set(weekly_map) | set(monthly_map)
    records = []

    for name in all_names:
        d = daily_map.get(name,   {})
        w = weekly_map.get(name,  {})
        m = monthly_map.get(name, {})

        d_pct = d.get("delivery_pct", 0)
        w_pct = w.get("delivery_pct", 0)
        m_pct = m.get("delivery_pct", 0)

        # Normalise 0–100 → 0–1 (cap at 80 for top mark)
        def norm(x): return min(x / 80.0, 1.0)

        d_score = norm(d_pct) * 3.5
        w_score = norm(w_pct) * 3.5
        m_score = norm(m_pct) * 3.0
        total   = round(d_score + w_score + m_score, 2)

        # Coverage bonus: all 3 timeframes present
        tf_count = sum([1 for x in [d_pct, w_pct, m_pct] if x > 0])
        coverage_bonus = 0.5 if tf_count == 3 else 0.0
        total = min(total + coverage_bonus, 10.0)

        symbol = d.get("symbol") or w.get("symbol") or m.get("symbol") or ""
        ltp    = d.get("ltp") or w.get("ltp") or m.get("ltp") or 0
        change = d.get("change_pct", 0)

        records.append({
            "name":         name,
            "symbol":       symbol,
            "ltp":          ltp,
            "change_pct":   change,
            "daily_del%":   d_pct,
            "weekly_del%":  w_pct,
            "monthly_del%": m_pct,
            "tf_count":     tf_count,
            "del_score":    total,
        })

    df = pd.DataFrame(records)
    if df.empty:
        return df
    df = df.sort_values("del_score", ascending=False).reset_index(drop=True)
    return df


# ─── TECHNICAL ANALYSIS ───────────────────────────────────────────────────────

def add_technicals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch 6-month OHLCV from yfinance for each stock and compute:
        EMA20, EMA50, RSI14, MACD signal, Volume ratio
    Then produce a Technical Score (0–10) and a combined Final Score.
    """
    try:
        import yfinance as yf
    except ImportError:
        print(YELLOW + "⚠ yfinance not installed. Skipping technicals.")
        return df

    tech_rows = []
    total = len(df)
    print(CYAN + f"\n⟳ Fetching technicals for {total} stocks via yfinance …")

    for i, row in df.iterrows():
        sym = row["symbol"]
        # ScanX symbols don't have .NS — add it
        if sym and not sym.endswith(".NS") and not sym.endswith(".BO"):
            yf_sym = sym + ".NS"
        elif sym:
            yf_sym = sym
        else:
            # Try to derive from name
            yf_sym = row["name"].upper().replace(" ", "")[:10] + ".NS"

        print(f"  [{i+1}/{total}] {yf_sym:<20}", end=" ", flush=True)

        try:
            ticker = yf.Ticker(yf_sym)
            hist   = ticker.history(period="6mo", interval="1d", auto_adjust=True)
            if hist.empty or len(hist) < 30:
                raise ValueError("Insufficient data")

            close  = hist["Close"]
            volume = hist["Volume"]

            ema_fast = close.ewm(span=EMA_FAST, adjust=False).mean()
            ema_slow = close.ewm(span=EMA_SLOW, adjust=False).mean()
            rsi      = _calc_rsi(close, 14)
            macd_sig = _calc_macd_signal(close)
            vol_ratio= volume.iloc[-1] / volume.iloc[-20:].mean() if volume.iloc[-20:].mean() > 0 else 1

            last_close  = close.iloc[-1]
            last_ema_f  = ema_fast.iloc[-1]
            last_ema_s  = ema_slow.iloc[-1]
            last_rsi    = rsi.iloc[-1]
            last_macd   = macd_sig.iloc[-1]   # positive = bullish

            # ── Technical score ──────────────────────────────────────────────
            t_score = 0.0

            # 1. Price above both EMAs (trend)
            if last_close > last_ema_f:  t_score += 1.5
            if last_close > last_ema_s:  t_score += 1.5

            # 2. EMA alignment (fast > slow)
            if last_ema_f > last_ema_s:  t_score += 1.0

            # 3. RSI in sweet spot (not overbought, not dead)
            if RSI_MIN <= last_rsi <= RSI_MAX: t_score += 2.0
            elif last_rsi < RSI_MIN:           t_score += 0.5   # oversold — risky

            # 4. MACD signal positive
            if last_macd > 0:  t_score += 2.0
            elif last_macd > -0.5: t_score += 0.5

            # 5. Volume surge (institutional activity aligned with delivery)
            if vol_ratio >= 1.5:   t_score += 1.5
            elif vol_ratio >= 1.0: t_score += 0.5

            t_score = min(round(t_score, 2), 10.0)

            # ── Swing signal ─────────────────────────────────────────────────
            # Combined
            final = round((row["del_score"] * 0.55) + (t_score * 0.45), 2)

            trend = "↑ BULLISH" if last_close > last_ema_s else ("↓ BEARISH" if last_close < last_ema_s else "→ NEUTRAL")
            signal = _swing_signal(row["del_score"], t_score, last_rsi, last_macd, last_close, last_ema_s)

            tech_rows.append({
                "ema20":       round(last_ema_f, 2),
                "ema50":       round(last_ema_s, 2),
                "rsi14":       round(last_rsi, 1),
                "macd_sig":    round(last_macd, 3),
                "vol_ratio":   round(vol_ratio, 2),
                "tech_score":  t_score,
                "final_score": final,
                "trend":       trend,
                "signal":      signal,
            })
            print(f"RSI={last_rsi:.0f}  Tech={t_score:.1f}  Final={final:.2f}  {signal}")

        except Exception as e:
            print(f"[skip: {e}]")
            tech_rows.append({
                "ema20": None, "ema50": None, "rsi14": None,
                "macd_sig": None, "vol_ratio": None,
                "tech_score": None, "final_score": row["del_score"],
                "trend": "N/A", "signal": "NO DATA",
            })

        time.sleep(0.3)   # be polite to yfinance

    tech_df = pd.DataFrame(tech_rows, index=df.index)
    return pd.concat([df, tech_df], axis=1)


def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def _calc_macd_signal(series: pd.Series, fast=12, slow=26, sig=9) -> pd.Series:
    ema_f  = series.ewm(span=fast, adjust=False).mean()
    ema_s  = series.ewm(span=slow, adjust=False).mean()
    macd   = ema_f - ema_s
    signal = macd.ewm(span=sig, adjust=False).mean()
    return macd - signal   # histogram; positive = bullish momentum


def _swing_signal(del_score, tech_score, rsi, macd, close, ema50):
    if del_score is None or tech_score is None:
        return "NO DATA"
    if del_score >= 7 and tech_score >= 7:
        return "★ STRONG BUY"
    if del_score >= 6 and tech_score >= 5 and close > ema50:
        return "✔ BUY"
    if del_score >= 5 and rsi < 45:
        return "◎ ACCUMULATE"
    if del_score >= 4 and tech_score >= 4:
        return "~ WATCH"
    return "✗ SKIP"


# ─── OUTPUT ───────────────────────────────────────────────────────────────────

def print_results(df: pd.DataFrame, top_n: int = 15):
    if df.empty:
        print(RED + "\n✗ No data returned. Check internet connection and try again.")
        return

    has_tech = "final_score" in df.columns

    sort_col = "final_score" if has_tech else "del_score"
    df = df.sort_values(sort_col, ascending=False).reset_index(drop=True)
    df_top = df.head(top_n)

    # ── Banner ────────────────────────────────────────────────────────────────
    print("\n" + "═"*80)
    print(BOLD + CYAN + "  📊 DELIVERY SWING TRADE FINDER  |  " + datetime.now().strftime("%d-%b-%Y %H:%M"))
    print("═"*80)

    try:
        from tabulate import tabulate

        if has_tech:
            cols = ["#", "Name", "LTP", "Chg%",
                    "D-Del%", "W-Del%", "M-Del%",
                    "DelScore", "RSI", "TechScore", "FinalScore", "Signal"]
            rows = []
            for idx, r in df_top.iterrows():
                signal = str(r.get("signal", ""))
                col = GREEN if "BUY" in signal else (YELLOW if "WATCH" in signal or "ACCUM" in signal else "")
                rows.append([
                    col + str(idx+1) + RESET,
                    col + str(r["name"])[:22] + RESET,
                    f"{r['ltp']:>10.2f}",
                    f"{r['change_pct']:>+6.2f}%",
                    f"{r['daily_del%']:>6.1f}%",
                    f"{r['weekly_del%']:>6.1f}%",
                    f"{r['monthly_del%']:>7.1f}%",
                    f"{r['del_score']:>8.2f}",
                    f"{r['rsi14']:>5.1f}" if r.get('rsi14') else "  N/A",
                    f"{r['tech_score']:>9.2f}" if r.get('tech_score') is not None else "   N/A",
                    f"{r['final_score']:>10.2f}",
                    col + signal + RESET,
                ])
        else:
            cols = ["#", "Name", "LTP", "Chg%",
                    "Daily Del%", "Weekly Del%", "Monthly Del%", "DelScore", "TF"]
            rows = []
            for idx, r in df_top.iterrows():
                rows.append([
                    idx+1, r["name"][:22],
                    f"{r['ltp']:>10.2f}",
                    f"{r['change_pct']:>+6.2f}%",
                    f"{r['daily_del%']:>6.1f}%",
                    f"{r['weekly_del%']:>6.1f}%",
                    f"{r['monthly_del%']:>7.1f}%",
                    f"{r['del_score']:>8.2f}",
                    r["tf_count"],
                ])

        print(tabulate(rows, headers=cols, tablefmt="fancy_grid"))

    except ImportError:
        # Plain fallback
        print(df_top.to_string(index=False))

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "─"*80)
    print(BOLD + "  SCORING METHODOLOGY")
    print("─"*80)
    print("  Delivery Score (0–10) ← Daily 35% + Weekly 35% + Monthly 30% + TF bonus")
    if has_tech:
        print("  Technical Score (0–10) ← EMA trend + RSI + MACD + Volume surge")
        print("  Final Score          ← Delivery 55% + Technical 45%")
        print()
        print(GREEN + "  ★ STRONG BUY  = DelScore≥7 & TechScore≥7  → high-conviction swing entry")
        print(GREEN + "  ✔ BUY         = DelScore≥6 & TechScore≥5  → solid setup")
        print(YELLOW + "  ◎ ACCUMULATE  = Del momentum without tech confirmation, RSI oversold")
        print(YELLOW + "  ~ WATCH       = Moderate scores, wait for trigger candle")
        print(RED    + "  ✗ SKIP        = Weak or mixed signals")
    print("─"*80)
    print()

    # ── Top 5 picks ───────────────────────────────────────────────────────────
    if has_tech:
        buys = df[df["signal"].str.contains("BUY", na=False)].head(5)
        if not buys.empty:
            print(BOLD + GREEN + "  🎯 TOP PICKS FOR SWING TRADE:")
            for _, r in buys.iterrows():
                print(f"     {r['name']:<25}  LTP={r['ltp']:>8.2f}  Final={r['final_score']:.2f}  {r['signal']}")
        print()


def save_csv(df: pd.DataFrame, path: str):
    df.to_csv(path, index=False)
    print(GREEN + f"✓ Results saved → {path}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Delivery Swing Trade Finder using ScanX + yfinance"
    )
    p.add_argument("--index",   default="Nifty 50",  help="Index to analyse (default: Nifty 50)")
    p.add_argument("--top",     default=15, type=int, help="Top N stocks to display")
    p.add_argument("--no-tech", action="store_true",  help="Skip yfinance technical analysis")
    p.add_argument("--csv",     default="",           help="Save results to CSV path")
    p.add_argument("--visible", action="store_true",  help="Run browser in visible (non-headless) mode")
    return p.parse_args()


def main():
    args = parse_args()
    global HEADLESS
    if args.visible:
        HEADLESS = False

    print(BOLD + CYAN + "\n🚀 Delivery Swing Finder Starting …")
    print(f"   Index  : {args.index}")
    print(f"   Top N  : {args.top}")
    print(f"   Techs  : {'No' if args.no_tech else 'Yes (yfinance)'}")
    print()

    # 1. Scrape ScanX
    raw_data = scrape_scanx(index_name=args.index)

    for tf, rows in raw_data.items():
        print(f"   {tf.capitalize():<8}: {len(rows)} stocks")

    if all(len(v) == 0 for v in raw_data.values()):
        print(RED + "\n✗ No data scraped. Possible causes:")
        print("  1. ScanX site structure changed")
        print("  2. JS rendering too slow — try --visible to debug")
        print("  3. Network issue")
        sys.exit(1)

    # 2. Build confluence score
    print(CYAN + "\n⟳ Computing delivery confluence scores …")
    df = build_confluence(raw_data)
    print(f"   {len(df)} unique stocks across all timeframes")

    # 3. Technical confirmation
    if not args.no_tech:
        df = add_technicals(df)
    else:
        df["final_score"] = df["del_score"]
        df["signal"] = df["del_score"].apply(
            lambda s: "★ HIGH DEL" if s >= 8 else ("✔ GOOD DEL" if s >= 6 else "~ MODERATE")
        )

    # 4. Print
    print_results(df, top_n=args.top)

    # 5. Save
    if args.csv:
        save_csv(df, args.csv)
    else:
        default_csv = f"delivery_swings_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        save_csv(df, default_csv)


if __name__ == "__main__":
    main()
