"""
Macro Risk Officer (MRO) — advisory-only macro context engine.

Answers: "What kind of market environment are we in right now?"

Output is a MacroContext object consumed by the Arbiter prompt builder.
MRO never generates signals and never overrides price structure.
"""

__version__ = "0.1.0"
