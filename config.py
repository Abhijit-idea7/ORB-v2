"""
config.py
---------
Configuration for the scaled-up ORB (Opening Range Breakout) trading bot.

Dual ORB windows:
  Primary   — 15-min range (9:15–9:30 IST), entries 9:30–11:00 IST
  Secondary — 30-min range (9:15–9:45 IST), entries 9:45–11:30 IST

Secondary window captures "slow starters" — stocks that consolidate longer
before breaking out. Doubles the signal opportunity without changing edge.

Key upgrades vs v1:
  • Universe 26 → 55 stocks (more sectors, more F&O coverage)
  • Daily candidates 15 → 25 (ATR%-ranked from expanded universe)
  • Max positions  5  → 10 (more concurrent trades)
  • Dual ORB windows (15-min primary + 30-min secondary)
  • Volume multiplier relaxed 1.3 → 1.15 (captures more valid breakouts)
  • Chase limit relaxed 0.8% → 1.0% (less filtering of valid breakouts)

All params can be overridden via environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Stock Universe — 55 NSE F&O stocks for ORB gap-and-breakout plays
# ---------------------------------------------------------------------------
# Selection criteria:
#   1. Active F&O participation → overnight institutional positioning drives gaps
#   2. Sector catalyst exposure → news-driven overnight moves
#   3. Sufficient liquidity → clean fills at market price
# ---------------------------------------------------------------------------
ORB_STOCK_UNIVERSE = [
    # Banking — most liquid, cleanest ORB structure
    "HDFCBANK", "SBIN", "AXISBANK", "ICICIBANK", "KOTAKBANK",
    "BANKBARODA", "PNB", "INDUSINDBK", "FEDERALBNK",
    "CANBK", "UNIONBANK", "IDFCFIRSTB",

    # Financials — rate-sensitive, gap on RBI/macro news
    "BAJFINANCE", "CHOLAFIN", "BAJAJFINSV", "LICHSGFIN", "MANAPPURAM",

    # IT — US tech moves and USD/INR drive overnight gaps
    "INFY", "WIPRO", "HCLTECH", "TCS", "TECHM", "LTIM", "PERSISTENT", "COFORGE",

    # Auto — monthly sales data and commodity input costs create gaps
    "TATAMOTORS", "M&M", "MARUTI", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT", "ASHOKLEY",

    # Metals — LME copper/steel overnight moves
    "TATASTEEL", "HINDALCO", "JSWSTEEL", "VEDL", "HINDCOPPER", "NMDC", "SAIL",

    # Oil & Gas — crude oil price gaps
    "RELIANCE", "ONGC", "BPCL", "IOC", "GAIL",

    # Power / Infra — policy and sector news sensitive
    "TATAPOWER", "ADANIGREEN", "ADANIPORTS", "ADANIENT", "NTPC", "POWERGRID",

    # High-beta / momentum
    "SUZLON", "ETERNAL", "IRCTC",

    # Pharma — FDA headline and USFDA inspection driven gaps
    "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB",
]

# ---------------------------------------------------------------------------
# Candidate Selection
# ---------------------------------------------------------------------------
ORB_TOP_N_STOCKS = int(os.getenv("ORB_TOP_N_STOCKS", "25"))
# ATR%-ranked from universe. Picks 25 most volatile stocks each morning.
# More candidates → more signal opportunities without lowering quality.

# ---------------------------------------------------------------------------
# Primary ORB Parameters (15-min window: 9:15–9:30 IST)
# ---------------------------------------------------------------------------
ORB_MINUTES             = int(os.getenv("ORB_MINUTES",            "15"))
# First 15 minutes of NSE session define the opening range.

ORB_VOLUME_MULTIPLIER   = float(os.getenv("ORB_VOLUME_MULTIPLIER", "1.15"))
# Breakout candle volume >= this × 10-candle avg.
# Relaxed from 1.3 → 1.15 to capture more valid breakouts.

ORB_MIN_RANGE_PCT       = float(os.getenv("ORB_MIN_RANGE_PCT",     "0.003"))
# Min ORB size as % of price (0.3%). Filters dead-flat opens.

ORB_MAX_RANGE_PCT       = float(os.getenv("ORB_MAX_RANGE_PCT",     "0.04"))
# Max ORB size as % of price (4%). Avoids extreme gap events.

ORB_CHASE_LIMIT_PCT     = float(os.getenv("ORB_CHASE_LIMIT_PCT",   "0.010"))
# Max extension beyond ORB level before entry blocked.
# Relaxed from 0.8% → 1.0% — captures breakouts that extend slightly further.

ORB_TARGET_MULTIPLIER   = float(os.getenv("ORB_TARGET_MULTIPLIER", "1.5"))
# Target = entry ± (ORB range × 1.5).
# Reduced from 2.5 → 1.5: backtest showed only 5.6% of trades reached 2.5× target,
# while 54% were force-closed at square-off time (price moved right direction but
# didn't travel far enough). At 1.5× far more trades complete as TARGET hits.
# Still profitable at 48% win rate with 1.5:1 R:R.

ORB_ENTRY_CUTOFF_TIME   = os.getenv("ORB_ENTRY_CUTOFF_TIME",       "11:00")
# Primary ORB entries cut off at 11:00 IST (90-min window after ORB establishes).

ORB_MIN_GAP_PCT         = float(os.getenv("ORB_MIN_GAP_PCT",       "0.002"))
# Gap-direction filter threshold (0.2%). Core edge — do not relax.

ORB_POSITION_SCALE      = float(os.getenv("ORB_POSITION_SCALE",    "1.0"))
# Capital scale per trade. 1.0 = Rs150,000 per trade.
# With 10 max positions: Rs150k × 10 = Rs1.5M max deployment.

ORB_FAILED_BUFFER_PCT   = float(os.getenv("ORB_FAILED_BUFFER_PCT", "0.005"))
# 0.5% close back inside range triggers ORB_FAILED exit.
# Tightened from 0.8% → 0.5%: cuts failing breakouts faster, reducing loss
# per failed trade. ORB_FAILED is the cleanest exit type — trigger it sooner.

ORB_BREAKEVEN_TRIGGER_R = float(os.getenv("ORB_BREAKEVEN_TRIGGER_R", "0.5"))
# Move SL to breakeven once trade gains 50% of initial risk.
# Tightened from 0.6R → 0.5R for faster capital protection at higher scale.

# ---------------------------------------------------------------------------
# Secondary ORB Parameters (30-min window: 9:15–9:45 IST)
# ---------------------------------------------------------------------------
ORB_SECONDARY_WINDOW_ENABLED = False
# DISABLED: backtest showed 30-min ORB had 36% win rate vs 50% for 15-min,
# producing net -Rs6,887 on 14 trades over 30 days. The wider range creates
# looser setups with lower conviction. Re-enable via env var if desired.
# Override: ORB_SECONDARY_WINDOW_ENABLED=true in .env

ORB_MINUTES_SECONDARY       = int(os.getenv("ORB_MINUTES_SECONDARY",       "30"))
ORB_ENTRY_CUTOFF_SECONDARY  = os.getenv("ORB_ENTRY_CUTOFF_SECONDARY",      "11:30")
ORB_VOLUME_MULT_SECONDARY   = float(os.getenv("ORB_VOLUME_MULT_SECONDARY", "1.20"))
ORB_CHASE_LIMIT_SECONDARY   = float(os.getenv("ORB_CHASE_LIMIT_SECONDARY", "0.010"))

# ---------------------------------------------------------------------------
# Position Management
# ---------------------------------------------------------------------------
ORB_MAX_POSITIONS            = int(os.getenv("ORB_MAX_POSITIONS", "10"))
# Max simultaneous open positions. Up from 5 → 10.

POSITION_SIZE_INR            = int(os.getenv("POSITION_SIZE_INR", "150000"))
# Capital per trade in INR. 10 × Rs150k = Rs1.5M max deployment.

DAILY_LOSS_CIRCUIT_BREAKER   = -999_999
# Effectively disabled. Re-enable with a sensible value if needed.

ONE_TRADE_PER_STOCK_PER_DAY  = True
# Once a stock closes (win or loss), blocked from re-entry same day.

# ---------------------------------------------------------------------------
# Shared Indicator Parameters
# ---------------------------------------------------------------------------
EMA_FAST        = 9
EMA_SLOW        = 20
EMA_MACRO       = 50
RSI_PERIOD      = 14
VOLUME_LOOKBACK = 10

# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------
TRADE_START_TIME    = "09:20"   # Wait until this time before entering the loop
SQUARE_OFF_TIME     = "15:10"   # Force-close all positions; 10-min buffer before Zerodha MIS
CANDLE_INTERVAL     = "2m"      # yfinance interval string
LOOP_SLEEP_SECONDS  = 120       # Sleep between strategy iterations (2-min candle)

# ---------------------------------------------------------------------------
# NIFTY50 Market Regime Filter
# ---------------------------------------------------------------------------
# Detects intraday market direction and adjusts position limits / allowed sides.
# BULL  → LONG_ONLY direction filter, full position count
# BEAR  → SHORT_ONLY direction filter, reduced position count
# NEUTRAL → both directions, moderate position count
# ---------------------------------------------------------------------------
REGIME_BULL_THRESHOLD        = 0.20
REGIME_BEAR_THRESHOLD        = -0.20
REGIME_BULL_MAX_POSITIONS    = 5    # Capped: backtest BULL days earned Rs613/day vs
                                    # BEAR days Rs3,366/day — BULL doesn't deserve full exposure
REGIME_BEAR_MAX_POSITIONS    = 5    # Same cap as BULL — short setups are cleaner
REGIME_NEUTRAL_MAX_POSITIONS = 5    # Conservative across all regimes

# ---------------------------------------------------------------------------
# Stocksdeveloper / Zerodha Webhook
# ---------------------------------------------------------------------------
STOCKSDEVELOPER_URL     = "https://tv.stocksdeveloper.in/"
STOCKSDEVELOPER_API_KEY = os.getenv("STOCKSDEVELOPER_API_KEY")
STOCKSDEVELOPER_ACCOUNT = os.getenv("STOCKSDEVELOPER_ACCOUNT", "AbhiZerodha")

if not STOCKSDEVELOPER_API_KEY:
    raise EnvironmentError(
        "STOCKSDEVELOPER_API_KEY is not set. "
        "Add it to your .env file or GitHub Actions secrets."
    )

EXCHANGE     = "NSE"
PRODUCT_TYPE = "INTRADAY"
ORDER_TYPE   = "MARKET"
VARIETY      = "REGULAR"
