import { Outlet } from "react-router-dom";
import { PublicFooter, PublicNavbar } from "@/components/layout/PublicNavbar";

export function PublicLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <PublicNavbar />
      <main className="flex-1">
        <Outlet />
      </main>
      <PublicFooter />
    </div>
  );
}
