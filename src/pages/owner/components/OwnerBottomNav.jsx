import {
  Bell,
  LayoutDashboard,
  ReceiptText,
  UserRound,
} from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

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
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <nav className="owner-app-nav" aria-label="Owner navigation">
      {NAV_ITEMS.map(({ label, path, icon: Icon }) => {
        const active = location.pathname.startsWith(path);

        return (
          <button
            type="button"
            key={path}
            className={`owner-app-nav-item${active ? " active" : ""}`}
            onClick={() => navigate(path)}
            aria-current={active ? "page" : undefined}
          >
            <span className="owner-app-nav-icon">
              <Icon size={21} />
              {label === "Alerts" && unreadAlerts > 0 && (
                <span className="owner-app-nav-badge" aria-hidden="true">
                  {unreadAlerts > 9 ? "9+" : unreadAlerts}
                </span>
              )}
            </span>
            <span>{label}</span>
          </button>
        );
      })}
    </nav>
  );
}

export default OwnerBottomNav;
