import { Bot, History, LayoutDashboard, SearchCheck } from "lucide-react";
import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/reviews/new", label: "New Review", icon: SearchCheck },
  { to: "/history", label: "History", icon: History },
];

export default function Navbar() {
  return (
    <header className="border-b border-slate-200/80 bg-white/70 backdrop-blur-md">
      <div className="flex h-[72px] w-full items-center justify-between px-4 sm:px-6 lg:px-8">
        <NavLink to="/" className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-sky-300/50 bg-sky-100">
            <Bot className="h-5 w-5 text-sky-700" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-900">Agentic AI Code Review Bot</p>
            <p className="text-xs text-slate-500">Autonomous pull request review assistant</p>
          </div>
        </NavLink>

        <nav className="flex items-center gap-2">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `inline-flex h-10 items-center gap-2 rounded-lg px-3 text-sm font-medium transition ${
                  isActive
                    ? "bg-sky-100 text-slate-900"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`
              }
            >
              <Icon className="h-4 w-4" />
              <span className="hidden sm:inline">{label}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  );
}
