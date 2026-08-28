import { AlertTriangle, LogOut } from "lucide-react";
import LogoutButton from "../../components/LogoutButton";
import MachineMetrics from "./components/MachineMetrics";
import MachineOverview from "./components/MachineOverview";
import OwnerPageShell from "./components/OwnerPageShell";
import {
  OwnerEmpty,
  OwnerError,
  OwnerLoading,
} from "./components/OwnerFeedback";
import RecentScans from "./components/RecentScans";
import RecyclingOverview from "./components/RecyclingOverview";
import RejectedBreakdown from "./components/RejectedBreakdown";
import {
  RecentAlerts,
  RecentTransactions,
} from "./components/RecentActivity";
import useOwnerDashboard from "./hooks/useOwnerDashboard";
import useOwnerMachine from "./hooks/useOwnerMachine";
import { normalizeText } from "./utils/ownerDashboard";

function OwnerDashboard() {
  const {
    owner,
    machine,
    loading: machineLoading,
    error: machineError,
  } = useOwnerMachine();
  const dashboard = useOwnerDashboard(machine?.id);

  const unreadAlerts = dashboard.recentAlerts.filter(
    (alert) => normalizeText(alert.status) === "unread"
  ).length;

  if (machineLoading) {
    return (
      <OwnerPageShell
        eyebrow="Owner workspace"
        title="Dashboard"
        subtitle="Preparing your machine overview"
      >
        <OwnerLoading />
      </OwnerPageShell>
    );
  }

  if (!machine) {
    return (
      <OwnerPageShell
        eyebrow="Owner workspace"
        title={`Welcome${owner?.fullName ? `, ${owner.fullName}` : ""}`}
        subtitle="Manage your EcoRefill machine from one place."
        action={
          <LogoutButton
            className="owner-header-button"
            ariaLabel="Log out"
          >
            <LogOut size={20} />
          </LogoutButton>
        }
      >
        <OwnerError message={machineError} />
        <section className="owner-panel owner-no-machine">
          <OwnerEmpty
            icon={AlertTriangle}
            title="No machine connected"
            description="Ask an administrator to assign a machine to this owner account."
          />
        </section>
      </OwnerPageShell>
    );
  }

  return (
    <OwnerPageShell
      eyebrow="Owner workspace"
      title={machine.machineName || machine.machineId || machine.id || "EcoRefill machine"}
      subtitle={`Welcome back${owner?.fullName ? `, ${owner.fullName}` : ""}.`}
      unreadAlerts={unreadAlerts}
      action={
        <LogoutButton
          className="owner-header-button"
          ariaLabel="Log out"
        >
          <LogOut size={20} />
        </LogoutButton>
      }
    >
      <OwnerError message={machineError || dashboard.error} />

      {dashboard.loading ? (
        <OwnerLoading label="Loading live machine activity..." />
      ) : (
        <>
          <MachineOverview machine={machine} />
          <MachineMetrics machine={machine} />

          <div className="owner-dashboard-layout">
            <div className="owner-dashboard-main">
              <RecyclingOverview analytics={dashboard.analytics} />
              <RecentScans items={dashboard.recentItems} />
            </div>

            <aside className="owner-dashboard-side">
              <RecentAlerts alerts={dashboard.recentAlerts} />
              <RecentTransactions
                transactions={dashboard.recentTransactions}
              />
              <RejectedBreakdown
                rejectedTypes={dashboard.analytics.rejectedTypes}
              />
            </aside>
          </div>
        </>
      )}
    </OwnerPageShell>
  );
}

export default OwnerDashboard;
