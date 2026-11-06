# Backtest report

**Nothing is proven.** None of the 8 setup families made money after fees on data they weren't built on, in a way that clearly beat random entries. Live trading stays off. Test mode will still trade the best 3 unproven setups with fake money, so you can watch how they do against real prices and fees. None of them can go live.

Data: 25 coins, hourly candles from 2025-11-06 to 2026-11-06. Setups were picked on 2025-11-15 to 2026-06-29 and judged on 2026-07-06 to 2026-11-06, which they never saw. 252 setup variations were tried in total, so some will look good on training data by pure luck. That's why only the unseen year and the walk forward periods count.

Every trade pays 0.5% Coinbase taker fee plus 0.1% slippage on the way in and again on the way out, so a round trip costs about 1.20%. A trade has to move that much just to break even.

For comparison, over the test period simply holding BTC returned +18.88% and holding all the coins equally returned +49.35%.

## Results by setup

| Setup | Test trades | Win rate | Avg per trade after fees | Profit factor | Beat random? | Walk forward | Verdict |
|---|---|---|---|---|---|---|---|
| Breakout with volume | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Oversold bounce in a BTC uptrend | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Volume spike continuation | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Alt catching up to BTC | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Trend pullback | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Trend breakout | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Moving average cross | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Momentum leader | 80 | 44% | +4.52% | 1.86 | no | 1/2 positive | failed |

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

Failed: nothing was profitable after fees on the training data.

## Moving average cross

Failed: nothing was profitable after fees on the training data.

## Momentum leader

Best version on training data: `momentum_leader[top=3]|168h|timed`. Rule: Once a day, buy a coin that's in the top 3 for 7 day gains, up on the week, while BTC is above its 50 day average. Hold up to 168h, no target, stop about 2x expected move, otherwise sell at the max hold time.

Training: 62 trades, +2.071% per trade, win rate 44%.

Unseen test period: 80 trades, +4.518% per trade after fees (+4.882% if entries filled as maker), win rate 44%, average win +22.28%, average loss -9.30%, profit factor 1.86, worst losing streak 8, 50% of months positive. Exits: target 0%, stop 16%, time 84%.

The same trades slid to random times averaged +3.620%. To pass, the setup had to beat +16.506%, which only 2.5% of random runs reach. Share of random runs that did at least as well as the setup: 28.2%.

By market regime: BTC above 50d avg: yes: 80 trades, +4.518%; high volatility: yes: 32 trades, +10.329%; high volatility: no: 48 trades, +0.643%.

Walk forward inside the training period (picked on 4 months, tested on the next 2): ? to ?: nothing passed training; 2026-05-15 to 2026-06-29: 10 trades, +1.425% per trade, +0.747% vs the 75th percentile of random timing.

**Failed because:** didn't clearly beat random entries (4.52% vs 16.51% for the top 2.5% of random runs); only 50% of test months were positive; walk forward: only 1 of 2 unseen periods made money and beat random timing.

## Test mode setups (unproven)

These looked best over the whole year, which is exactly the data they were picked on, so their numbers are flattering. Test mode trades them with fake money to find out if they hold up on new prices.

**Momentum leader**: Once a day, buy a coin that's in the top 3 for 7 day gains, up on the week, while BTC is above its 50 day average. Hold up to 168h, no target, stop about 2x expected move, otherwise sell at the max hold time. Past year: 142 trades, 44% wins, +3.45% per trade after fees. Last 4 months alone: 80 trades, +4.52% per trade.

**Trend breakout**: Price breaks above its highest point of the last 10 days while above its 20 day average, with BTC above its 50 day average. Hold up to 72h, no target, stop about 2x expected move, otherwise sell at the max hold time. Past year: 341 trades, 45% wins, +1.46% per trade after fees. Last 4 months alone: 172 trades, +3.18% per trade.

**Moving average cross**: The 2 day average crosses above the 10 day average. Hold up to 168h, no target, stop about 2x expected move, otherwise sell at the max hold time. Past year: 489 trades, 42% wins, +0.92% per trade after fees. Last 4 months alone: 160 trades, +4.46% per trade.

## Caveats

Trades on different coins often fire at the same time because crypto moves together, so the real number of independent bets is smaller than the trade count. The live bot also caps open positions, so it can't take every signal the backtest took. Spreads and fills on small coins can be worse than the slippage assumed here. Markets change, which is why the backtest reruns every month and drops setups that stop working.
