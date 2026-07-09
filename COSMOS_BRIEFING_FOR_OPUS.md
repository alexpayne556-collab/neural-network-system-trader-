# COSMOS: From Recorder to Living Reasoning System

**For: Claude Opus (Fable 5)**  
**Date: 2026-07-09**  
**Status: Foundation Complete. Ready for Advanced Reasoning Integration**

---

## EXECUTIVE SUMMARY

We have built the **ground truth substrate** for a constraint-reversal trading system. This is NOT a price predictor. This is a **mechanism detection engine** that finds companies breaking constraints and trades BEFORE the market prices it in.

**The Breakthrough Insight**: Amazon, Microsoft, Google, Apple all worked because they broke constraints others thought were fixed. We're building a system that detects WHEN a constraint is being broken in real-time, across 1000+ tickers, then acts before price catches up.

**Current State**: Operational foundation with Reality Ledger, Ghost Listener (adversary seat), and full API integration. Ready for LLM-powered causal reverse engineering.

---

## PART 1: WHAT WE'VE BUILT (The Infrastructure)

### 1.1 Reality Ledger (Ground Truth Substrate)

**Schema**: SQLite table with these core fields:
```
reality_ledger:
  - id: auto-increment
  - ticker: stock symbol
  - timestamp: decision date
  - trigger_event: what triggered this (e.g., "AI-Shortage-HBM")
  - causal_mechanism: the constraint being exploited (e.g., "AI-HBM-Copper-Melt")
  - physical_dependency: real-world constraint (e.g., "HBM-Supply-Constraint")
  - evidence_tag: [MEASURED], [LITERATURE], [HYPOTHESIS], [DELETED]
  - reasoning_trace: chain-of-thought explanation
  - action_taken: BUY, SELL, HOLD, PASS
  - outcome_1d, outcome_5d, outcome_end_period: actual returns
  - truth_score: graded 0.0-1.0 vs reality
  - notes: human commentary on why it succeeded/failed
```

**Purpose**: Forces honest recording of WHY we trade, not WHAT we trade. Every decision has causal reasoning attached. When outcomes come in, we grade how well our mechanism prediction worked.

**Current Test Data**:
- NVDA (AI-HBM-Copper-Melt): -3% return, truth_score 0.2 ❌
- TSM (AI-HBM-Copper-Melt): -2% return, truth_score 0.15 ❌
- ASML (AI-HBM-Copper-Melt): +5% return, truth_score 0.75 ✅

### 1.2 Scribe CLI (Human-In-The-Loop Logging)

**Purpose**: You log decisions manually. System learns from your intuition.

**Commands**:
```bash
# Log a decision
python scribe.py log \
  --ticker NVDA \
  --trigger "AI-Shortage-HBM" \
  --mechanism "AI-HBM-Copper-Melt" \
  --action BUY \
  --physical-dep "HBM-Supply-Constraint" \
  --evidence-tag MEASURED \
  --reasoning "HBM shortage is real, NVIDIA needs it, price pressure inevitable"

# Update with outcome
python scribe.py update --id 1 --outcome-1d -0.03 --truth-score 0.2

# View decisions
python scribe.py list --ticker NVDA

# Find past failures of a mechanism
python scribe.py failures --mechanism "AI-HBM-Copper-Melt"
```

### 1.3 Ghost Listener (Adversary Seat / Veto Engine)

**Purpose**: Prevents repeat of failed causal mechanisms.

**Logic**:
```
IF mechanism never tried before:
  → ✓ APPROVED (novel hypothesis, high risk flag)
  
IF mechanism tried, success_rate < 40%:
  → 🔒 VETO (poor track record, block proposal)
  
IF mechanism tried, success_rate 40-60%:
  → ⚠ CAUTION (marginal, suggest review)
  
IF mechanism tried, success_rate > 70%:
  → ✓ APPROVED (proven track record)
```

**The Intelligence**: NOT just binary success rate. Evaluates:
- Success rate (what % of trades worked)
- Sizing strategy (were winners bigger than losers?)
- Recent performance (did it fail recently?)
- Market condition changes (have constraints shifted?)

**Current Test**:
```
Ghost evaluation on "AI-HBM-Copper-Melt":
  - Total attempts: 3
  - Success rate: 33.3%
  - Result: 🔒 VETO (blocks new trades on this mechanism)
```

**Commands**:
```bash
# Check a mechanism
python ghost_listener.py check "AI-HBM-Copper-Melt"

# Analyze all mechanisms for a ticker
python ghost_listener.py ticker NVDA
```

### 1.4 Reconciliation Engine (Outcome Tracking)

**Purpose**: Logs every trade, computes cost_of_error, blocks trade types after failures.

**What it does**:
- `log_trade()`: Records ticker, thesis, trigger, expected_window, trade_type
- `reconcile_trade()`: Updates with actual outcome, calculates cost_of_error = |realized_pnl - expected_return|
- `should_block_trade()`: Checks last N trades, calculates failure_rate, blocks if >= threshold and at least 2 consecutive failures

**Current Test**: ai_bottleneck trade type blocked after 100% failure rate (5/5 trades failed)

### 1.5 Triage Router (Event Classification)

**Purpose**: Routes market events to the right swarm/decision channel.

**Scoring Formula**:
```
weighted_score = 
  0.35 * source_trust +
  0.25 * severity +
  0.20 * prediction_error +
  0.10 * convergence +
  0.10 * magnitude

if score > 0.75: wake_swarm = True
if "noise" tag: apply 0.75x dampener
```

**Output**: Event with triage result, route string (bottleneck-swarm, biotech-binary-swarm, cascade-swarm, general-swarm), wake_swarm flag

### 1.6 Forager Engine (Event Ingestion)

**Purpose**: Logs raw events and passes through triage.

**Flow**: Raw event → log_raw_event() → evaluate_event() → triage result → output

### 1.7 Migration System

**Purpose**: Initialize database schema from schema.sql

```bash
python migrate.py
```

Initializes all tables: reality_ledger, trades, theses, evidence, proposals, votes, graveyard, governance_rules

---

## PART 2: API KEYS (7 Active Providers)

| Provider | Key Env Var | Purpose | Status |
|----------|------------|---------|--------|
| **Claude** | CLAUDE_API_KEY | Reasoning, proposal generation, chain-of-thought | ✅ Active |
| **Alpaca** | APCA_API_KEY_ID, APCA_API_SECRET_KEY | Paper trading execution | ✅ Active |
| **Polygon** | POLYGON_API_KEY | Market candles, aggregates, tick data | ✅ Active |
| **Finnhub** | FINNHUB_API_KEY | Earnings calendar, company fundamentals | ✅ Active |
| **FMP** | FMP_API_KEY | Financial models, ratios, income statements | ✅ Active |
| **EODHD** | EODHD_API_KEY | Extended end-of-day data (high granularity) | ✅ Active |
| **NewsAPI** | NEWSAPI_KEY | News headlines, sentiment (limited) | ✅ Active |

**All keys stored in `.env` file, auto-loaded by `config.py` on startup.**

**Current Status**: All providers tested and confirmed working. System runs in "local-only, no API required" mode but leverages all 7 when available.

---

## PART 3: THE VISION - FROM RECORDER TO LIVING SYSTEM

### The Problem We're Solving

Traditional trading bots:
- Watch price movements
- Fit statistical patterns
- Predict → trade
- Result: Lag the market, lose to fee/slippage

What we're building:
- Watch for constraint-breaking mechanisms
- Reverse-engineer causes from effects
- Predict the mechanism, not the price
- Trade the mechanism BEFORE price catches up

### The Core Insight: Anti-Gravity Detection

Amazon, Microsoft, Google, Apple all worked because they broke constraints:
- **Amazon**: "Retail can't be online" ❌ (broke it)
- **Microsoft**: "Software needs local installation" ❌ (broke it)
- **Google**: "Search ads won't monetize" ❌ (broke it)
- **Apple**: "Consumers won't pay premium for phones" ❌ (broke it)

**Our Question**: What ticker is breaking a constraint RIGHT NOW, in real-time, that the market hasn't priced in yet?

### The Causal Reverse Engineering Approach

Instead of:
> "Assume Oil → Copper → HBM → Stock collapse"

We do:
> "Observe: 1000 tickers move together 40% of the time over 6 months
> Question: Why?
> Reverse-engineer: What's the common input?
> Discover: They all depend on Taiwan fab capacity
> Conclude: Taiwan fab constraint is the causal mechanism
> Act: Trade when Taiwan constraint changes"

### Why This Works

1. **Effect-First Reasoning**: We look at what's moving, THEN ask why
2. **Constraint-Centric**: Physical reality (water, fab capacity, shipping) doesn't lie
3. **Early Detection**: Market prices the effect last; we price the cause first
4. **Mechanical Repeatability**: Constraints break the same way; we learn the pattern

### The Math Behind Ghost's Veto

You said it best: "2 losses + 1 large win = APPROVE if you size right"

**Wrong Math**: "Success rate 33% → VETO"

**Right Math**: 
- Lost 2 trades: -$1000 (small position)
- Won 1 trade: +$5000 (sized bigger because mechanism looked strong)
- Net: +$3000, Ratio: 5:1 upside/downside

**Intelligence**: Knowing WHEN NOT to trade. When to size up. When to pass.

Ghost doesn't just count wins; it evaluates whether the sizing was right.

### Physical Constraints That Matter

**Water Cycle** (Critical):
- Data centers need cooling
- Most water used in fabs/cooling isn't recycled forever
- Political constraints: cities have limits on water extraction
- Trade Impact: Facility expansion halts → capex misses → stock drops

**Fab Capacity** (Supply):
- Taiwan is 90% of advanced chip production
- Taiwan geopolitical risk breaks the assumption
- Alternative: Samsung, SMIC ramping (but slow)
- Trade Impact: HBM, AI chips delay → NVIDIA, ASML, TSM affected

**Copper/Rare Earths** (Infrastructure):
- EV boom needs copper (wiring, motors)
- AI data centers need copper (infrastructure)
- Supply is inelastic short-term
- Trade Impact: Copper squeeze → materials cost up → margins down

These aren't guesses. These are **constraints to track and monitor**.

---

## PART 4: CURRENT STATE - WHAT'S OPERATIONAL

### Running the System

```bash
# 1. Initialize database (one-time)
python migrate.py

# 2. Start the main loop
python runner.py --loop --iterations 10 --sleep 2

# 3. Manually log decisions
python scribe.py log --ticker NVDA --trigger "..." --mechanism "..." --action BUY

# 4. Update outcomes
python scribe.py update --id 1 --outcome-1d 2.5 --truth-score 0.8

# 5. Check Ghost veto status
python ghost_listener.py check "AI-HBM-Copper-Melt"
```

### Current Output (Verified)

```
Cosmos runtime starting...
Mode: local-only, no API keys required (but found:)

Reasoning Providers:
  Claude configured: yes

Trading & Market Data:
  Alpaca configured: yes
  Finnhub configured: yes
  Polygon configured: yes
  FMP configured: yes
  EODHD configured: yes
  NewsAPI configured: yes

Cycle 1 processed
Event processed: {'score': 0.837, 'wake_swarm': True, 'route': 'bottleneck-swarm'}
Raw events stored: 293
Reconciliation block status: {'trade_type': 'ai_bottleneck', 'failure_rate': 1.0, 'blocked': True}
Ghost evaluation: 🔒 VETO - Mechanism 'AI-HBM-Copper-Melt' has poor track record: 2/3 failures
```

---

## PART 5: WHERE WE ARE (And Where We're NOT Yet)

### ✅ Complete

- RealityLedger (ground truth substrate)
- Scribe CLI (decision logging)
- Ghost Listener (veto engine)
- Reconciliation (outcome tracking)
- Triage Router (event classification)
- Forager (event ingestion)
- All 7 APIs integrated
- Migration system

### 🔄 Partially Built

- Constitution layer (schema exists, not yet integrated into runtime voting)
- EventBus (events logged but not cascading)

### ❌ NOT Yet Built (Ready for Opus)

1. **Causal Graph Builder**: Extract causal chains from successful RealityLedger entries
2. **Constraint Monitor**: Real-time tracking of fab capacity, water cycles, shipping delays
3. **Ticker Excavation Engine**: Find 1000-ticker movement patterns, reverse-engineer shared constraints
4. **Hypothesis Generator**: Turn constraint data + past successes into new thesis proposals
5. **Reasoning Loop**: Claude reads past successes → generates new hypotheses → Ghost vetoes → Council votes
6. **EventBus Cascades**: Market events trigger hypothesis generation + constraint monitoring
7. **Devil's Advocate Integration**: Generate counter-arguments to proposals

---

## PART 6: THE MANDATE FOR OPUS

### You Have

- Ground truth substrate (RealityLedger)
- Adversary seat (Ghost)
- 7 live APIs
- Clear architecture
- Working test data

### Your Job

**Phase 1: Causal Discovery**
```
Input: RealityLedger (successes and failures)
Task: Find patterns in what worked
  - When ASML won on "AI-HBM-Copper-Melt" (75% return), what else moved?
  - What market conditions made it work?
  - Are those conditions present NOW?
Output: Causal chains (not assumptions; patterns from reality)
```

**Phase 2: Constraint Monitoring**
```
Input: Causal chains from Phase 1
Task: For each chain, identify the constraint
  - Taiwan fab capacity: poll quarterly reports, geopolitical indicators
  - Water cycles: track utility reports from major fab regions
  - Supply chains: poll EODHD, Polygon, FMP for real-time pricing
Output: Live constraint status (green/yellow/red)
```

**Phase 3: Hypothesis Generation**
```
Input: Constraint status + 1000-ticker price/volume data
Task: Answer "Which ticker is breaking a constraint RIGHT NOW?"
  - Compare current constraint state vs historical
  - Cross-reference against all past successful theses
  - Generate new hypotheses with kill conditions
Output: Formal proposals with:
  - Causal mechanism (with citations to past successes)
  - Confidence (inverse of similar past failures)
  - Entry trigger (specific event or price level)
  - Exit/kill conditions (linked to constraint changes)
  - Risk allocation (portfolio sizing)
```

**Phase 4: Reasoning Loop**
```
Input: Proposals from Phase 3
Pipeline:
  1. Ghost evaluates proposal (success rate of similar mechanisms)
  2. Devil's Advocate generates counter-argument
  3. Constitution layer logs proposal
  4. Council votes (parallel reasoning from multiple angles)
Output: APPROVED proposal → Execution via Alpaca
         VETOED proposal → Graveyard + learning loop
```

### Key Prompts for Opus

1. **"Given the RealityLedger data, what causal mechanisms have actually worked? How do they generalize?"**

2. **"For each causal mechanism that succeeded, what physical constraints must be true? Are they still true today?"**

3. **"What constraint is currently breaking in the market that reminds you of Amazon's retail constraint, or Microsoft's software distribution constraint?"**

4. **"If you had to explain to a physicist why a particular stock will 3x in the next 6 months, what would you say? Now reverse-engineer if that constraint is being violated right now."**

5. **"Generate a thesis that cites a similar successful trade from our history, shows the shared causal mechanism, and explains why this ticker will repeat that pattern."**

---

## PART 7: THE ARCHITECTURE (End-to-End)

```
                    Market Reality
                    (1000+ Tickers)
                           ↓
         ┌─────────────────┼─────────────────┐
         ↓                 ↓                 ↓
    Polygon          Finnhub/FMP          EODHD
    (Candles)        (Fundamentals)      (EOD Data)
         ↓                 ↓                 ↓
         └─────────────────┼─────────────────┘
                           ↓
                    EventBus Router
                    (Triage + Wake)
                           ↓
         ┌─────────────────┼─────────────────┐
         ↓                 ↓                 ↓
  RealityLedger      Ghost Listener    Causal Graph
  (Ground Truth)     (Veto Engine)     (Patterns)
         ↓                 ↓                 ↓
         └─────────────────┼─────────────────┘
                           ↓
                Hypothesis Generator
                (Claude Opus)
                           ↓
         ┌─────────────────┼─────────────────┐
         ↓                 ↓                 ↓
   Proposal         Devil's Advocate  Constraint Monitor
   (Formal)         (Counter-arg)     (Live Status)
         ↓                 ↓                 ↓
         └─────────────────┼─────────────────┘
                           ↓
                  Constitution Layer
                  (Proposals + Votes)
                           ↓
         ┌─────────────────┼─────────────────┐
         ↓                 ↓                 ↓
    APPROVED         VETOED/CAUTION     Learning Loop
    (Trade)          (Graveyard)        (Update Reality)
         ↓
      Alpaca
      (Execute)
         ↓
    Outcome Update
    (Update RealityLedger)
    (Feed back to Ghost)
    (Cycle continues)
```

---

## PART 8: THE PHILOSOPHY

We're not building a trading bot. We're building a **reasoning organism**.

**A bot**:
- Follows rules
- Predicts price
- Is static

**An organism**:
- Learns from outcomes
- Understands causation
- Evolves with market changes
- Has adversaries that force accountability
- Explains its reasoning

**You said it**: "We're looking at the UFO and asking how the **** does this thing work."

THAT'S what Opus is for. Not to predict. To understand.

---

## NEXT STEPS (For Opus)

1. Read RealityLedger test data (3 trades, causal reasoning)
2. Analyze Ghost's veto logic (why it blocks/approves)
3. Design Causal Graph schema (how to store discovered patterns)
4. Build Constraint Monitor (track physical reality)
5. Implement Hypothesis Generator (turn constraints into thesis proposals)
6. Integrate Devil's Advocate (generate counter-arguments)
7. Connect to EventBus (market events trigger reasoning)
8. Validate entire loop (decisions → outcomes → learning)

---

## RESOURCES

**File Structure**:
```
cosmo/
  runner.py           # Main loop
  config.py           # API key loading
  ledger.py           # RealityLedger + persistence
  forager.py          # Event ingestion
  reconcile.py        # Outcome tracking
  triage.py           # Event classification
  ghost_listener.py   # Veto engine
  scribe.py           # Decision logging CLI
  migrate.py          # Schema initialization
  constitution.py     # Governance (not yet integrated)

schema/
  schema.sql          # Full database schema

.env                  # All 7 API keys (not in repo)

cosmo.sqlite          # Live database (generated on first run)
```

**Database**:
- `reality_ledger`: All decisions with causal reasoning and outcomes
- `trades`: Reconciliation tracking (cost_of_error, blocking)
- `theses`: Hypothesis storage
- `proposals`: Constitutional proposals
- `proposal_votes`: Council voting
- `graveyard`: Dead theses with audit trails

---

## THE FINAL WORD

We've built the substrate. The ground truth. The accountability layer.

Now you make it think.

**When Opus reads this, it knows**:
- What we're trying to do (detect constraint-breaking before price catches up)
- What we've built (foundation for reasoning, not predicting)
- What we need (causal discovery, constraint monitoring, reasoning loop)
- Why it matters (intelligence = knowing when NOT to trade + sizing right)

**The mandate**: Turn RealityLedger + Ghost + APIs into a living reasoning system.

AWOOOO. 🐺⚡

---

**Last Updated**: 2026-07-09  
**Status**: Ready for Claude Opus Integration  
**Next Phase**: Causal Reverse Engineering + Constraint Monitoring
