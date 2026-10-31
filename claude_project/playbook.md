# Playbook

This is the bot's research on how these coins actually behave. Every number comes from the price history, nothing is a guess.

## The fee hurdle

A round trip costs about 1.20% in fees and slippage. The typical move (median, ignoring direction) is 0.42% over 1 hour, 0.85% over 4 hours and 2.32% over 24 hours. Short holds start in a hole, because the typical 1 to 2 hour move is about the same size as the fees.

## Time of day (UK time)

Busiest hours: 15:00 (0.94% avg move), 16:00 (0.88% avg move), 14:00 (0.83% avg move). Quietest: 07:00 (0.57%), 11:00 (0.56%), 10:00 (0.56%).
Best average hour 21:00 (+9.1 basis points), worst 23:00 (-10.6). These drifts are tiny next to the fees, which is why time of day alone rarely works.

## Weekends

Weekend hours move 0.80x as much as weekday hours, so weekends are quieter.

## Alts and BTC

Alts move with BTC in the same hour (average correlation 0.64, average beta 1.31, so a 1% BTC move comes with about a 1.3% alt move). BTC's move one hour earlier barely predicts the next alt hour (correlation 0.002), so the catch up mostly happens inside the same hour.

## After big BTC days

BTC up 5%+ in a day (11 times): BTC's next day averaged +0.55%, up 36% of the time; alts averaged +1.69%.
BTC down 5%+ in a day (6 times): BTC's next day averaged +0.85%, up 33% of the time; alts averaged +1.04%.

## Market regimes

BTC above its 50 day average: yes: average 24h move +0.51%, up 50% of days, a random 24h long after fees -0.69%.
BTC above its 50 day average: no: average 24h move -0.11%, up 47% of days, a random 24h long after fees -1.30%.
high volatility: yes: average 24h move +0.79%, up 52% of days, a random 24h long after fees -0.41%.
high volatility: no: average 24h move +0.10%, up 47% of days, a random 24h long after fees -1.09%.

## Coins

| Coin | Yearly volatility | Return over the period | Daily volume (USD m) |
|---|---|---|---|
| BTC-USD | 43% | -29% | 403.8 |
| ETH-USD | 59% | -41% | 195.2 |
| ZEC-USD | 134% | +233% | 98.1 |
| XRP-USD | 64% | -50% | 61.9 |
| SOL-USD | 65% | -48% | 49.3 |
| NEAR-USD | 105% | +116% | 41.0 |
| SUI-USD | 86% | -61% | 15.5 |
| QNT-USD | 105% | +155% | 12.5 |
| ADA-USD | 76% | -68% | 9.9 |
| PUMP-USD | 124% | +0% | 7.9 |
| LINK-USD | 69% | -31% | 7.3 |
| UNI-USD | 97% | +24% | 7.2 |
| LTC-USD | 62% | -42% | 7.2 |
| TAO-USD | 96% | -51% | 6.5 |
| DOGE-USD | 68% | -59% | 6.2 |
| XLM-USD | 80% | -43% | 6.1 |
| HBAR-USD | 71% | -63% | 6.0 |
| VVV-USD | 149% | +1437% | 6.0 |
| AERO-USD | 106% | -41% | 5.9 |
| ENA-USD | 111% | -51% | 5.8 |
| AVAX-USD | 72% | -52% | 5.6 |
| ONDO-USD | 94% | -39% | 5.4 |
| ZRO-USD | 118% | +17% | 4.6 |
| INJ-USD | 103% | -1% | 3.9 |
| WLD-USD | 117% | -49% | 3.4 |

## Verdict from the latest backtest

**Nothing is proven.** None of the 8 setup families made money after fees on data they weren't built on, in a way that clearly beat random entries. Live trading stays off. Test mode will still trade the best 3 unproven setups with fake money, so you can watch how they do against real prices and fees. None of them can go live.


No setup is proven, so nothing can trade live. See the test mode setups in the backtest report for what's being paper traded.

## Risk rules the bot enforces

1. Never risk more than 2.0% of the pot on one trade. Position size comes from the stop distance, capped at £40.
2. At most 2 positions open and 3 new trades a day.
3. Stop for the day after losing £5.
4. Halt completely if the pot falls to £80, until you turn it back on.
5. Spot only, long only. No leverage, margin, futures or perpetuals, ever.
