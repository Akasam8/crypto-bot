# Backtest report

**Nothing is proven.** None of the 8 setup families made money after fees on data they weren't built on, in a way that clearly beat random entries. Live trading stays off. Test mode will still trade the best 3 unproven setups with fake money, so you can watch how they do against real prices and fees. None of them can go live.

Data: 25 coins, hourly candles from 2025-11-01 to 2026-11-01. Setups were picked on 2025-11-09 to 2026-06-24 and judged on 2026-07-01 to 2026-11-01, which they never saw. 252 setup variations were tried in total, so some will look good on training data by pure luck. That's why only the unseen year and the walk forward periods count.

Every trade pays 0.5% Coinbase taker fee plus 0.1% slippage on the way in and again on the way out, so a round trip costs about 1.20%. A trade has to move that much just to break even.

For comparison, over the test period simply holding BTC returned +33.12% and holding all the coins equally returned +72.60%.

## Results by setup

| Setup | Test trades | Win rate | Avg per trade after fees | Profit factor | Beat random? | Walk forward | Verdict |
|---|---|---|---|---|---|---|---|
| Breakout with volume | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Oversold bounce in a BTC uptrend | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Volume spike continuation | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Alt catching up to BTC | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Trend pullback | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Trend breakout | 143 | 45% | +3.71% | 2.09 | no | 0/2 positive | failed |
| Moving average cross | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Momentum leader | 78 | 49% | +6.35% | 2.22 | no | 1/2 positive | failed |

## Breakout with volume

Failed: nothing was profitable after fees on the training data.

## Oversold bounce in a BTC uptrend

Failed: nothing was profitable after fees on the training data.

## Volume spike continuation

Failed: nothing was profitable after fees on the training data.

## Alt catching up to BTC

Failed: nothing was profitable after fees on the training data.

## Trend pullback

Failed: nothing was profitable after fees on the training data.

## Trend breakout

Best version on training data: `trend_breakout[btc_filter=True,days=20]|72h|timed`. Rule: Price breaks above its highest point of the last 20 days while above its 20 day average, with BTC above its 50 day average. Hold up to 72h, no target, stop about 2x expected move, otherwise sell at the max hold time.

Training: 122 trades, +0.108% per trade, win rate 36%.

Unseen test period: 143 trades, +3.705% per trade after fees (+4.067% if entries filled as maker), win rate 45%, average win +15.87%, average loss -6.15%, profit factor 2.09, worst losing streak 8, 75% of months positive. Exits: target 0%, stop 10%, time 90%.

The same trades slid to random times averaged +0.372%. To pass, the setup had to beat +5.430%, which only 2.5% of random runs reach. Share of random runs that did at least as well as the setup: 8.0%.

By market regime: BTC above 50d avg: yes: 143 trades, +3.705%; high volatility: yes: 72 trades, +3.152%; high volatility: no: 71 trades, +4.267%.

Walk forward inside the training period (picked on 4 months, tested on the next 2): 2026-03-09 to 2026-05-09: 110 trades, -0.320% per trade, -1.284% vs the 75th percentile of random timing; ? to ?: nothing passed training.

**Failed because:** didn't clearly beat random entries (3.71% vs 5.43% for the top 2.5% of random runs); walk forward: only 0 of 2 unseen periods made money and beat random timing.

## Moving average cross

Failed: nothing was profitable after fees on the training data.

## Momentum leader

Best version on training data: `momentum_leader[top=3]|168h|timed`. Rule: Once a day, buy a coin that's in the top 3 for 7 day gains, up on the week, while BTC is above its 50 day average. Hold up to 168h, no target, stop about 2x expected move, otherwise sell at the max hold time.

Training: 64 trades, +2.752% per trade, win rate 45%.

Unseen test period: 78 trades, +6.348% per trade after fees (+6.719% if entries filled as maker), win rate 49%, average win +23.74%, average loss -10.17%, profit factor 2.22, worst losing streak 7, 50% of months positive. Exits: target 0%, stop 19%, time 81%.

The same trades slid to random times averaged +4.322%. To pass, the setup had to beat +19.713%, which only 2.5% of random runs reach. Share of random runs that did at least as well as the setup: 17.8%.

By market regime: BTC above 50d avg: yes: 78 trades, +6.348%; high volatility: yes: 29 trades, +12.100%; high volatility: no: 49 trades, +2.944%.

Walk forward inside the training period (picked on 4 months, tested on the next 2): ? to ?: nothing passed training; 2026-05-09 to 2026-06-24: 14 trades, +0.051% per trade, +1.107% vs the 75th percentile of random timing.

**Failed because:** didn't clearly beat random entries (6.35% vs 19.71% for the top 2.5% of random runs); only 50% of test months were positive; walk forward: only 1 of 2 unseen periods made money and beat random timing.

## Test mode setups (unproven)

These looked best over the whole year, which is exactly the data they were picked on, so their numbers are flattering. Test mode trades them with fake money to find out if they hold up on new prices.

**Momentum leader**: Once a day, buy a coin that's in the top 3 for 7 day gains, up on the week, while BTC is above its 50 day average. Hold up to 168h, target about 2x expected move, stop about 1x. Past year: 158 trades, 49% wins, +3.40% per trade after fees. Last 4 months alone: 86 trades, +4.70% per trade.

**Trend breakout**: Price breaks above its highest point of the last 10 days while above its 20 day average, with BTC above its 50 day average. Hold up to 72h, no target, stop about 2x expected move, otherwise sell at the max hold time. Past year: 346 trades, 45% wins, +1.67% per trade after fees. Last 4 months alone: 178 trades, +3.21% per trade.

**Moving average cross**: The 5 day average crosses above the 20 day average. Hold up to 168h, no target, stop about 2x expected move, otherwise sell at the max hold time. Past year: 243 trades, 42% wins, +1.45% per trade after fees. Last 4 months alone: 89 trades, +7.23% per trade.

## Caveats

Trades on different coins often fire at the same time because crypto moves together, so the real number of independent bets is smaller than the trade count. The live bot also caps open positions, so it can't take every signal the backtest took. Spreads and fills on small coins can be worse than the slippage assumed here. Markets change, which is why the backtest reruns every month and drops setups that stop working.
