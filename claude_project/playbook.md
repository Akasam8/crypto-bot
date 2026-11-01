# Playbook

This is the bot's research on how these coins actually behave. Every number comes from the price history, nothing is a guess.

## The fee hurdle

A round trip costs about 1.20% in fees and slippage. The typical move (median, ignoring direction) is 0.43% over 1 hour, 0.87% over 4 hours and 2.35% over 24 hours. Short holds start in a hole, because the typical 1 to 2 hour move is about the same size as the fees.

## Time of day (UK time)

Busiest hours: 15:00 (0.96% avg move), 16:00 (0.89% avg move), 14:00 (0.86% avg move). Quietest: 11:00 (0.59%), 07:00 (0.58%), 10:00 (0.58%).
Best average hour 21:00 (+8.8 basis points), worst 23:00 (-9.6). These drifts are tiny next to the fees, which is why time of day alone rarely works.

## Weekends

Weekend hours move 0.80x as much as weekday hours, so weekends are quieter.

## Alts and BTC

Alts move with BTC in the same hour (average correlation 0.63, average beta 1.30, so a 1% BTC move comes with about a 1.3% alt move). BTC's move one hour earlier barely predicts the next alt hour (correlation 0.003), so the catch up mostly happens inside the same hour.

## After big BTC days

BTC up 5%+ in a day (11 times): BTC's next day averaged +0.55%, up 36% of the time; alts averaged +1.70%.
BTC down 5%+ in a day (6 times): BTC's next day averaged +0.85%, up 33% of the time; alts averaged +0.88%.

## Market regimes

BTC above its 50 day average: yes: average 24h move +0.52%, up 49% of days, a random 24h long after fees -0.68%.
BTC above its 50 day average: no: average 24h move -0.15%, up 46% of days, a random 24h long after fees -1.34%.
high volatility: yes: average 24h move +0.81%, up 52% of days, a random 24h long after fees -0.39%.
high volatility: no: average 24h move +0.10%, up 47% of days, a random 24h long after fees -1.10%.

## Coins

| Coin | Yearly volatility | Return over the period | Daily volume (USD m) |
|---|---|---|---|
| BTC-USD | 43% | -29% | 403.8 |
| ETH-USD | 59% | -41% | 195.2 |
| ZEC-USD | 133% | +195% | 98.1 |
| XRP-USD | 64% | -50% | 61.9 |
| SOL-USD | 65% | -49% | 53.4 |
| NEAR-USD | 105% | +104% | 40.0 |
| SUI-USD | 86% | -62% | 15.5 |
| QNT-USD | 105% | +147% | 11.7 |
| ADA-USD | 76% | -68% | 9.9 |
| PUMP-USD | 124% | -5% | 7.9 |
| LINK-USD | 69% | -33% | 7.8 |
| UNI-USD | 97% | +24% | 7.2 |
| LTC-USD | 62% | -43% | 7.2 |
| TAO-USD | 96% | -55% | 6.5 |
| DOGE-USD | 68% | -60% | 6.2 |
| XLM-USD | 80% | -45% | 6.1 |
| HBAR-USD | 71% | -64% | 6.0 |
| AERO-USD | 106% | -40% | 5.8 |
| AVAX-USD | 72% | -53% | 5.6 |
| ENA-USD | 111% | -52% | 5.5 |
| VVV-USD | 149% | +1349% | 5.5 |
| ONDO-USD | 94% | -41% | 5.4 |
| ZRO-USD | 118% | +16% | 4.3 |
| INJ-USD | 103% | -8% | 3.9 |
| STRK-USD | 166% | -59% | 3.4 |

## Verdict from the latest backtest

**Nothing is proven.** None of the 8 setup families made money after fees on data they weren't built on, in a way that clearly beat random entries. Live trading stays off. Test mode will still trade the best 3 unproven setups with fake money, so you can watch how they do against real prices and fees. None of them can go live.


No setup is proven, so nothing can trade live. See the test mode setups in the backtest report for what's being paper traded.

## Risk rules the bot enforces

1. Never risk more than 2.0% of the pot on one trade. Position size comes from the stop distance, capped at £40.
2. At most 2 positions open and 3 new trades a day.
3. Stop for the day after losing £5.
4. Halt completely if the pot falls to £80, until you turn it back on.
5. Spot only, long only. No leverage, margin, futures or perpetuals, ever.
