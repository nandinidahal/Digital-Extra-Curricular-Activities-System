import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { dashboardPath } from "../utils/format";
import type { Role } from "../types";

// Sends guests to /login, and sends users to their own dashboard if the role does not match
export default function ProtectedRoute({ role }: { role: Role }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <p className="p-10 text-center">Loading…</p>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  if (user.role !== role && user.role !== "admin") return <Navigate to={dashboardPath(user.role)} replace />;
  return <Outlet />;
}
