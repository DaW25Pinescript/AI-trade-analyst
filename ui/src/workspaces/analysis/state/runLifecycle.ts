// ---------------------------------------------------------------------------
// Run Lifecycle State Machine — UI_CONTRACT §7
//
// Deterministic state manager for analysis run lifecycle.
// Enforces valid transitions only. Preserves run_id / request_id across
// all states including failure.
//
// Synchronous flow (this PR):
//   idle → validating → submitting → running → completed | failed
//
// Streaming flow (reserved — not implemented):
//   idle → validating → submitting → running → partial → completed | failed
//
// `partial` exists in the type for future streaming support but is never
// entered or rendered in the synchronous MVP.
// ---------------------------------------------------------------------------

/**
 * Canonical run lifecycle states per UI_CONTRACT §7.
 * `partial` is reserved for future streaming — not entered in synchronous flow.
 */
export type RunState =
  | "idle"
  | "validating"
  | "submitting"
  | "running"
  | "partial"
  | "completed"
  | "failed";

/**
 * Post-completion modifiers (UI_CONTRACT §7).
 * Applied to completed runs to signal secondary conditions.
 */
export type CompletionModifier =
  | "artifact-missing"
  | "stale"
  | "inconsistent"
  | null;

/**
 * Error detail preserved from backend — mixed detail pattern (§11.1).
 */
export interface RunErrorDetail {
  message: string;
  code?: string;
  request_id?: string;
  run_id?: string;
}

/**
 * Full lifecycle state snapshot — immutable, replaced on each transition.
 */
export interface RunLifecycleState {
  state: RunState;
  run_id: string | null;
  request_id: string | null;
  error: RunErrorDetail | null;
  modifier: CompletionModifier;
  startedAt: number | null;
  completedAt: number | null;
}

/**
 * Valid state transitions for the synchronous flow.
 * `partial` transitions are included for type completeness but guarded.
 */
const VALID_TRANSITIONS: Record<RunState, RunState[]> = {
  idle: ["validating"],
  validating: ["submitting", "idle"],
  submitting: ["running", "failed"],
  running: ["completed", "failed", "partial"],
  partial: ["completed", "failed", "partial"],
  completed: ["idle"],
  failed: ["idle"],
};

export function createInitialState(): RunLifecycleState {
  return {
    state: "idle",
    run_id: null,
    request_id: null,
    error: null,
    modifier: null,
    startedAt: null,
    completedAt: null,
  };
}

/**
 * Validates whether a transition from `from` to `to` is allowed.
 */
export function isValidTransition(from: RunState, to: RunState): boolean {
  return VALID_TRANSITIONS[from]?.includes(to) ?? false;
}

/**
 * Transition context — carries data for the new state.
 */
export interface TransitionContext {
  run_id?: string | null;
  request_id?: string | null;
  error?: RunErrorDetail | null;
  modifier?: CompletionModifier;
}

/**
 * Attempts a state transition. Returns new state on success, or throws
 * on invalid transition (programming error — should never happen at runtime).
 */
export function transition(
  current: RunLifecycleState,
  to: RunState,
  ctx: TransitionContext = {},
): RunLifecycleState {
  if (!isValidTransition(current.state, to)) {
    throw new Error(
      `Invalid run lifecycle transition: ${current.state} → ${to}`,
    );
  }

  const now = Date.now();

  // Reset on idle
  if (to === "idle") {
    return createInitialState();
  }

  return {
    state: to,
    // Preserve run_id: new value > existing > null
    run_id: ctx.run_id ?? current.run_id,
    request_id: ctx.request_id ?? current.request_id,
    error: ctx.error ?? null,
    modifier: ctx.modifier ?? null,
    startedAt:
      to === "submitting" ? now : current.startedAt,
    completedAt:
      to === "completed" || to === "failed" ? now : null,
  };
}

// ---- Typed transition actions ----

export function toValidating(current: RunLifecycleState): RunLifecycleState {
  return transition(current, "validating");
}

export function toSubmitting(current: RunLifecycleState): RunLifecycleState {
  return transition(current, "submitting");
}

export function toRunning(
  current: RunLifecycleState,
  ctx?: { run_id?: string; request_id?: string },
): RunLifecycleState {
  return transition(current, "running", ctx);
}

export function toCompleted(
  current: RunLifecycleState,
  ctx?: { run_id?: string; modifier?: CompletionModifier },
): RunLifecycleState {
  return transition(current, "completed", ctx);
}

export function toFailed(
  current: RunLifecycleState,
  error: RunErrorDetail,
  ctx?: { run_id?: string; request_id?: string },
): RunLifecycleState {
  return transition(current, "failed", { ...ctx, error });
}

export function toIdle(current: RunLifecycleState): RunLifecycleState {
  return transition(current, "idle");
}

// ---- Query helpers ----

export function isTerminal(state: RunState): boolean {
  return state === "completed" || state === "failed";
}

export function isRunning(state: RunState): boolean {
  return state === "submitting" || state === "running" || state === "partial";
}

export function canSubmit(state: RunState): boolean {
  return state === "idle";
}

export function canReset(state: RunState): boolean {
  return state === "completed" || state === "failed";
}
