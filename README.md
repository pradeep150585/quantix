# 📈 Nifty Scanner Pro

AI-powered Nifty 200 market intelligence platform built with Python, Streamlit, and the Upstox API v2.

---

## Features

| Section | Description |
|---|---|
| **Live Dashboard** | All major NSE indices with RSI, MACD, heatmap, VIX, A/D ratio |
| **Live Scanner** | Real-time Nifty 200 quotes — VWAP, TBQ/TSQ, Rel Volume, circuits |
| **News & Sentiment** | RSS-based news engine with keyword sentiment and AI recommendations |
| **Legendary Strategies** | Minervini Trend Template · Qullamaggie VCP · Zanger Breakouts |
| **AI Top Picks** | Composite scoring across technical, RS, volume, news, and sector |
| **Settings** | Configure API keys, alerts, scanner params, and refresh intervals |

---

## Quick Start

### 1. Clone and install

```bash
git clone <repo-url>
cd NiftyScanner
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure

```bash
cp config/config.yaml.example config/config.yaml
```

Edit `config/config.yaml` and set your Upstox access token:

```yaml
upstox:
  access_token: "YOUR_ACCESS_TOKEN_HERE"
  api_key: "YOUR_API_KEY_HERE"
```

Alternatively, use environment variables (they override config.yaml):

```bash
cp .env.example .env
# edit .env with your values
```

### 3. Run

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Getting an Upstox Access Token

1. Register at [upstox.com](https://upstox.com) and create an API app.
2. Complete the OAuth flow once to obtain an access token.
3. Paste the token into `config/config.yaml` or the `UPSTOX_ACCESS_TOKEN` env var.
4. Tokens expire daily — regenerate via the Upstox developer portal or automate with their OAuth flow.

---

## Deployment

### Streamlit Community Cloud

1. Push this repo to GitHub (ensure `config/config.yaml` is in `.gitignore`).
2. Add secrets in the Streamlit Cloud dashboard under **Settings → Secrets**:
   ```toml
   UPSTOX_ACCESS_TOKEN = "..."
   UPSTOX_API_KEY = "..."
   ```
3. Set the main file to `app.py`.

### Docker

```bash
docker build -t nifty-scanner .
docker run -p 8501:8501 \
  -e UPSTOX_ACCESS_TOKEN=your_token \
  -e UPSTOX_API_KEY=your_key \
  nifty-scanner
```

### Render / Railway

- Set environment variables `UPSTOX_ACCESS_TOKEN` and `UPSTOX_API_KEY` in the platform dashboard.
- Start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

### Linux VPS

```bash
pip install -r requirements.txt
# Run with screen or systemd
screen -S scanner
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

---

## Project Structure

```
app.py                  # Entry point
config/
  config.yaml           # Your configuration (gitignored)
  config.yaml.example   # Template
pages/                  # One file per navigation page
components/             # Reusable UI components and CSS
api/                    # Upstox REST + WebSocket clients
services/               # Instruments, market data, index, AI picks, alerts
scanner/                # Live scanner and strategy scan engine
strategies/             # Minervini, Qullamaggie, Zanger scoring
indicators/             # All technical indicators (pandas-ta based)
news/                   # RSS news engine with sentiment scoring
database/               # SQLite watchlist, alerts, scan history
utils/                  # Logger setup
logs/                   # Rotating log files
```

---

## Optional: Telegram Alerts

1. Create a bot via [@BotFather](https://t.me/BotFather) and get the token.
2. Get your chat ID from [@userinfobot](https://t.me/userinfobot).
3. Enable in `config.yaml`:
   ```yaml
   alerts:
     telegram_enabled: true
     telegram_bot_token: "..."
     telegram_chat_id: "..."
     min_score_alert: 75
   ```

---

## Disclaimer

This application is for **educational and informational purposes only**. It does not constitute financial advice. Strategy scanners are educational interpretations of publicly discussed trading principles. Always do your own research before making investment decisions.
