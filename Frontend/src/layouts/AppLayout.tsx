import { Outlet } from "react-router-dom";
import { AppNavbar, MobileTabBar } from "@/components/layout/AppNavbar";
import { RealtimeProvider } from "@/contexts/RealtimeContext";

export function AppLayout() {
  return (
    <RealtimeProvider>
      <div className="min-h-screen">
        <AppNavbar />
        <main className="mx-auto max-w-7xl px-3 pt-5 pb-28 sm:px-6 lg:pb-12">
          <Outlet />
        </main>
        <MobileTabBar />
      </div>
    </RealtimeProvider>
  );
}
