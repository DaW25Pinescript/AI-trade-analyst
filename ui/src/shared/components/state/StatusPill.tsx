// ---------------------------------------------------------------------------
// StatusPill — reusable compact state indicator.
// Used for triage_status, bias, and other categorical labels.
// ---------------------------------------------------------------------------

interface StatusPillProps {
  label: string;
  variant?: "default" | "positive" | "negative" | "neutral" | "warning";
}

const VARIANT_STYLES: Record<string, string> = {
  default: "bg-gray-800 text-gray-300",
  positive: "bg-emerald-900/50 text-emerald-300",
  negative: "bg-red-900/50 text-red-300",
  neutral: "bg-gray-800 text-gray-400",
  warning: "bg-amber-900/50 text-amber-300",
};

export function StatusPill({ label, variant = "default" }: StatusPillProps) {
  if (!label) return null;

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${VARIANT_STYLES[variant] ?? VARIANT_STYLES.default}`}
    >
      {label}
    </span>
  );
}
