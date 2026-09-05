import {
  Bell,
  Leaf,
  LayoutDashboard,
  ReceiptText,
  UserRound,
} from "lucide-react";
import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  {
    label: "Dashboard",
    path: "/owner/dashboard",
    icon: LayoutDashboard,
  },
  {
    label: "Transactions",
    path: "/owner/transactions",
    icon: ReceiptText,
  },
  {
    label: "Alerts",
    path: "/owner/alerts",
    icon: Bell,
  },
  {
    label: "Profile",
    path: "/owner/profile",
    icon: UserRound,
  },
];

function OwnerBottomNav({ unreadAlerts = 0 }) {
  return (
    <nav className="owner-app-nav" aria-label="Owner navigation">
      <div className="owner-app-nav-brand" aria-label="EcoRefill owner portal">
        <span><Leaf size={22} /></span>
        <div>
          <strong>EcoRefill</strong>
          <small>Owner portal</small>
        </div>
      </div>

      <div className="owner-app-nav-links">
        {NAV_ITEMS.map(({ label, path, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              `owner-app-nav-item${isActive ? " active" : ""}`
            }
          >
            <span className="owner-app-nav-icon">
              <Icon size={21} />
              {label === "Alerts" && unreadAlerts > 0 && (
                <span className="owner-app-nav-badge" aria-label={`${unreadAlerts} unread alerts`}>
                  {unreadAlerts > 9 ? "9+" : unreadAlerts}
                </span>
              )}
            </span>
            <span>{label}</span>
          </NavLink>
        ))}
      </div>

      <p className="owner-app-nav-note">
        Monitor your machine, activity, and service needs in one place.
      </p>
    </nav>
  );
}

export default OwnerBottomNav;
