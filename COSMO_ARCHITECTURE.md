# Cosmo architecture brief

## Goal
Cosmo is not a single script. It is an always-on reasoning organism with a persistent ledger, event-driven triage, and specialized swarms that wake only when a signal is strong enough to matter.

## Core layers
1. Ledger / Pillar 0
   - Stores theses, evidence, and kill conditions.
   - Gives the system memory that survives across sessions.
   - Prevents zombie ideas from being resurrected without explicit re-evaluation.

2. Forager layer
   - Lightweight data collectors that poll feeds such as SEC filings, news, and market data.
   - They write raw observations into the ledger and publish simple events.

3. Triage orchestrator
   - Evaluates incoming signals for source trust, materiality, prediction error, and convergence.
   - Decides whether the event is merely noise or worthy of waking the research swarm.

4. Specialized swarms
   - Bottleneck swarm: structural thesis plays such as AI supply-chain bottlenecks.
   - Biotech binary swarm: FDA and catalyst-date trades with hard-risk checks.
   - Cascade swarm: geopolitical and event-propagation plays.
   - Microcap shock swarm: high-velocity squeeze and float-shock situations.

5. Human-in-the-loop layer
   - The human can override, annotate, and add context.
   - Every override is recorded as a correction to the ledger so the system can learn from human judgment over time.

## First implementation slice
This repository now includes:
- a lightweight sqlite-backed ledger in cosmo/ledger.py
- a simple triage orchestrator in cosmo/triage.py
- tests that prove the model can store thesis state and wake the swarm when a signal converges

## Immediate next steps
1. Add a simple event bus abstraction so foragers can publish events asynchronously.
2. Add a research-agent wrapper that consumes a high-signal event and writes a new thesis into the ledger.
3. Add a human override and scoring layer so outcomes can be graded and used to tune the triage thresholds.
