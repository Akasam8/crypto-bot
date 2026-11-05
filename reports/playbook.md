# Playbook

This is the bot's research on how these coins actually behave. Every number comes from the price history, nothing is a guess.

## The fee hurdle

A round trip costs about 1.20% in fees and slippage. The typical move (median, ignoring direction) is 0.42% over 1 hour, 0.85% over 4 hours and 2.28% over 24 hours. Short holds start in a hole, because the typical 1 to 2 hour move is about the same size as the fees.

## Time of day (UK time)

Busiest hours: 15:00 (0.93% avg move), 16:00 (0.86% avg move), 14:00 (0.83% avg move). Quietest: 07:00 (0.56%), 11:00 (0.55%), 10:00 (0.55%).
Best average hour 21:00 (+9.1 basis points), worst 23:00 (-11.3). These drifts are tiny next to the fees, which is why time of day alone rarely works.

## Weekends

Weekend hours move 0.80x as much as weekday hours, so weekends are quieter.

## Alts and BTC

Alts move with BTC in the same hour (average correlation 0.65, average beta 1.30, so a 1% BTC move comes with about a 1.3% alt move). BTC's move one hour earlier barely predicts the next alt hour (correlation 0.006), so the catch up mostly happens inside the same hour.

## After big BTC days

BTC up 5%+ in a day (11 times): BTC's next day averaged +0.55%, up 36% of the time; alts averaged +1.83%.
BTC down 5%+ in a day (7 times): BTC's next day averaged +0.85%, up 33% of the time; alts averaged +0.80%.

## Market regimes

BTC above its 50 day average: yes: average 24h move +0.50%, up 50% of days, a random 24h long after fees -0.70%.
BTC above its 50 day average: no: average 24h move -0.11%, up 45% of days, a random 24h long after fees -1.30%.
high volatility: yes: average 24h move +0.64%, up 50% of days, a random 24h long after fees -0.56%.
high volatility: no: average 24h move +0.17%, up 48% of days, a random 24h long after fees -1.03%.

## Coins

| Coin | Yearly volatility | Return over the period | Daily volume (USD m) |
|---|---|---|---|
| BTC-USD | 43% | -27% | 416.6 |
| ETH-USD | 58% | -35% | 203.3 |
| ZEC-USD | 131% | +148% | 104.8 |
| XRP-USD | 63% | -47% | 61.6 |
| SOL-USD | 64% | -45% | 53.4 |
| NEAR-USD | 104% | +89% | 40.0 |
| SUI-USD | 85% | -58% | 13.8 |
| QNT-USD | 105% | +126% | 10.2 |
| ADA-USD | 76% | -66% | 7.8 |
| LINK-USD | 68% | -30% | 7.3 |
| PUMP-USD | 123% | -4% | 6.8 |
| UNI-USD | 97% | +25% | 6.8 |
| ENA-USD | 110% | -52% | 6.4 |
| LTC-USD | 61% | -42% | 6.3 |
| TAO-USD | 95% | -45% | 5.8 |
| VVV-USD | 149% | +1455% | 5.8 |
| DOGE-USD | 67% | -57% | 5.7 |
| XLM-USD | 79% | -45% | 5.5 |
| HBAR-USD | 71% | -61% | 5.4 |
| AERO-USD | 106% | -35% | 5.3 |
| ONDO-USD | 94% | -40% | 5.2 |
| AVAX-USD | 71% | -51% | 4.4 |
| INJ-USD | 102% | +20% | 4.0 |
| PEPE-USD | 93% | -16% | 3.4 |
| ZRO-USD | 118% | +12% | 3.4 |

## Verdict from the latest backtest

**Nothing is proven.** None of the 8 setup families made money after fees on data they weren't built on, in a way that clearly beat random entries. Live trading stays off. Test mode will still trade the best 3 unproven setups with fake money, so you can watch how they do against real prices and fees. None of them can go live.


No setup is proven, so nothing can trade live. See the test mode setups in the backtest report for what's being paper traded.

## Risk rules the bot enforces

1. Never risk more than 2.0% of the pot on one trade. Position size comes from the stop distance, capped at £40.
2. At most 2 positions open and 3 new trades a day.
3. Stop for the day after losing £5.
4. Halt completely if the pot falls to £80, until you turn it back on.
5. Spot only, long only. No leverage, margin, futures or perpetuals, ever.
