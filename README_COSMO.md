# Cosmo local runtime

This is the first local, persistent runtime for the Cosmo system.

## What is built
- A persistent SQLite ledger for theses, evidence, kill conditions, raw events, and proposals.
- A triage engine that decides whether an incoming event is strong enough to wake a specialist swarm.
- A runtime entry point that can be launched locally and shows visible output.
- A constitutional governance layer for proposals, votes, and graveyard entries.

## How it works
1. The runtime starts and creates a local database at the repository root: cosmo.sqlite.
2. It ingests a sample or real event.
3. It writes the event into the ledger.
4. It scores the event through the triage engine.
5. If the event passes the threshold, it routes to a swarm such as bottleneck, biotech, cascade, or general.

## Files
- cosmo/ledger.py: persistent memory and event storage
- cosmo/triage.py: signal scoring and routing
- cosmo/forager.py: ingestion + triage pipeline
- cosmo/constitution.py: governance and proposal ledger
- cosmo/runner.py: local runtime entry point
- schema/schema.sql: constitutional schema

## Run it locally
From the repository root:

```powershell
python cosmo/runner.py
```

You will see startup output and a processed event in the terminal.

## Why this matters
This is not a toy script. It is the local substrate that can be shared with Claude, Gemini, and other agents so they all read and write to the same persistent reasoning environment.
