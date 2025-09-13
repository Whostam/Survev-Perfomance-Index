# Survev Performance Index (SPI)

A paste-friendly **Streamlit app** to compute a single Survev skill rating from your mode stats (Solo/Duo/Squad).  
It combines **Kills/Game, Survival time, Average Damage, and Win%** with a **small-sample confidence weight** and gives you a **tier**.

## 🌟 Features
- Paste messy text from your Survev profile — the parser extracts just what we need.
- Manual overrides if parsing misses anything.
- Per-mode **SPI** + **Adjusted SPI** (confidence-weighted) + **Tier**.
- Games-weighted **Overall rating** across modes.
- Tunable confidence constant (in Settings).

## 🧮 Formula
Per mode:
- **Base (Consistency):** `Kills/Games × 100`
- **Survival (capped at 3:00):** `min(AvgSurvived, 180) / 180 × 50`
- **Damage:** `AvgDamage / 500 × 40`
- **Win Bonus:** `Win% × 2`

```
SPI = Base + Survival + Damage + WinBonus
```

**Confidence weight** to avoid 1–5-game spikes:
```
AdjSPI = 300 + (Games / (Games + 50)) × (SPI − 300)
```
**Overall rating** is the games-weighted average of per-mode AdjSPI.

**Tiers**
- Grandmaster: ≥ 750
- Master: 650–749
- Diamond: 550–649
- Platinum: 450–549
- Gold: 350–449
- Silver: 250–349
- Bronze: < 250

## 🚀 Run Locally
```bash
# 1) Clone
git clone https://github.com/<YOUR-USER>/Survev-Perfomance-Index.git
cd Survev-Perfomance-Index

# 2) Create env (optional but recommended)
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3) Install deps
pip install -r requirements.txt

# 4) Launch
streamlit run survev_spi_app.py
```

## ☁️ Deploy (Streamlit Community Cloud)
1. Push this repo to GitHub (you already did 🎉).  
2. Go to https://share.streamlit.io → **New app**.  
3. Select this repo, branch `main`, and file **`survev_spi_app.py`**.  
4. Leave Python version default and let it read `requirements.txt`.  
5. Click **Deploy**.

## 📋 Example paste (works in the text box)
```
SOLO 280 GAMES
WINS 58    WIN % 20.7
KILLS 1062
AVG SURVIVED 2:37
AVG DAMAGE 432

DUO 79 GAMES
WINS 10    WIN % 12.7
KILLS 233
AVG SURVIVED 2:20
AVG DAMAGE 441

SQUAD 232 GAMES
WINS 73    WIN % 31.5
KILLS 681
AVG SURVIVED 2:37
AVG DAMAGE 568
```

## 🔧 Customize
- Change tier thresholds or the confidence constant in code (top of file).
- Translate parser keywords if your UI language differs.

## 🙌 Credits
Built with ❤️ for Survev players by Whosty and ChatGPT.
