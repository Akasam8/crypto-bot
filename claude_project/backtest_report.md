# Backtest report

**Nothing is proven.** None of the 8 setup families made money after fees on data they weren't built on, in a way that clearly beat random entries. Live trading stays off. Test mode will still trade the best 3 unproven setups with fake money, so you can watch how they do against real prices and fees. None of them can go live.

Data: 25 coins, hourly candles from 2025-11-05 to 2026-11-05. Setups were picked on 2025-11-14 to 2026-06-28 and judged on 2026-07-05 to 2026-11-05, which they never saw. 252 setup variations were tried in total, so some will look good on training data by pure luck. That's why only the unseen year and the walk forward periods count.

Every trade pays 0.5% Coinbase taker fee plus 0.1% slippage on the way in and again on the way out, so a round trip costs about 1.20%. A trade has to move that much just to break even.

For comparison, over the test period simply holding BTC returned +21.61% and holding all the coins equally returned +50.61%.

## Results by setup

| Setup | Test trades | Win rate | Avg per trade after fees | Profit factor | Beat random? | Walk forward | Verdict |
|---|---|---|---|---|---|---|---|
| Breakout with volume | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Oversold bounce in a BTC uptrend | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Volume spike continuation | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Alt catching up to BTC | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Trend pullback | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Trend breakout | 141 | 45% | +3.32% | 1.98 | no | 0/2 positive | failed |
| Moving average cross | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Momentum leader | 76 | 49% | +5.15% | 1.95 | no | 0/2 positive | failed |

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

Training: 125 trades, +0.006% per trade, win rate 36%.

Unseen test period: 141 trades, +3.322% per trade after fees (+3.683% if entries filled as maker), win rate 45%, average win +15.02%, average loss -6.13%, profit factor 1.98, worst losing streak 8, 50% of months positive. Exits: target 0%, stop 9%, time 91%.

The same trades slid to random times averaged +0.228%. To pass, the setup had to beat +5.434%, which only 2.5% of random runs reach. Share of random runs that did at least as well as the setup: 8.0%.

By market regime: BTC above 50d avg: yes: 141 trades, +3.322%; high volatility: yes: 73 trades, +3.177%; high volatility: no: 68 trades, +3.478%.

Walk forward inside the training period (picked on 4 months, tested on the next 2): 2026-03-14 to 2026-05-14: 123 trades, -1.041% per trade, -1.521% vs the 75th percentile of random timing; 2026-05-14 to 2026-06-28: 11 trades, -3.805% per trade, -4.147% vs the 75th percentile of random timing.

**Failed because:** didn't clearly beat random entries (3.32% vs 5.43% for the top 2.5% of random runs); only 50% of test months were positive; walk forward: only 0 of 2 unseen periods made money and beat random timing.

## Moving average cross

Failed: nothing was profitable after fees on the training data.

## Momentum leader

Best version on training data: `momentum_leader[top=3]|168h|timed`. Rule: Once a day, buy a coin that's in the top 3 for 7 day gains, up on the week, while BTC is above its 50 day average. Hold up to 168h, no target, stop about 2x expected move, otherwise sell at the max hold time.

Training: 63 trades, +2.867% per trade, win rate 46%.

Unseen test period: 76 trades, +5.155% per trade after fees (+5.522% if entries filled as maker), win rate 49%, average win +21.75%, average loss -10.58%, profit factor 1.95, worst losing streak 7, 50% of months positive. Exits: target 0%, stop 20%, time 80%.

The same trades slid to random times averaged +3.874%. To pass, the setup had to beat +17.706%, which only 2.5% of random runs reach. Share of random runs that did at least as well as the setup: 28.2%.

By market regime: BTC above 50d avg: yes: 76 trades, +5.155%; high volatility: yes: 31 trades, +11.158%; high volatility: no: 45 trades, +1.019%.

Walk forward inside the training period (picked on 4 months, tested on the next 2): ? to ?: nothing passed training; 2026-05-14 to 2026-06-28: 11 trades, -0.160% per trade, -0.318% vs the 75th percentile of random timing.

**Failed because:** didn't clearly beat random entries (5.15% vs 17.71% for the top 2.5% of random runs); only 50% of test months were positive; walk forward: only 0 of 2 unseen periods made money and beat random timing.

## Test mode setups (unproven)

These looked best over the whole year, which is exactly the data they were picked on, so their numbers are flattering. Test mode trades them with fake money to find out if they hold up on new prices.

**Trend breakout**: Price breaks above its highest point of the last 20 days while above its 20 day average. Hold up to 168h, no target, stop about 2x expected move, otherwise sell at the max hold time. Past year: 242 trades, 43% wins, +3.02% per trade after fees. Last 4 months alone: 105 trades, +8.08% per trade.

**Momentum leader**: Once a day, buy a coin that's in the top 3 for 7 day gains, up on the week, while BTC is above its 50 day average. Hold up to 168h, target about 2x expected move, stop about 1x. Past year: 156 trades, 48% wins, +2.63% per trade after fees. Last 4 months alone: 85 trades, +3.25% per trade.

**Moving average cross**: The 5 day average crosses above the 20 day average. Hold up to 168h, no target, stop about 2x expected move, otherwise sell at the max hold time. Past year: 245 trades, 43% wins, +1.85% per trade after fees. Last 4 months alone: 82 trades, +8.19% per trade.

## Caveats

Trades on different coins often fire at the same time because crypto moves together, so the real number of independent bets is smaller than the trade count. The live bot also caps open positions, so it can't take every signal the backtest took. Spreads and fills on small coins can be worse than the slippage assumed here. Markets change, which is why the backtest reruns every month and drops setups that stop working.
