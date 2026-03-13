import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-gray-700 bg-gray-900 p-12 text-center">
      <h2 className="text-2xl font-semibold text-gray-200">404</h2>
      <p className="mt-2 text-sm text-gray-500">Route not found</p>
      <Link
        to="/triage"
        className="mt-4 rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
      >
        Go to Triage
      </Link>
    </div>
  );
}
