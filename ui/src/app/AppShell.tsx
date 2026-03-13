import { NavLink, Outlet } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/triage", label: "Triage" },
  { to: "/analysis", label: "Analysis" },
  { to: "/journal", label: "Journal" },
  { to: "/review", label: "Review" },
  { to: "/ops", label: "Ops" },
] as const;

export function AppShell() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-gray-800 bg-gray-900 px-6 py-3">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-gray-100">
            AI Trade Analyst
          </h1>
          <nav className="flex gap-1">
            {NAV_ITEMS.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `rounded px-3 py-1.5 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-blue-600 text-white"
                      : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
