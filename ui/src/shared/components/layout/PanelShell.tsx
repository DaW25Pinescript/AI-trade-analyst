// ---------------------------------------------------------------------------
// PanelShell — workspace panel container.
// Provides consistent padding, background, and optional header slot.
// ---------------------------------------------------------------------------

import type { ReactNode } from "react";

export interface PanelShellProps {
  children: ReactNode;
  className?: string;
}

export function PanelShell({ children, className = "" }: PanelShellProps) {
  return (
    <div className={`space-y-4 ${className}`}>
      {children}
    </div>
  );
}
