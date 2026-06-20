import { Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "../pages/login";
import HomePage from "../pages/home";
import TeamPage from "../pages/team";
import EarningsPage from "../pages/earnings";
import RechargePage from "../pages/recharge";
import SalesPage from "../pages/sales";
import WithdrawalPage from "../pages/withdrawal";
import ProfilePage from "../pages/profile";
import NotificationsPage from "../pages/notifications";
import AppLayout from "../components/Layout";
import { useAuthStore } from "../stores/auth";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token);
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<HomePage />} />
        <Route path="team" element={<TeamPage />} />
        <Route path="earnings" element={<EarningsPage />} />
        <Route path="recharge" element={<RechargePage />} />
        <Route path="sales" element={<SalesPage />} />
        <Route path="withdrawal" element={<WithdrawalPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="notifications" element={<NotificationsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
