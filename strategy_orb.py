"""
strategy_orb.py
---------------
Dual-Window Opening Range Breakout (ORB) Strategy.

SOURCE: Andrew Aziz, "Advanced Techniques in Day Trading"

TWO ORB WINDOWS
---------------
Primary   (15-min): range = 9:15–9:30 IST, entries until 11:00 IST
Secondary (30-min): range = 9:15–9:45 IST, entries until 11:30 IST

The strategy checks the primary window first. If no signal fires for a
stock on the primary window, the secondary window provides a second chance.
Secondary captures "slow starters" that consolidate beyond the 15-min range
before committing to a direction.

ENTRY RULES (applied to both windows — example for LONG)
---------------------------------------------------------
  1. ORB window has closed (established flag = True)
  2. Before the window's entry cutoff time
  3. Gap direction aligned: gap-up → LONG allowed; gap-down → LONG blocked
  4. Close > ORB high (price has broken out)
  5. Extension ≤ chase limit (not chasing a move already 1% extended)
  6. Volume on breakout candle ≥ multiplier × 10-candle average
  7. Close > VWAP (fair-value confirmation)
  8. ORB range is meaningful: 0.3%–4% of price

STOP LOSS   LONG: ORB Low  |  SHORT: ORB High
TARGET      LONG/SHORT: entry ± (ORB range × 2.5)

EXIT SIGNALS (priority order)
------------------------------
  TARGET     — candle High/Low touches target (intrabar detection)
  STOP_LOSS  — candle Low/High breaches effective SL
               Breakeven trigger: SL moves to entry once gain = 0.5 × initial risk
  ORB_FAILED — close more than 0.8% back inside the range
               Uses the breakout level stored in the position (correct for both windows)
  SQUARE_OFF — forced close at 15:10 IST (handled by main loop)
"""

import logging
from datetime import datetime

import pandas as pd
import pytz

from config import (
    ORB_BREAKEVEN_TRIGGER_R,
    ORB_CHASE_LIMIT_PCT,
    ORB_CHASE_LIMIT_SECONDARY,
    ORB_ENTRY_CUTOFF_SECONDARY,
    ORB_ENTRY_CUTOFF_TIME,
    ORB_FAILED_BUFFER_PCT,
    ORB_MAX_RANGE_PCT,
    ORB_MIN_GAP_PCT,
    ORB_MIN_RANGE_PCT,
    ORB_POSITION_SCALE,
    ORB_TARGET_MULTIPLIER,
    ORB_VOLUME_MULT_SECONDARY,
    ORB_VOLUME_MULTIPLIER,
)
from indicators import (
    DAY_OPEN_COL,
    ORB_EST_30_COL,
    ORB_ESTABLISHED_COL,
    ORB_HIGH_30_COL,
    ORB_HIGH_COL,
    ORB_LOW_30_COL,
    ORB_LOW_COL,
    PREV_DAY_CLOSE_COL,
    VOLAVG_COL,
    VWAP_COL,
)

IST    = pytz.timezone("Asia/Kolkata")
logger = logging.getLogger(__name__)
_HOLD  = {"action": "HOLD", "sl": 0.0, "target": 0.0}

STRATEGY_NAME = "ORB"


def _is_past_cutoff(now_ist: datetime, cutoff_str: str) -> bool:
    h, m = map(int, cutoff_str.split(":"))
    return now_ist >= now_ist.replace(hour=h, minute=m, second=0, microsecond=0)


def _check_orb_window(
    row,
    symbol:      str,
    now_ist:     datetime,
    cutoff_time: str,
    orb_high_key: str,
    orb_low_key:  str,
    orb_est_key:  str,
    vol_multiplier: float,
    chase_limit:    float,
    window_label:   str,
    gap_pct:        float,
    gap_up:         bool,
    gap_down:       bool,
    close:          float,
    vol_ratio:      float,
    vwap:           float,
) -> dict:
    """
    Evaluate one ORB window for entry signal.
    Returns a signal dict or _HOLD.
    """
    if _is_past_cutoff(now_ist, cutoff_time):
        return _HOLD

    if not bool(row.get(orb_est_key, False)):
        return _HOLD

    orb_high_val = row.get(orb_high_key)
    orb_low_val  = row.get(orb_low_key)
    if pd.isna(orb_high_val) or pd.isna(orb_low_val):
        return _HOLD

    orb_high  = float(orb_high_val)
    orb_low   = float(orb_low_val)
    orb_range = orb_high - orb_low

    if orb_range <= 0:
        return _HOLD

    range_pct = orb_range / orb_high
    if range_pct < ORB_MIN_RANGE_PCT:
        logger.info(f"{symbol} ORB-{window_label}: range too narrow ({range_pct:.2%})")
        return _HOLD
    if range_pct > ORB_MAX_RANGE_PCT:
        logger.info(f"{symbol} ORB-{window_label}: range too wide ({range_pct:.2%})")
        return _HOLD

    logger.info(
        f"{symbol} ORB-{window_label}: close={close:.2f} "
        f"orb=[{orb_low:.2f}–{orb_high:.2f}] range={range_pct:.2%} "
        f"gap={gap_pct:+.2%} vol={vol_ratio:.2f}x vwap={vwap:.2f}"
    )

    # ---- LONG: breakout above ORB high ----
    if close > orb_high:
        if gap_down:
            logger.info(f"{symbol} ORB-{window_label}: LONG rejected — gap-down ({gap_pct:+.2%})")
            return _HOLD

        extension = (close - orb_high) / orb_high
        if extension > chase_limit:
            logger.info(f"{symbol} ORB-{window_label}: LONG rejected — chasing {extension:.2%}")
            return _HOLD
        if vol_ratio < vol_multiplier:
            logger.info(f"{symbol} ORB-{window_label}: LONG rejected — weak volume {vol_ratio:.2f}x")
            return _HOLD
        if vwap > 0 and close < vwap:
            logger.info(f"{symbol} ORB-{window_label}: LONG rejected — below VWAP {vwap:.2f}")
            return _HOLD

        sl   = orb_low
        risk = close - sl
        if risk <= 0:
            return _HOLD
        target = close + (orb_range * ORB_TARGET_MULTIPLIER)
        rr     = (target - close) / risk
        logger.info(
            f"{symbol} ORB-{window_label}: *** BUY *** "
            f"entry={close:.2f} sl={sl:.2f} target={target:.2f} "
            f"R:R={rr:.1f} vol={vol_ratio:.2f}x gap={gap_pct:+.2%}"
        )
        return {
            "action": "BUY",
            "sl": sl,
            "target": target,
            "strategy": STRATEGY_NAME,
            "quantity_scale": ORB_POSITION_SCALE,
            "orb_breakout_level": orb_high,   # stored for ORB_FAILED exit check
            "window": window_label,
        }

    # ---- SHORT: breakdown below ORB low ----
    if close < orb_low:
        if gap_up:
            logger.info(f"{symbol} ORB-{window_label}: SHORT rejected — gap-up ({gap_pct:+.2%})")
            return _HOLD

        extension = (orb_low - close) / orb_low
        if extension > chase_limit:
            logger.info(f"{symbol} ORB-{window_label}: SHORT rejected — chasing {extension:.2%}")
            return _HOLD
        if vol_ratio < vol_multiplier:
            logger.info(f"{symbol} ORB-{window_label}: SHORT rejected — weak volume {vol_ratio:.2f}x")
            return _HOLD
        if vwap > 0 and close > vwap:
            logger.info(f"{symbol} ORB-{window_label}: SHORT rejected — above VWAP {vwap:.2f}")
            return _HOLD

        sl   = orb_high
        risk = sl - close
        if risk <= 0:
            return _HOLD
        target = close - (orb_range * ORB_TARGET_MULTIPLIER)
        rr     = (close - target) / risk
        logger.info(
            f"{symbol} ORB-{window_label}: *** SELL *** "
            f"entry={close:.2f} sl={sl:.2f} target={target:.2f} "
            f"R:R={rr:.1f} vol={vol_ratio:.2f}x gap={gap_pct:+.2%}"
        )
        return {
            "action": "SELL",
            "sl": sl,
            "target": target,
            "strategy": STRATEGY_NAME,
            "quantity_scale": ORB_POSITION_SCALE,
            "orb_breakout_level": orb_low,   # stored for ORB_FAILED exit check
            "window": window_label,
        }

    return _HOLD


def generate_signal(df: pd.DataFrame, symbol: str = "", sim_time=None) -> dict:
    """
    Evaluate the last completed candle (iloc[-2]) for an ORB entry signal.

    Checks primary 15-min window first. If no signal, checks secondary 30-min window.

    sim_time: candle timestamp for backtesting.
    """
    now_ist = sim_time if sim_time is not None else datetime.now(IST)
    if hasattr(now_ist, "tzinfo") and now_ist.tzinfo is None:
        now_ist = IST.localize(now_ist)

    if len(df) < 3:
        return _HOLD

    row = df.iloc[-2]

    # --- Common values ---
    close   = float(row["Close"])
    volume  = float(row["Volume"])
    vol_avg = float(row[VOLAVG_COL]) if not pd.isna(row.get(VOLAVG_COL)) else 0.0
    vwap    = float(row[VWAP_COL])   if not pd.isna(row.get(VWAP_COL))   else 0.0

    vol_ratio = (volume / vol_avg) if vol_avg > 0 else 0.0

    # Gap calculation
    prev_close = row.get(PREV_DAY_CLOSE_COL)
    day_open   = row.get(DAY_OPEN_COL)
    gap_pct    = 0.0
    if not pd.isna(prev_close) and not pd.isna(day_open) and float(prev_close) > 0:
        gap_pct = (float(day_open) - float(prev_close)) / float(prev_close)

    gap_up   = gap_pct >= ORB_MIN_GAP_PCT
    gap_down = gap_pct <= -ORB_MIN_GAP_PCT

    common = dict(
        symbol=symbol, now_ist=now_ist,
        gap_pct=gap_pct, gap_up=gap_up, gap_down=gap_down,
        close=close, vol_ratio=vol_ratio, vwap=vwap,
    )

    # --- Primary window (15-min ORB) ---
    signal = _check_orb_window(
        row,
        cutoff_time=ORB_ENTRY_CUTOFF_TIME,
        orb_high_key=ORB_HIGH_COL,
        orb_low_key=ORB_LOW_COL,
        orb_est_key=ORB_ESTABLISHED_COL,
        vol_multiplier=ORB_VOLUME_MULTIPLIER,
        chase_limit=ORB_CHASE_LIMIT_PCT,
        window_label="15m",
        **common,
    )
    if signal["action"] in ("BUY", "SELL"):
        return signal

    # --- Secondary window (30-min ORB) ---
    signal = _check_orb_window(
        row,
        cutoff_time=ORB_ENTRY_CUTOFF_SECONDARY,
        orb_high_key=ORB_HIGH_30_COL,
        orb_low_key=ORB_LOW_30_COL,
        orb_est_key=ORB_EST_30_COL,
        vol_multiplier=ORB_VOLUME_MULT_SECONDARY,
        chase_limit=ORB_CHASE_LIMIT_SECONDARY,
        window_label="30m",
        **common,
    )
    return signal


def check_exit_signal(df: pd.DataFrame, position: dict) -> str | None:
    """
    Exit conditions for an open ORB position.

    Priority:
      1. TARGET     — intrabar: candle High (BUY) / Low (SELL) reached target
      2. STOP_LOSS  — intrabar: candle Low (BUY) / High (SELL) hit effective SL
                      Breakeven: SL → entry once gain = ORB_BREAKEVEN_TRIGGER_R × risk
      3. ORB_FAILED — close-based: price closed back inside the ORB range
                      Uses orb_breakout_level stored in position (correct for both windows)
    """
    if len(df) < 2:
        return None

    row      = df.iloc[-2]
    close    = float(row["Close"])
    candle_h = float(row["High"])
    candle_l = float(row["Low"])

    direction    = position["direction"]
    target       = float(position["target"])
    original_sl  = float(position["sl"])
    entry_price  = float(position.get("entry_price", original_sl))
    initial_risk = abs(entry_price - original_sl)

    # The breakout level used for ORB_FAILED — stored from whichever window fired.
    # Falls back to df column if not present (backward compatibility).
    breakout_level = position.get("orb_breakout_level")
    if breakout_level is None:
        raw = row.get(ORB_HIGH_COL if direction == "BUY" else ORB_LOW_COL)
        breakout_level = float(raw) if raw is not None and not pd.isna(raw) else None

    if direction == "BUY":
        if initial_risk > 0 and candle_h >= entry_price + ORB_BREAKEVEN_TRIGGER_R * initial_risk:
            effective_sl = max(original_sl, entry_price)
        else:
            effective_sl = original_sl

        if candle_h >= target:
            return "TARGET"
        if candle_l <= effective_sl:
            return "STOP_LOSS"
        if breakout_level and close < breakout_level * (1 - ORB_FAILED_BUFFER_PCT):
            return "ORB_FAILED"

    else:  # SELL
        if initial_risk > 0 and candle_l <= entry_price - ORB_BREAKEVEN_TRIGGER_R * initial_risk:
            effective_sl = min(original_sl, entry_price)
        else:
            effective_sl = original_sl

        if candle_l <= target:
            return "TARGET"
        if candle_h >= effective_sl:
            return "STOP_LOSS"
        if breakout_level and close > breakout_level * (1 + ORB_FAILED_BUFFER_PCT):
            return "ORB_FAILED"

    return None
