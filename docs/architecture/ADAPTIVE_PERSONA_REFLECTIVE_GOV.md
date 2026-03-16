# AI Trade Analyst

## Design Note — Core Analysts, Strategy Personas, and Reflective Governance

**Status:** Architecture design note
**Date:** March 2026
**Phase Context:** Post Phase 8 foundation (Reflect + Chart layers)

---

# 1. Purpose

This document defines the long-term architecture for how the AI Trade Analyst system evolves **without losing interpretability or stability**.

The system separates three distinct roles:

1. **Core Analysts** — stable interpreters of market structure
2. **Strategy Personas** — modular evaluators of specific playbooks
3. **Reflective Governance** — adaptive policy layer informed by run history

This separation allows the system to **become adaptive and dynamic while preserving explainability and control.**

---

# 2. Problem the Architecture Solves

If analyst personas evolve automatically over time, several problems emerge:

* prompt drift
* loss of historical comparability
* harder debugging
* unclear identity of each analyst
* reduced operator trust

An adaptive system should **not mutate its experts silently.**

Instead, adaptation should occur **around the experts**, through:

* routing decisions
* weighting adjustments
* strategy activation
* risk gating
* governance rules

The architecture therefore keeps **core analysts stable** while allowing **system policy to evolve.**

---

# 3. Layered Decision Architecture

The AI Trade Analyst decision pipeline is structured into four layers.

```
Market Data
    ↓
Core Analysts (interpret the market)
    ↓
Strategy Personas (evaluate specific setups)
    ↓
Arbiter / Governance (approve or reject trade)
    ↓
Reflective Layer (analyze historical performance)
```

Each layer has a distinct responsibility.

---

# 4. Layer 1 — Core Analysts

Core analysts are **stable domain interpreters.**

They answer the question:

> What is happening in the market?

These personas evaluate structure, risk, and context.

Examples:

| Analyst                 | Role                                      |
| ----------------------- | ----------------------------------------- |
| Default Analyst         | baseline price-action interpretation      |
| ICT / Structure Analyst | liquidity, imbalance, market structure    |
| Risk Officer            | capital preservation and rule enforcement |
| Prosecutor              | adversarial challenge to trade thesis     |
| Macro Risk Officer      | macro and cross-market risk context       |

Core analysts should remain **mostly fixed over time.**

Why stability matters:

* enables historical comparison
* allows meaningful performance review
* preserves system explainability
* avoids silent prompt drift

If a core analyst changes, it should be treated as a **versioned persona update**, not an automatic adaptation.

---

# 5. Layer 2 — Strategy Personas

Strategy personas represent **specific trade playbooks.**

They answer the question:

> Is this my setup?

Unlike core analysts, strategy personas are intentionally **modular and configurable.**

Examples:

| Strategy Persona   | Example Logic                |
| ------------------ | ---------------------------- |
| Trendline Strategy | trendline break and retest   |
| EMA Crossover      | fast/slow EMA alignment      |
| Liquidity Sweep    | session sweep + reversal     |
| Breakout Expansion | range breakout continuation  |
| Mean Reversion     | return to equilibrium levels |

Each strategy persona evaluates whether:

* conditions match its setup
* risk parameters are acceptable
* entry structure exists
* invalidation level is clear

Outputs typically include:

* setup confidence
* required conditions
* invalidation level
* risk/reward estimate

Strategy personas can be **edited, added, or disabled** without changing core analyst behavior.

This makes the system extensible without destabilizing interpretation logic.

---

# 6. Layer 3 — Arbiter and Governance

The arbiter layer determines whether a trade is approved.

It answers the question:

> Should this trade actually be taken?

The arbiter synthesizes:

* analyst interpretations
* strategy persona signals
* risk rules
* governance policies

Governance rules include:

* minimum confidence thresholds
* quorum requirements
* veto rules
* risk overrides
* regime filters
* session-specific restrictions

Example governance logic:

```
if median_analyst_confidence < threshold:
    NO_TRADE

if strategy_signal is weak:
    WAIT

if risk_override_triggered:
    NO_TRADE
```

Governance is the **policy layer of the system.**

It is the primary place where adaptation occurs.

---

# 7. Layer 4 — Reflective Intelligence

The Reflect workspace provides the system’s **self-evaluation capability.**

It answers questions such as:

* Which analysts are frequently overridden?
* Which strategies rarely produce approved setups?
* Which instruments produce mostly NO_TRADE decisions?
* Where is analyst confidence poorly calibrated?

Reflect aggregates historical runs and surfaces patterns.

It does **not automatically change the system.**

Instead it provides **insight and recommendations.**

Examples of reflective outputs:

* Persona override rate
* Stance alignment statistics
* Strategy activation frequency
* Instrument/session verdict distribution

These insights guide future governance adjustments.

---

# 8. Adaptation Model

The system becomes adaptive through **policy changes**, not persona mutation.

Adaptation occurs through:

| Adaptive lever        | Example                                                  |
| --------------------- | -------------------------------------------------------- |
| Governance thresholds | raise required confidence                                |
| Strategy activation   | enable breakout persona only in trend regime             |
| Persona weighting     | reduce influence of frequently overridden analyst        |
| Routing logic         | call additional specialist analysts in uncertain markets |
| Risk constraints      | reduce allowed exposure during macro risk events         |

This ensures that:

* analysts remain interpretable
* system behavior evolves intelligently
* decisions remain explainable

---

# 9. Why Strategy Personas Are Modular

Strategy personas are intentionally separate from analysts.

Core analysts interpret the market broadly.

Strategy personas evaluate **specific trading ideas.**

Benefits of modular strategy personas:

* easy to add new playbooks
* easier performance tracking
* clear accountability for strategy behavior
* reduced complexity inside analyst prompts

Reflect can analyze strategy personas independently to determine:

* which playbooks work in which contexts
* which strategies are mostly noise
* which setups produce strong signals

---

# 10. Governance Adaptation Cycle

The long-term evolution loop looks like this:

```
Trade Runs Execute
      ↓
Artifacts Stored
      ↓
Reflect Aggregates History
      ↓
Patterns Surface
      ↓
Operator Adjusts Governance Policy
      ↓
System Behavior Evolves
```

Importantly:

The system **observes → recommends → adapts**.

It does **not self-modify blindly.**

---

# 11. What This Architecture Prevents

This design intentionally prevents:

* uncontrolled prompt drift
* analysts changing behavior unpredictably
* loss of interpretability
* hidden strategy bias
* overfitting to recent trades

It ensures the system evolves **through explicit governance decisions.**

---

# 12. Future Evolution

Later phases may introduce:

### Strategy Persona Performance Scoring

Reflect evaluates success rate by market regime.

### Adaptive Strategy Activation

Strategies activate automatically based on market conditions.

### Confidence Calibration

Reflect compares analyst confidence to eventual outcomes.

### Simulation Layer

System replays past runs under alternative policies.

---

# 13. Key Design Principle

The system evolves through **governance and modular strategies**, not through silent mutation of expert personas.

> Core analysts remain stable interpreters.
> Strategy personas are modular playbook evaluators.
> Adaptation occurs in governance policy informed by reflection.

This principle keeps the AI Trade Analyst system **adaptive, explainable, and controllable.**

---

If you'd like, I can also draft a **second companion design note** that is extremely useful for where you're heading:

**"Strategy Persona Framework — How new strategies are added, tested, and governed."**

That one would define:

* strategy persona interface
* evaluation contract
* reflect metrics for strategies
* safe rollout of new playbooks.
