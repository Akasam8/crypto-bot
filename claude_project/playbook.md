# Playbook

This is the bot's research on how these coins actually behave. Every number comes from the price history, nothing is a guess.

## The fee hurdle

A round trip costs about 1.20% in fees and slippage. The typical move (median, ignoring direction) is 0.46% over 1 hour, 0.91% over 4 hours and 2.47% over 24 hours. Short holds start in a hole, because the typical 1 to 2 hour move is about the same size as the fees.

## Time of day (UK time)

Busiest hours: 15:00 (0.97% avg move), 14:00 (0.86% avg move), 16:00 (0.85% avg move). Quietest: 04:00 (0.61%), 11:00 (0.61%), 10:00 (0.59%).
Best average hour 22:00 (+6.8 basis points), worst 19:00 (-3.4). These drifts are tiny next to the fees, which is why time of day alone rarely works.

## Weekends

Weekend hours move 0.80x as much as weekday hours, so weekends are quieter.

## Alts and BTC

Alts move with BTC in the same hour (average correlation 0.62, average beta 1.31, so a 1% BTC move comes with about a 1.3% alt move). BTC's move one hour earlier barely predicts the next alt hour (correlation -0.008), so the catch up mostly happens inside the same hour.

## After big BTC days

BTC up 5%+ in a day (34 times): BTC's next day averaged -0.44%, up 41% of the time; alts averaged +0.06%.
BTC down 5%+ in a day (25 times): BTC's next day averaged +0.57%, up 48% of the time; alts averaged +0.97%.

## Market regimes

BTC above its 50 day average: yes: average 24h move +0.07%, up 47% of days, a random 24h long after fees -1.12%.
BTC above its 50 day average: no: average 24h move +0.03%, up 47% of days, a random 24h long after fees -1.16%.
high volatility: yes: average 24h move +0.18%, up 47% of days, a random 24h long after fees -1.01%.
high volatility: no: average 24h move -0.04%, up 47% of days, a random 24h long after fees -1.23%.

## Coins

| Coin | Yearly volatility | Return over the period | Daily volume (USD m) |
|---|---|---|---|
| BTC-USD | 47% | +124% | 412.6 |
| ETH-USD | 64% | +25% | 195.2 |
| ZEC-USD | 123% | +4554% | 106.1 |
| XRP-USD | 80% | +108% | 63.1 |
| SOL-USD | 85% | +142% | 53.4 |
| NEAR-USD | 110% | +210% | 41.0 |
| SUI-USD | 108% | +107% | 16.7 |
| QNT-USD | 95% | +97% | 12.5 |
| ADA-USD | 92% | -34% | 9.9 |
| LINK-USD | 86% | +6% | 7.8 |
| UNI-USD | 104% | +71% | 7.3 |
| LTC-USD | 75% | -19% | 7.2 |
| DOGE-USD | 92% | +12% | 6.2 |
| XLM-USD | 88% | +40% | 6.1 |
| HBAR-USD | 99% | +41% | 6.0 |
| AERO-USD | 134% | +587% | 5.9 |
| AVAX-USD | 93% | -23% | 5.7 |
| ONDO-USD | 118% | +49% | 5.6 |
| ZRO-USD | 121% | -55% | 4.6 |
| INJ-USD | 113% | -52% | 3.9 |
| AAVE-USD | 96% | +61% | 3.7 |
| FET-USD | 120% | -53% | 3.5 |
| STRK-USD | 138% | -98% | 3.4 |
| FIL-USD | 102% | -77% | 2.8 |
| BCH-USD | 81% | +22% | 2.5 |

## Verdict from the latest backtest

**Nothing survived.** None of the 6 setup families made money after fees on data they weren't built on, in a way that clearly beat random entries. The bot will stay idle and only send daily summaries. That's an honest result, and it means the £100 stays in your pocket.


No setup survived the latest backtest, so there are no live strategy cards. The scanner stays idle until the monthly rerun finds something.

## Risk rules the bot enforces

1. Never risk more than 2.0% of the pot on one trade. Position size comes from the stop distance, capped at £40.
2. At most 2 positions open and 3 new trades a day.
3. Stop for the day after losing £5.
4. Halt completely if the pot falls to £80, until you turn it back on.
5. Spot only, long only. No leverage, margin, futures or perpetuals, ever.
