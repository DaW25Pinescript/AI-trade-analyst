// ---------------------------------------------------------------------------
// OpsLayerSection — renders governance or officer layer entities.
// All-caps section title per visual direction.
// ---------------------------------------------------------------------------

import type { OpsEntityViewModel } from "../adapters/opsViewModel";
import { OpsEntityCard } from "./OpsEntityCard";

export interface OpsLayerSectionProps {
  title: string;
  entities: OpsEntityViewModel[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function OpsLayerSection({
  title,
  entities,
  selectedId,
  onSelect,
}: OpsLayerSectionProps) {
  if (entities.length === 0) return null;

  return (
    <section>
      <h3 className="mb-3 text-xs font-bold uppercase tracking-widest text-gray-500">
        {title}
      </h3>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {entities.map((entity) => (
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
