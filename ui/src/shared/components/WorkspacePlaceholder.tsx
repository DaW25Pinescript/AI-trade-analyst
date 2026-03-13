interface WorkspacePlaceholderProps {
  name: string;
}

export function WorkspacePlaceholder({ name }: WorkspacePlaceholderProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-gray-700 bg-gray-900 p-12 text-center">
      <h2 className="text-2xl font-semibold text-gray-200">{name}</h2>
      <p className="mt-2 text-sm text-gray-500">
        Workspace shell — placeholder for future implementation
      </p>
    </div>
  );
}
