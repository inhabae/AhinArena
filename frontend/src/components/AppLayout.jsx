import { IconChartBar, IconHome, IconTrophy } from "@tabler/icons-react";
import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/", label: "Home", icon: IconHome, end: true },
  { to: "/matches", label: "Match History", icon: IconChartBar },
  { to: "/leaderboard", label: "Leaderboard", icon: IconTrophy },
];

export default function AppLayout() {
  return (
    <div className="app-shell">
      <header className="top-nav">
        <NavLink to="/" className="brand-link" aria-label="AhinArena home">
          <img src="/ahin.svg" alt="" className="brand-mark" />
          <span className="brand-wordmark">AhinArena</span>
        </NavLink>

        <nav className="nav-links" aria-label="Primary navigation">
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                isActive ? "nav-link nav-link-active" : "nav-link"
              }
            >
              <Icon size={17} stroke={1.75} aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </header>

      <Outlet />
    </div>
  );
}
