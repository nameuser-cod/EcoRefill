import { Navigate, Route, Routes } from "react-router-dom";
import Login from "./pages/auth/Login";
import Register from "./pages/auth/Register";
import UserDashboard from "./pages/user/UserDashboard";
import OwnerDashboard from "./pages/owner/OwnerDashboard";
import MachineHome from "./pages/machine/MachineHome";
import RedeemQRCode from "./pages/machine/RedeemQRCode";
import ScanQR, { CameraScan } from "./pages/user/ScanQR";
import UserHistory from "./pages/user/UserHistory";
import BuyPoints from "./pages/user/BuyPoints";
import MachineWaterRefill from "./pages/machine/MachineWaterRefill";
import UserWaterRefill from "./pages/user/UserWaterRefill";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/machine" />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/user/dashboard" element={<UserDashboard />} />
      <Route path="/owner/dashboard" element={<OwnerDashboard />} />
      <Route path="/machine" element={<MachineHome />} />
      <Route path="/machine/redeem-qr" element={<RedeemQRCode />} />
      <Route path="/user/scan-qr" element={<ScanQR />} />
      <Route path="/user/history" element={<UserHistory />} />
      <Route path="/user/buy-points" element={<BuyPoints />} />
      <Route path="/user/scan-qr" element={<ScanQR />} />
      <Route path="/user/camera-scan"element={<CameraScan />} />
      <Route path="/machine/water-refill"element={<MachineWaterRefill />}/>
      <Route path="/user/water-refill/:sessionId"element={<UserWaterRefill />}/>
    </Routes>
  );
}

export default App;
