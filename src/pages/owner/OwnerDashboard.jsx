import { AlertTriangle, LogOut } from "lucide-react";
import PhoneNotificationSettings from "./components/PhoneNotificationSettings";
import LogoutButton from "../../components/LogoutButton";
import MachineOverview from "./components/MachineOverview";
import DashboardSection from "./components/DashboardSection";
import OwnerPoints from "./components/OwnerPoints";
import OwnerPageShell from "./components/OwnerPageShell";
import {
  OwnerEmpty,
  OwnerError,
  OwnerLoading,
} from "./components/OwnerFeedback";
import RecentScans from "./components/RecentScans";
import RecyclingOverview from "./components/RecyclingOverview";
import {
  RecentAlerts,
  RecentTransactions,
} from "./components/RecentActivity";
import useOwnerDashboard from "./hooks/useOwnerDashboard";
import useOwnerMachine from "./hooks/useOwnerMachine";
import { getAlertStatus } from "./utils/ownerAlerts";

function OwnerDashboard() {
  const {
    owner,
    machine,
    loading: machineLoading,
    error: machineError,
  } = useOwnerMachine();
  const dashboard = useOwnerDashboard(machine?.id, machine);
  const { recycling, transactions, alerts, refills } = dashboard.sections;
  const logoutAction = (
    <LogoutButton
      className="owner-dashboard-logout-button"
      ariaLabel="Log out"
      title="Log out"
    >
      <LogOut size={20} />
    </LogoutButton>
  );

  const unreadAlerts = dashboard.recentAlerts.filter(
    (alert) => getAlertStatus(alert) === "unread"
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
      <OwnerError message={machineError} />
      <MachineOverview machine={machine} owner={owner} />
      <PhoneNotificationSettings />

      <div className="owner-dashboard-layout">
        <div className="owner-dashboard-main">
          <DashboardSection
            title="Recycling overview"
            sources={[dashboard.analyticsSource]}
            hasContent={!dashboard.analyticsSource.loading && !dashboard.analyticsSource.error}
            onRetry={dashboard.retryAnalytics}
          >
            <RecyclingOverview key={machine.id} analytics={dashboard.analytics} machine={machine} />
          </DashboardSection>
          <DashboardSection
            title="Scan history"
            sources={[recycling]}
            hasContent={dashboard.recentItems.length > 0}
            onRetry={() => dashboard.retry(["recycling"])}
          >
            <RecentScans key={machine.id} items={dashboard.recentItems}
              canLoadMore={dashboard.canLoadMoreScans} onLoadMore={dashboard.loadMoreScans} loading={recycling.loading} />
          </DashboardSection>
        </div>

        <aside className="owner-dashboard-side">
          <DashboardSection
            title="Recent alerts"
            sources={[alerts]}
            hasContent={dashboard.recentAlerts.length > 0}
            onRetry={() => dashboard.retry(["alerts"])}
          >
            <RecentAlerts alerts={dashboard.recentAlerts} />
          </DashboardSection>
          <DashboardSection
            title="Transactions"
            sources={[transactions, recycling, refills]}
            hasContent={dashboard.recentTransactions.length > 0}
            onRetry={() => dashboard.retry(
              ["transactions", "recycling", "refills"].filter((key) =>
                dashboard.sections[key].loading || dashboard.sections[key].error
              )
            )}
          >
            <RecentTransactions
              key={machine.id}
              machineId={machine.id}
              transactions={dashboard.recentTransactions}
              recyclingRecords={dashboard.recentItems}
            />
          </DashboardSection>
        </aside>
      </div>
    </OwnerPageShell>
  );
}

export default OwnerDashboard;
