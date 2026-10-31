# crypto-bot

A small Coinbase bot that only trades setups which proved themselves on 3 years of hourly data, after fees, on data they were never tuned on. Most of the time the honest answer is "no trade", and the bot is built to say that.

## How it works

Everything runs on GitHub Actions, so nothing needs to stay on at home.

1. **Backtest** (`.github/workflows/backtest.yml`) pulls 3 years of hourly candles for the 25 most traded coins on Coinbase, tests 6 setup families (555 variations) with Coinbase fees and slippage on both sides, picks the best version of each on the first 2 years, then judges it on the last year it never saw. A setup only survives if it makes money after fees, beats the same trades slid to random times, and holds up in 3 rolling walk forward periods. It runs on the 1st of every month and whenever the code changes. Results land in `reports/`.
2. **Hourly scan** (`.github/workflows/scan.yml`) runs at 7 minutes past every hour. It checks open positions with exactly the backtest's exit rules, looks for surviving setups on the candle that just closed, applies the risk rules, and posts to Discord. Every signal and trade goes in `state/trades.csv`.
3. **Claude** reads the files in `claude_project/` (playbook, backtest report, journal summary) so you can ask it about any trade.

## Files worth reading

`reports/backtest_report.md` is the verdict. `reports/playbook.md` holds the market notes plus the live strategy cards. `state/trades.csv` is the journal, and `state/state.json` shows whether the bot is halted.

## Modes

Set these as repository **variables** (Settings, Secrets and variables, Actions, Variables tab):

| Variable | Values | What it does |
|---|---|---|
| `BOT_MODE` | `PAPER` (default), `LIVE_MANUAL`, `LIVE_AUTO` | Paper simulates trades. Live manual sends signals for you to place by hand. Live auto places real orders. |
| `TRADING_ENABLED` | `false` (default), `true` | Live auto only places orders when this is `true`. Set it to `false` to stop real orders instantly. |
| `COINBASE_PORTFOLIO_UUID` | your bot portfolio's ID | Live auto refuses to run without it. |

Only move from paper to live after **40+ paper trades, a positive result after fees, and a win rate within 10 points of the backtest**. The weekly Discord check tells you where you stand.

## Secrets

Set these under Settings, Secrets and variables, Actions, Secrets tab. Never paste them anywhere else.

| Secret | When |
|---|---|
| `DISCORD_WEBHOOK_URL` | now |
| `COINBASE_API_KEY` | only when going live auto |
| `COINBASE_API_SECRET` | only when going live auto |

## Going live auto, safely

1. In Coinbase, create a new portfolio called `bot` and move only the trading money into it (convert to USDC first if you hold GBP, since most coins trade against USDC).
2. In the Coinbase Developer Platform (portal.cdp.coinbase.com), create an API key **scoped to the bot portfolio**, tick **View** and **Trade**, leave **Transfer off**, and set the key type to **ECDSA** under advanced settings. Download the key file.
3. Put the key name in `COINBASE_API_KEY` and the private key in `COINBASE_API_SECRET`, and the portfolio's ID in the `COINBASE_PORTFOLIO_UUID` variable.
4. Set `BOT_MODE` to `LIVE_AUTO` and `TRADING_ENABLED` to `true`.

On every run the bot checks the key. If it can move money out, isn't scoped to that portfolio, or can't trade, the bot halts and tells you on Discord. Every entry goes in with an attached take profit and stop loss, so exits sit on Coinbase even if a run is late. Watch the first few live trades closely, because this part can only be fully proven against a real account.

## Risk rules (config.toml)

The bot never risks more than 2% of the pot on one trade (stop distance plus fees), with positions capped at £40. It allows at most 2 open positions and 3 new trades a day, stops for the day after losing £5, and halts completely if the pot falls to £80. It trades spot only and long only, with no leverage, margin, futures or perpetuals.

## Stopping it

To pause everything, go to Actions, pick Hourly scan, and click Disable workflow. To stop new real orders, set `TRADING_ENABLED` to `false`; positions already open keep being managed as long as the Coinbase key secrets stay in place. After a halt, review the journal, then go to Actions, pick **Resume after halt**, and click Run workflow.

## Running it yourself

```bash
pip install -r requirements.txt
python -m pytest -q                      # 24 tests incl. no lookahead and paper vs backtest parity
python -m bot.run_backtest --synthetic   # offline dry run on fake data with no edge in it
python -m bot.run_backtest               # real data, needs internet access to Coinbase
python -m bot.scan                       # one scan
```

## Moving it to another PC or server

Everything lives in this repo, so moving is a clone plus a scheduler. On any machine with Python 3.12:

```bash
git clone https://github.com/<you>/crypto-bot.git && cd crypto-bot
pip install -r requirements.txt
cp .env.example .env        # paste the same secrets you set in GitHub
```

On Windows, `powershell -ExecutionPolicy Bypass -File scripts\windows_tasks.ps1` registers hidden hourly scan and monthly backtest tasks (no console windows). On Linux or a Raspberry Pi, add `7 * * * * cd /path/to/crypto-bot && python3 -m bot.scan` to `crontab -e`. Then disable the GitHub workflows so two copies don't trade at once.

Not financial advice. Crypto can drop fast, and a setup that worked for 3 years can stop working.
