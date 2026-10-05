import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import StartupAnimation from "./components/StartupAnimation";
import PhoneNotificationBridge from "./components/PhoneNotificationBridge";
import Welcome from "./pages/auth/Welcome";

const Login = lazy(() => import("./pages/auth/Login"));
const Register = lazy(() => import("./pages/auth/Register"));
const UserDashboard = lazy(() => import("./pages/user/UserDashboard"));
const OwnerDashboard = lazy(() => import("./pages/owner/OwnerDashboard"));
const OwnerAlerts = lazy(() => import("./pages/owner/OwnerAlerts"));
const OwnerProfile = lazy(() => import("./pages/owner/OwnerProfile"));
const OwnerTransactions = lazy(() => import("./pages/owner/OwnerTransactions"));
const OwnerWorkspace = lazy(() => import("./pages/owner/OwnerWorkspace"));
const MachineHome = lazy(() => import("./pages/machine/MachineHome"));
const RedeemQRCode = lazy(() => import("./pages/machine/RedeemQRCode"));
const ScanQR = lazy(() => import("./pages/user/ScanQR"));
const CameraScan = lazy(() => import("./pages/user/CameraScan"));
const UserHistory = lazy(() => import("./pages/user/UserHistory"));
const BuyPoints = lazy(() => import("./pages/user/BuyPoints"));
const UserProfile = lazy(() => import("./pages/user/UserProfile"));
const FindMachines = lazy(() => import("./pages/user/FindMachines"));
const MachineWaterRefill = lazy(() => import("./pages/machine/MachineWaterRefill"));
const UserWaterRefill = lazy(() => import("./pages/user/UserWaterRefill"));

function App() {
  return (
    <StartupAnimation>
      <PhoneNotificationBridge />
      <Suspense fallback={<p role="status" aria-live="polite">Loading page...</p>}>
        <Routes>
          <Route path="/" element={<Welcome />} />
          <Route path="/welcome" element={<Welcome />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/user/dashboard" element={<UserDashboard />} />
          <Route path="/owner" element={<OwnerWorkspace />}>
            <Route path="dashboard" element={<OwnerDashboard />} />
            <Route path="transactions" element={<OwnerTransactions />} />
            <Route path="alerts" element={<OwnerAlerts />} />
            <Route path="profile" element={<OwnerProfile />} />
          </Route>
          <Route path="/machine" element={<MachineHome />} />
          <Route path="/machine/redeem-qr" element={<RedeemQRCode />} />
          <Route path="/user/scan-qr" element={<ScanQR />} />
          <Route path="/user/history" element={<UserHistory />} />
          <Route path="/user/buy-points" element={<BuyPoints />} />
          <Route path="/user/profile" element={<UserProfile />} />
          <Route path="/user/machines" element={<FindMachines />} />
          <Route path="/user/camera-scan" element={<CameraScan />} />
          <Route path="/machine/water-refill" element={<MachineWaterRefill />} />
          <Route path="/user/water-refill/:sessionId" element={<UserWaterRefill />} />
        </Routes>
      </Suspense>
    </StartupAnimation>
  );
}

export default App;
