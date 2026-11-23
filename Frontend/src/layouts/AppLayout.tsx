// import { Outlet } from "react-router-dom";
// import { AppNavbar, MobileTabBar } from "@/components/layout/AppNavbar";
// import { Footer } from "@/components/layout/Footer"
// import { RealtimeProvider } from "@/contexts/RealtimeContext";

// export function AppLayout() {
//   return (
//     <RealtimeProvider>
//       <div className="min-h-screen">
//         <AppNavbar />
//         <main className="mx-auto max-w-7xl px-3 pt-5 pb-28 sm:px-6 lg:pb-12">
//           <Outlet />
//         </main>
//         <MobileTabBar />
//         <Footer />
//       </div>
//     </RealtimeProvider>
//   );
// }


import { Outlet } from "react-router-dom";
import { AppNavbar, MobileTabBar } from "@/components/layout/AppNavbar";
import { Footer } from "@/components/layout/Footer";
import { RealtimeProvider } from "@/contexts/RealtimeContext";

export function AppLayout() {
  return (
    <RealtimeProvider>
      <div className="flex min-h-screen flex-col">
        <AppNavbar />

        <main className="mx-auto w-full max-w-7xl flex-1 px-3 pt-5 pb-28 sm:px-6 lg:pb-12">
          <Outlet />
        </main>

        <Footer />

        <MobileTabBar />
      </div>
    </RealtimeProvider>
  );
}
