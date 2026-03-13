// ---------------------------------------------------------------------------
// OpsDepartmentSection — framed department box with subtle border.
// All-caps title, entity card grid inside.
// ---------------------------------------------------------------------------

import type { OpsDepartmentViewModel } from "../adapters/opsViewModel";
import { OpsEntityCard } from "./OpsEntityCard";

export interface OpsDepartmentSectionProps {
  department: OpsDepartmentViewModel;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function OpsDepartmentSection({
  department,
  selectedId,
  onSelect,
}: OpsDepartmentSectionProps) {
  return (
    <section className="rounded-lg border border-gray-700/40 bg-gray-900/30 p-4">
      <h4 className="mb-3 text-xs font-bold uppercase tracking-widest text-gray-500">
        {department.label}
      </h4>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {department.entities.map((entity) => (
          <OpsEntityCard
            key={entity.id}
            entity={entity}
            selected={entity.id === selectedId}
            onClick={onSelect}
          />
        ))}
      </div>
    </section>
  );
}
