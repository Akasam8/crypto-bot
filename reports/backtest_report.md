# Backtest report

**Nothing survived.** None of the 6 setup families made money after fees on data they weren't built on, in a way that clearly beat random entries. The bot will stay idle and only send daily summaries. That's an honest result, and it means the £100 stays in your pocket.

Data: 25 coins, hourly candles from 2023-11-01 to 2026-10-31. Setups were picked on 2023-11-09 to 2025-10-30 and judged on 2025-10-31 to 2026-10-31, which they never saw. 555 setup variations were tried in total, so some will look good on training data by pure luck. That's why only the unseen year and the walk forward periods count.

Every trade pays 0.5% Coinbase taker fee plus 0.1% slippage on the way in and again on the way out, so a round trip costs about 1.20%. A trade has to move that much just to break even.

For comparison, over the test year simply holding BTC returned -29.71% and holding all the coins equally returned -14.87%.

## Results by setup

| Setup | Test trades | Win rate | Avg per trade after fees | Profit factor | Beat random? | Walk forward | Verdict |
|---|---|---|---|---|---|---|---|
| Breakout with volume | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Oversold bounce in a BTC uptrend | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Volume spike continuation | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Alt catching up to BTC | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Trend pullback | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |
| Time of day entry | 0 | n/a | n/a | n/a | n/a | n/a | failed on training |

## Breakout with volume

Failed: nothing was profitable after fees even on the training data.

## Oversold bounce in a BTC uptrend

Failed: nothing was profitable after fees even on the training data.

## Volume spike continuation

Failed: nothing was profitable after fees even on the training data.

## Alt catching up to BTC

Failed: nothing was profitable after fees even on the training data.

## Trend pullback

Failed: nothing was profitable after fees even on the training data.

## Time of day entry

Failed: nothing was profitable after fees even on the training data.

## Caveats

Trades on different coins often fire at the same time because crypto moves together, so the real number of independent bets is smaller than the trade count. The live bot also caps open positions, so it can't take every signal the backtest took. Spreads and fills on small coins can be worse than the slippage assumed here. Markets change, which is why the backtest reruns every month and drops setups that stop working.
