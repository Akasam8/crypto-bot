# Backtest report

**Nothing is proven.** None of the 8 setup families made money after fees on data they weren't built on, in a way that clearly beat random entries. Live trading stays off. Test mode will still trade the best 3 unproven setups with fake money, so you can watch how they do against real prices and fees. None of them can go live.

Data: 25 coins, hourly candles from 2025-10-31 to 2026-10-31. Setups were picked on 2025-11-08 to 2026-06-23 and judged on 2026-06-30 to 2026-10-31, which they never saw. 252 setup variations were tried in total, so some will look good on training data by pure luck. That's why only the unseen year and the walk forward periods count.

Every trade pays 0.5% Coinbase taker fee plus 0.1% slippage on the way in and again on the way out, so a round trip costs about 1.20%. A trade has to move that much just to break even.

For comparison, over the test year simply holding BTC returned +32.01% and holding all the coins equally returned +69.98%.

## Results by setup

| Setup | Test trades | Win rate | Avg per trade after fees | Profit factor | Beat random? | Walk forward | Verdict |
|---|---|---|---|---|---|---|---|
| Breakout with volume | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Oversold bounce in a BTC uptrend | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Volume spike continuation | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Alt catching up to BTC | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Trend pullback | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Trend breakout | 140 | 44% | +3.04% | 1.87 | no | 0/2 positive | failed |
| Moving average cross | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Momentum leader | 76 | 49% | +5.60% | 2.07 | no | 0/2 positive | failed |

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

Training: 124 trades, +0.025% per trade, win rate 36%.

Unseen test year: 140 trades, +3.038% per trade after fees (+3.398% if entries filled as maker), win rate 44%, average win +14.72%, average loss -6.25%, profit factor 1.87, worst losing streak 8, 50% of months positive. Exits: target 0%, stop 10%, time 90%.

The same trades slid to random times averaged +0.410%. To pass, the setup had to beat +5.383%, which only 2.5% of random runs reach. Share of random runs that did at least as well as the setup: 8.2%.

By market regime: BTC above 50d avg: yes: 140 trades, +3.038%; high volatility: yes: 71 trades, +2.636%; high volatility: no: 69 trades, +3.451%.

Walk forward inside the training period (picked on 4 months, tested on the next 2): 2026-03-08 to 2026-05-08: 105 trades, -0.934% per trade, -1.822% vs the 75th percentile of random timing; ? to ?: nothing passed training.

**Failed because:** didn't clearly beat random entries (3.04% vs 5.38% for the top 2.5% of random runs); only 50% of test months were positive; walk forward: only 0 of 2 unseen periods made money and beat random timing.

## Moving average cross

Failed: nothing was profitable after fees on the training data.

## Momentum leader

Best version on training data: `momentum_leader[top=3]|168h|timed`. Rule: Once a day, buy a coin that's in the top 3 for 7 day gains, up on the week, while BTC is above its 50 day average. Hold up to 168h, no target, stop about 2x expected move, otherwise sell at the max hold time.

Training: 66 trades, +2.201% per trade, win rate 44%.

Unseen test year: 76 trades, +5.601% per trade after fees (+5.970% if entries filled as maker), win rate 49%, average win +22.24%, average loss -10.19%, profit factor 2.07, worst losing streak 7, 50% of months positive. Exits: target 0%, stop 20%, time 80%.

The same trades slid to random times averaged +3.939%. To pass, the setup had to beat +17.435%, which only 2.5% of random runs reach. Share of random runs that did at least as well as the setup: 21.2%.

By market regime: BTC above 50d avg: yes: 76 trades, +5.601%; high volatility: yes: 29 trades, +13.142%; high volatility: no: 47 trades, +0.948%.

Walk forward inside the training period (picked on 4 months, tested on the next 2): ? to ?: nothing passed training; 2026-05-08 to 2026-06-23: 18 trades, -2.454% per trade, -1.328% vs the 75th percentile of random timing.

**Failed because:** didn't clearly beat random entries (5.60% vs 17.44% for the top 2.5% of random runs); only 50% of test months were positive; walk forward: only 0 of 2 unseen periods made money and beat random timing.

## Test mode setups (unproven)

These looked best over the whole year, which is exactly the data they were picked on, so their numbers are flattering. Test mode trades them with fake money to find out if they hold up on new prices.

**Momentum leader**: Once a day, buy a coin that's in the top 3 for 7 day gains, up on the week, while BTC is above its 50 day average. Hold up to 168h, no target, stop about 2x expected move, otherwise sell at the max hold time. Past year: 142 trades, 46% wins, +4.02% per trade after fees. Last 4 months alone: 76 trades, +5.60% per trade.

**Trend breakout**: Price breaks above its highest point of the last 20 days while above its 20 day average, with BTC above its 50 day average. Hold up to 168h, no target, stop about 2x expected move, otherwise sell at the max hold time. Past year: 200 trades, 41% wins, +3.26% per trade after fees. Last 4 months alone: 102 trades, +7.67% per trade.

**Moving average cross**: The 5 day average crosses above the 20 day average. Hold up to 168h, no target, stop about 2x expected move, otherwise sell at the max hold time. Past year: 243 trades, 43% wins, +1.65% per trade after fees. Last 4 months alone: 89 trades, +7.43% per trade.

## Caveats

Trades on different coins often fire at the same time because crypto moves together, so the real number of independent bets is smaller than the trade count. The live bot also caps open positions, so it can't take every signal the backtest took. Spreads and fills on small coins can be worse than the slippage assumed here. Markets change, which is why the backtest reruns every month and drops setups that stop working.
