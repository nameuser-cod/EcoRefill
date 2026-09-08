import { AlertTriangle, LogOut } from "lucide-react";
import LogoutButton from "../../components/LogoutButton";
import MachineOverview from "./components/MachineOverview";
import OwnerPoints from "./components/OwnerPoints";
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
  const logoutAction = (
    <LogoutButton
      className="owner-header-button"
      ariaLabel="Log out"
      title="Log out"
    >
      <LogOut size={20} />
    </LogoutButton>
  );

  const unreadAlerts = dashboard.recentAlerts.filter(
    (alert) => normalizeText(alert.status) === "unread"
  ).length;

  if (machineLoading) {
    return (
      <OwnerPageShell
        eyebrow="Owner workspace"
        title="Dashboard"
        subtitle="Preparing your machine overview"
        action={logoutAction}
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
        action={logoutAction}
      >
        <OwnerError message={machineError} />
        <OwnerPoints owner={owner} />
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
      title="Dashboard"
      subtitle={`Welcome back${owner?.fullName ? `, ${owner.fullName}` : ""}. Here’s how ${machine.machineName || machine.machineId || "your machine"} is doing.`}
      unreadAlerts={unreadAlerts}
      action={logoutAction}
    >
      <OwnerError message={machineError || dashboard.error} />
      <MachineOverview machine={machine} />
      <OwnerPoints owner={owner} />

      {dashboard.loading ? (
        <OwnerLoading label="Loading live machine activity..." />
      ) : (
        <>
          <div className="owner-dashboard-layout">
            <div className="owner-dashboard-main">
              <RecyclingOverview analytics={dashboard.analytics} machine={machine} />
              <RecentScans key={machine.id} items={dashboard.recentItems} />
            </div>

            <aside className="owner-dashboard-side">
              <RecentAlerts alerts={dashboard.recentAlerts} />
              <RecentTransactions
                machineId={machine.id}
                transactions={dashboard.recentTransactions}
                recyclingRecords={dashboard.recentItems}
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
