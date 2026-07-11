import { IconChartBar, IconHome, IconLogin, IconPlus, IconTrophy } from "@tabler/icons-react";
import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../useAuth";

const navItems = [
  { to: "/", label: "Home", icon: IconHome, end: true },
  { to: "/matches", label: "Match History", icon: IconChartBar },
  { to: "/leaderboard", label: "Leaderboard", icon: IconTrophy },
  { to: "/bots/new", label: "Register Bot", icon: IconPlus },
];

export default function AppLayout() {
  const { isAuthenticated, loading, user } = useAuth();

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

        <div className="auth-nav">
          {!loading && isAuthenticated && (
            <span title={user.email}>{user.email}</span>
          )}
          {!loading && !isAuthenticated && (
            <NavLink to="/login" className="nav-link">
              <IconLogin size={17} stroke={1.75} aria-hidden="true" />
              <span>Log in</span>
            </NavLink>
          )}
        </div>
      </header>

      <Outlet />
    </div>
  );
}
