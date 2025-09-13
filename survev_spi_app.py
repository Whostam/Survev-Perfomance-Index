
import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import streamlit as st
import pandas as pd

# ---------- CONFIG ----------
st.set_page_config(page_title="Survev SPI Calculator", page_icon="🎯", layout="centered")

TIERS = [
    ("Grandmaster", 750),
    ("Master", 650),
    ("Diamond", 550),
    ("Platinum", 450),
    ("Gold", 350),
    ("Silver", 250),
    ("Bronze", -10**9),  # floor
]

CONFIDENCE_CONST = 50  # affects shrinkage for small samples
NEUTRAL_BASELINE = 300
SURVIVAL_CAP_SEC = 180  # 3:00 cap for survival scaling

# ---------- HELPERS ----------
def parse_time_to_seconds(s: str) -> Optional[int]:
    """Parse 'M:SS' or 'MM:SS' to seconds. Returns None if not found."""
    s = s.strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", s)
    if not m: 
        return None
    minutes, seconds = int(m.group(1)), int(m.group(2))
    return minutes * 60 + seconds

def tier_from_score(score: float) -> str:
    for name, threshold in TIERS:
        if score >= threshold:
            return name
    return "Bronze"

@dataclass
class ModeStats:
    games: int
    kills: int
    win_pct: float
    avg_survived_sec: int
    avg_damage: float

    def spi_components(self) -> Dict[str, float]:
        base = (self.kills / self.games) * 100 if self.games > 0 else 0.0
        survival = (min(self.avg_survived_sec, SURVIVAL_CAP_SEC) / SURVIVAL_CAP_SEC) * 50.0
        damage = (self.avg_damage / 500.0) * 40.0
        win_bonus = self.win_pct * 2.0
        return {
            "Base": base,
            "Survival": survival,
            "Damage": damage,
            "WinBonus": win_bonus,
        }

    def spi(self) -> float:
        comps = self.spi_components()
        return comps["Base"] + comps["Survival"] + comps["Damage"] + comps["WinBonus"]

    def adj_spi(self) -> float:
        spi = self.spi()
        w = self.games / (self.games + CONFIDENCE_CONST) if self.games > 0 else 0.0
        return NEUTRAL_BASELINE + w * (spi - NEUTRAL_BASELINE)

# Robust paste parser
def parse_block(raw: str) -> Dict[str, ModeStats]:
    """
    Accepts a messy paste from the profile screen.
    Tries to extract per-mode blocks for SOLO, DUO, SQUAD.
    Looks for keys: games, kills, win %, avg survived, avg damage.
    """
    text = re.sub(r"[^\S\r\n]+", " ", raw)  # collapse whitespace but keep newlines
    modes = {}
    # Split by mode headers if present; otherwise, treat entire text as SOLO
    parts = re.split(r"(?i)\b(SOLO|DUO|SQUAD)\b", text)
    if len(parts) > 1:
        # parts like ['', 'SOLO', '...block...', 'DUO', '...block...']
        it = iter(parts)
        preamble = next(it, "")
        for mode, block in zip(it, it):
            parsed = parse_stats_in_text(block)
            if parsed:
                modes[mode.upper()] = parsed
    else:
        parsed = parse_stats_in_text(text)
        if parsed:
            modes["SOLO"] = parsed
    return modes

def find_number(pattern: str, s: str) -> Optional[float]:
    m = re.search(pattern, s, flags=re.I)
    if not m:
        return None
    return float(m.group(1))

def parse_stats_in_text(s: str) -> Optional[ModeStats]:
    # Games
    games = find_number(r"(\d+)\s*GAMES?", s) or find_number(r"\bGames?\b.*?(\d+)", s)
    # Kills
    kills = find_number(r"\bKILLS?\b.*?(\d+)", s)
    # Win %
    win_pct = find_number(r"\bWIN\s*%?\b.*?([\d.]+)", s)
    # Avg survived time like 3:18
    time_match = re.search(r"\bAVG\s*SURVIVED\b.*?(\d{1,2}:\d{2})", s, flags=re.I)
    avg_survived_sec = parse_time_to_seconds(time_match.group(1)) if time_match else None
    # Avg damage
    avg_damage = find_number(r"\bAVG\s*DAMAGE\b.*?([\d.]+)", s)

    # Fallbacks: sometimes the paste is minimal; allow direct fields too
    if games is None:
        # try from kills and k/g
        kg = find_number(r"\bK/?G\b.*?([\d.]+)", s)
        if kills is not None and kg:
            games = kills / kg

    # Validate
    if any(v is None for v in [games, kills, win_pct, avg_survived_sec, avg_damage]):
        return None

    return ModeStats(
        games=int(round(games)),
        kills=int(round(kills)),
        win_pct=float(win_pct),
        avg_survived_sec=int(avg_survived_sec),
        avg_damage=float(avg_damage),
    )

def overall_adj_spi(modes: Dict[str, ModeStats]) -> float:
    total_games = sum(m.games for m in modes.values())
    if total_games == 0:
        return 0.0
    weighted = sum(m.adj_spi() * m.games for m in modes.values())
    return weighted / total_games

# ---------- UI ----------
st.title("🎯 Survev SPI Calculator")
st.caption("Paste your stats text or fill the fields. Calculates per-mode SPI, applies small-sample confidence, and aggregates an Overall rating.")

with st.expander("How to use", expanded=False):
    st.markdown(
        """
        **Option A — Paste your stats:** Copy the text from your Survev profile screen
        (include the mode panels) and paste it below. The parser will extract what's needed.

        **Option B — Manual entry:** If parsing fails, fill in the fields for each mode you play.

        **We only need:** Games, Kills, Win %, Avg Survived (mm:ss), Avg Damage.
        """
    )

raw = st.text_area("Paste stats here (any format — we'll try to parse it):", height=220, placeholder="Example: SOLO 280 GAMES ... KILLS 1062 ... WIN % 20.7 ... AVG SURVIVED 2:37 ... AVG DAMAGE 432 ...")

parsed_modes = parse_block(raw) if raw.strip() else {}

# Manual overrides
st.subheader("Manual Entry / Fixes")
cols = st.columns(3)
mode_names = ["SOLO", "DUO", "SQUAD"]

def manual_mode_input(name: str) -> Optional[ModeStats]:
    with st.container():
        st.markdown(f"**{name}**")
        use = st.checkbox(f"Add/override {name}", value=(name in parsed_modes))
        if not use:
            return None
        games = st.number_input(f"{name} – Games", min_value=0, step=1, value=int(parsed_modes.get(name, ModeStats(0,0,0.0,0,0.0)).games) if name in parsed_modes else 0)
        kills = st.number_input(f"{name} – Kills", min_value=0, step=1, value=int(parsed_modes.get(name, ModeStats(0,0,0.0,0,0.0)).kills) if name in parsed_modes else 0)
        win_pct = st.number_input(f"{name} – Win %", min_value=0.0, max_value=100.0, step=0.1, value=float(parsed_modes.get(name, ModeStats(0,0,0.0,0,0.0)).win_pct) if name in parsed_modes else 0.0)
        time_str = st.text_input(f"{name} – Avg Survived (mm:ss)", value=f"{parsed_modes.get(name, ModeStats(0,0,0.0,0,0.0)).avg_survived_sec//60}:{parsed_modes.get(name, ModeStats(0,0,0.0,0,0.0)).avg_survived_sec%60:02d}" if name in parsed_modes else "0:00")
        avg_damage = st.number_input(f"{name} – Avg Damage", min_value=0.0, step=1.0, value=float(parsed_modes.get(name, ModeStats(0,0,0.0,0,0.0)).avg_damage) if name in parsed_modes else 0.0)
        sec = parse_time_to_seconds(time_str) or 0
        return ModeStats(int(games), int(kills), float(win_pct), int(sec), float(avg_damage))

manual_modes: Dict[str, ModeStats] = {}
c1, c2, c3 = st.columns(3)
with c1: m1 = manual_mode_input("SOLO")
with c2: m2 = manual_mode_input("DUO")
with c3: m3 = manual_mode_input("SQUAD")
for m, key in [(m1, "SOLO"), (m2, "DUO"), (m3, "SQUAD")]:
    if m:
        manual_modes[key] = m

# Merge: manual overrides trump parsed
modes = parsed_modes.copy()
modes.update(manual_modes)

st.markdown("---")
if not modes:
    st.info("Paste your stats above or enable a mode in Manual Entry.")
    st.stop()

# Results table
rows = []
for name, ms in modes.items():
    comps = ms.spi_components()
    spi = ms.spi()
    adj = ms.adj_spi()
    rows.append({
        "Mode": name,
        "Games": ms.games,
        "Kills": ms.kills,
        "Win %": round(ms.win_pct, 1),
        "Avg Survived (s)": ms.avg_survived_sec,
        "Avg Damage": round(ms.avg_damage, 1),
        "Base": round(comps["Base"], 1),
        "Survival": round(comps["Survival"], 1),
        "Damage": round(comps["Damage"], 1),
        "WinBonus": round(comps["WinBonus"], 1),
        "SPI": round(spi, 1),
        "AdjSPI": round(adj, 1),
        "Tier": tier_from_score(adj),
    })

df = pd.DataFrame(rows).sort_values("Mode")
st.dataframe(df, use_container_width=True)

overall = overall_adj_spi(modes)
st.subheader("Overall Rating")
st.metric(label="Overall AdjSPI", value=f"{overall:.1f}", delta=None)
st.markdown(f"**Tier:** `{tier_from_score(overall)}`")

with st.expander("Settings", expanded=False):
    st.write("Confidence constant (higher = slower trust of small samples)")
    cc = st.slider("Confidence constant", 10, 200, CONFIDENCE_CONST)
    st.caption("Change this and re-run to experiment (requires app restart).")

st.markdown("---")
st.caption("SPI = Base(Kills/Game×100) + Survival(≤3:00→50) + Damage(Avg/500×40) + WinBonus(Win%×2). AdjSPI shrinks toward 300 with low games.")
