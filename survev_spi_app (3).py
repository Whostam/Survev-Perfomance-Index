
import re
from dataclasses import dataclass
from typing import Dict, Optional
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Survev SPI Calculator", page_icon="🎯", layout="centered")

TIERS = [
    ("Grandmaster", 750),
    ("Master", 650),
    ("Diamond", 550),
    ("Platinum", 450),
    ("Gold", 350),
    ("Silver", 250),
    ("Bronze", -10**9),
]
CONFIDENCE_CONST = 50
NEUTRAL_BASELINE = 300
SURVIVAL_CAP_SEC = 180  # 3:00

def parse_time_to_seconds(s: str) -> Optional[int]:
    s = s.strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", s)
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))

def tier_from_score(score: float) -> str:
    for name, th in TIERS:
        if score >= th:
            return name
    return "Bronze"

@dataclass
class ModeStats:
    games: int
    kills: int
    win_pct: float
    avg_survived_sec: int
    avg_damage: float

    def spi_components(self):
        base = (self.kills / self.games) * 100 if self.games > 0 else 0.0
        survival = (min(self.avg_survived_sec, SURVIVAL_CAP_SEC) / SURVIVAL_CAP_SEC) * 50.0
        damage = (self.avg_damage / 500.0) * 40.0
        win_bonus = self.win_pct * 2.0
        return {"Base": base, "Survival": survival, "Damage": damage, "WinBonus": win_bonus}

    def spi(self) -> float:
        c = self.spi_components()
        return c["Base"] + c["Survival"] + c["Damage"] + c["WinBonus"]

    def adj_spi(self) -> float:
        s = self.spi()
        w = self.games / (self.games + CONFIDENCE_CONST) if self.games > 0 else 0.0
        return NEUTRAL_BASELINE + w * (s - NEUTRAL_BASELINE)

def _num(x: str) -> Optional[float]:
    if x is None:
        return None
    x = x.strip().replace(",", ".")
    try:
        return float(x)
    except:
        return None

def _take(s: str, patterns):
    for p in patterns:
        m = re.search(p, s, flags=re.I | re.S)
        if m:
            return m.group(1)
    return None

def parse_stats_in_text(s: str) -> Optional[ModeStats]:
    # Robust patterns: allow label:value, label on next line, or value then label.
    games = _take(s, [
        r"(\d+)\s*GAMES?",
        r"\bGAMES?\b(?:\s*[:\-]?\s*|\s*\n\s*)(\d+)",
    ])
    kills = _take(s, [
        r"\bKILLS?\b(?:\s*[:\-]?\s*|\s*\n\s*)(\d+)",
    ])
    win_pct = _take(s, [
        r"\bWIN\s*%?(?:\s*[:\-]?\s*|\s*\n\s*)([\d.,]+)",
    ])
    t = _take(s, [
        r"\bAVG\s*SURVIVED\b(?:\s*[:\-]?\s*|\s*\n\s*)(\d{1,2}:\d{2})",
    ])
    avg_survived_sec = parse_time_to_seconds(t) if t else None
    avg_damage = _take(s, [
        r"\bAVG\s*DAMAGE\b(?:\s*[:\-]?\s*|\s*\n\s*)([\d.,]+)",
    ])

    # Fallback: compute games from Kills and K/G if needed
    if games is None:
        kg = _take(s, [r"\bK/?G\b(?:\s*[:\-]?\s*|\s*\n\s*)([\d.,]+)"])
        if kills and kg:
            try:
                games = float(kills) / float(kg.replace(",", "."))
            except:
                games = None

    # Convert
    if any(v is None for v in [games, kills, win_pct, avg_survived_sec, avg_damage]):
        return None
    return ModeStats(
        games=int(round(float(games))),
        kills=int(round(float(kills))),
        win_pct=float(_num(win_pct)),
        avg_survived_sec=int(avg_survived_sec),
        avg_damage=float(_num(avg_damage)),
    )

def parse_block(raw: str):
    # Keep newlines, collapse only spaces/tabs
    text = re.sub(r"[^\S\r\n]+", " ", raw)
    modes = {}
    parts = re.split(r"(?i)\b(SOLO|DUO|SQUAD)\b", text)
    if len(parts) > 1:
        it = iter(parts)
        _ = next(it, "")
        for mode, block in zip(it, it):
            parsed = parse_stats_in_text(block)
            if parsed:
                modes[mode.upper()] = parsed
    else:
        parsed = parse_stats_in_text(text)
        if parsed:
            modes["SOLO"] = parsed
    return modes

def overall_adj_spi(modes: Dict[str, ModeStats]) -> float:
    total = sum(m.games for m in modes.values())
    if total == 0:
        return 0.0
    return sum(m.adj_spi() * m.games for m in modes.values()) / total

st.title("🎯 Survev SPI Calculator")
st.caption("Paste your stats (even messy). We'll search across newlines and labels on separate lines.")

with st.expander("How to use", expanded=False):
    st.write("Paste the whole page text, or turn on manual entry below. Needed fields per mode: Games, Kills, Win %, Avg Survived (mm:ss), Avg Damage.")

raw = st.text_area("Paste your stats here:", height=270, placeholder="Paste the full text from your stats page...")

parsed_modes = parse_block(raw) if raw.strip() else {}

# Debug: show what we found
with st.expander("🔎 Debug: parsed fields", expanded=False):
    if parsed_modes:
        for name, ms in parsed_modes.items():
            st.write(name, ms)
    else:
        st.write("No modes parsed yet.")

st.subheader("Manual Entry / Fixes")
def manual_input(name: str):
    st.markdown(f"**{name}**")
    use = st.checkbox(f"Add/override {name}", value=(name in parsed_modes))
    if not use:
        return None
    g = st.number_input(f"{name} – Games", min_value=0, step=1, value=(parsed_modes.get(name).games if name in parsed_modes else 0))
    k = st.number_input(f"{name} – Kills", min_value=0, step=1, value=(parsed_modes.get(name).kills if name in parsed_modes else 0))
    w = st.number_input(f"{name} – Win %", min_value=0.0, max_value=100.0, step=0.1, value=(parsed_modes.get(name).win_pct if name in parsed_modes else 0.0))
    t = st.text_input(f"{name} – Avg Survived (mm:ss)", value=(f"{parsed_modes.get(name).avg_survived_sec//60}:{parsed_modes.get(name).avg_survived_sec%60:02d}" if name in parsed_modes else "0:00"))
    d = st.number_input(f"{name} – Avg Damage", min_value=0.0, step=1.0, value=(parsed_modes.get(name).avg_damage if name in parsed_modes else 0.0))
    sec = parse_time_to_seconds(t) or 0
    return ModeStats(int(g), int(k), float(w), int(sec), float(d))

manual_modes: Dict[str, ModeStats] = {}
c1, c2, c3 = st.columns(3)
with c1: m1 = manual_input("SOLO")
with c2: m2 = manual_input("DUO")
with c3: m3 = manual_input("SQUAD")
for m, key in [(m1, "SOLO"), (m2, "DUO"), (m3, "SQUAD")]:
    if m: manual_modes[key] = m

modes = parsed_modes.copy()
modes.update(manual_modes)

st.markdown("---")
if not modes:
    st.info("Paste your stats above or enable a mode in Manual Entry.")
    st.stop()

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
st.metric("Overall AdjSPI", f"{overall:.1f}")
st.markdown(f"**Tier:** `{tier_from_score(overall)}`")
