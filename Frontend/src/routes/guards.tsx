import { Navigate, Outlet, useLocation } from "react-router-dom";
import { PageLoader } from "@/components/common/Feedback";
import { useAuth } from "@/contexts/AuthContext";

/** Only for logged-in users. Remembers where the visitor wanted to go (?next=...). */
export function RequireAuth() {
  const { status, signedOut } = useAuth();
  const location = useLocation();
  if (status === "loading") return <PageLoader />;
  if (status === "anonymous" && signedOut) return <Navigate to="/" replace />;
  if (status === "anonymous") {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
  return <Outlet />;
}

/**
 * Login/register pages: logged-in users are sent on. Honours ?next= so that right after a
 * successful login the visitor lands on the page they originally asked for.
 */
export function RequireGuest() {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <PageLoader />;
  if (status === "authenticated") {
    return <Navigate to={safeNext(new URLSearchParams(location.search).get("next"))} replace />;
  }
  return <Outlet />;
}

/** Moderator-only pages (admin or coordinator). The backend enforces the same rule. */
export function RequireModerator() {
  const { isModerator } = useAuth();
  return isModerator ? <Outlet /> : <Navigate to="/home" replace />;
}

/** Only allow internal paths as post-login targets (prevents open redirects). */
export function safeNext(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return "/home";
  return value;
}
