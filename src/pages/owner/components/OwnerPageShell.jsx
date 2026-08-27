import OwnerBottomNav from "./OwnerBottomNav";
import "../../../styles/owner.css";
import "../../../styles/owner-dashboard.css";

function OwnerPageShell({
  eyebrow,
  title,
  subtitle,
  action,
  unreadAlerts = 0,
  children,
}) {
  return (
    <div className="owner-app-page">
      <main className="owner-app-shell">
        <header className="owner-app-header">
          <div>
            <p className="owner-app-eyebrow">{eyebrow}</p>
            <h1>{title}</h1>
            {subtitle && <p className="owner-app-subtitle">{subtitle}</p>}
          </div>
          {action && <div className="owner-app-header-action">{action}</div>}
        </header>

        {children}
      </main>

      <OwnerBottomNav unreadAlerts={unreadAlerts} />
    </div>
  );
}

export default OwnerPageShell;
