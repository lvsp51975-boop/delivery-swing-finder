# 🚀 Delivery Swing Finder — GitHub Actions Setup

Runs every trading day at **4:15 PM IST** automatically — even when your PC is OFF.
Results sent to **Telegram** and/or **Email** with CSV attachment.

---

## 📁 Files Required in Your GitHub Repo

```
your-repo/
├── delivery_swing_finder.py        ← main script
├── results/                        ← auto-created, stores CSVs
│   └── .gitkeep
└── .github/
    └── workflows/
        └── delivery_swing.yml      ← this workflow file
```

---

## ⚡ One-Time Setup (15 minutes)

### Step 1 — Create GitHub Repo

1. Go to https://github.com/new
2. Create a **private** repo (e.g. `delivery-swing-finder`)
3. Upload both files:
   - `delivery_swing_finder.py`
   - `.github/workflows/delivery_swing.yml`
4. Create empty `results/` folder — add a file called `.gitkeep` inside it

---

### Step 2 — Set Up Telegram Bot (FREE, recommended)

1. Open Telegram → search **@BotFather**
2. Send `/newbot` → give it a name → copy the **Bot Token**
3. Start a chat with your new bot
4. Get your Chat ID:
   - Open: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Send any message to your bot first
   - Look for `"chat":{"id":XXXXXXXXX}` — that's your Chat ID

---

### Step 3 — Set Up Email (Gmail, optional)

1. Go to Google Account → Security → **App Passwords**
2. Generate an App Password for "Mail"
3. Save it (looks like: `xxxx xxxx xxxx xxxx`)

---

### Step 4 — Add Secrets to GitHub

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these secrets:

| Secret Name           | Value                        | Required? |
|-----------------------|------------------------------|-----------|
| `TELEGRAM_BOT_TOKEN`  | Your bot token               | Optional  |
| `TELEGRAM_CHAT_ID`    | Your Telegram chat ID        | Optional  |
| `GMAIL_USER`          | yourname@gmail.com           | Optional  |
| `GMAIL_APP_PASSWORD`  | Gmail app password           | Optional  |
| `NOTIFY_EMAIL`        | Email to send results to     | Optional  |

> You need at least ONE of Telegram or Email, otherwise results are only in GitHub artifacts.

---

### Step 5 — Enable Actions

1. Go to your repo → **Actions** tab
2. Click **"I understand my workflows, go ahead and enable them"**
3. Done! ✅

---

## 📅 Schedule

| Day       | Time (IST) | Runs? |
|-----------|-----------|-------|
| Mon–Fri   | 4:15 PM   | ✅ Yes |
| Saturday  | —         | ❌ No  |
| Sunday    | —         | ❌ No  |
| Holidays  | —         | ❌ No (script checks NSE calendar) |

---

## 🖐 Manual Run (anytime)

1. Go to repo → **Actions** → **Delivery Swing Finder**
2. Click **"Run workflow"**
3. Choose index + top N → **Run**

---

## 📥 Download Results

Every run saves a CSV artifact:

**Actions** → click the run → scroll down → **Artifacts** → download `swing-results-XXX`

Kept for **30 days** automatically.

---

## 🔔 What You'll Receive

**Telegram message:**
```
📊 Delivery Swing Finder — 20260514_1615
Total stocks scanned: 50

🎯 4 BUY Signals:
  Kotak Bank           LTP=383.20  Score=8.14  ★ STRONG BUY
  Tata Consumer        LTP=1228.30 Score=7.90  ★ STRONG BUY
  Apollo Hospitals     LTP=8119.00 Score=7.90  ★ STRONG BUY
  Grasim Industries    LTP=2938.70 Score=7.64  ★ STRONG BUY

📁 Download CSV from GitHub Actions artifacts.
```

**Email:** Same data as HTML table + CSV attached.

---

## 💰 Cost

**ZERO.** GitHub Free tier includes:
- 2,000 Actions minutes / month
- Each run takes ~5–8 minutes
- 20 trading days × 8 min = ~160 min/month ← well within free limit

---

## 🛠 Troubleshooting

| Problem | Fix |
|---------|-----|
| Workflow not triggering | Check Actions tab is enabled |
| Telegram not working | Verify Bot Token + Chat ID, make sure you messaged the bot first |
| Email not sending | Use App Password, not your Gmail password |
| Script fails | Check Actions logs → click failed step for details |
| ScanX scrape fails | Site may have changed; check manually and update selectors |
