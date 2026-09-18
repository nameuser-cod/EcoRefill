import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import MachineHome from "./pages/machine/MachineHome";
import RedeemQRCode from "./pages/machine/RedeemQRCode";
import MachineWaterRefill from "./pages/machine/MachineWaterRefill";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/machine" element={<MachineHome />} />
        <Route path="/machine/redeem-qr" element={<RedeemQRCode />} />
        <Route path="/machine/water-refill" element={<MachineWaterRefill />} />
        <Route path="*" element={<Navigate to="/machine" replace />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
