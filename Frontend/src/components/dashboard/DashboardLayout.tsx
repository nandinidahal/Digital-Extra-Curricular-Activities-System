



import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import type { LucideIcon } from "lucide-react";

type NavItem = {
  label: string;
  path: string;
  icon: LucideIcon | string;
};

type DashboardLayoutProps = {
  role: "user" | "coordinator" | "admin";
  title: string;
  subtitle: string;
  children: ReactNode;
  navItems: NavItem[];
};

const roleLabels = {
  user: "Student",
  coordinator: "Coordinator",
  admin: "Administrator",
};

export default function DashboardLayout({
  role,
  title,
  subtitle,
  children,
  navItems,
}: DashboardLayoutProps) {
  const location = useLocation();

  // Highlight the active sidebar item.
  // Dashboard matches only /dashboard.
  // Profile also stays active on edit, privacy and account pages.
  const isActive = (path: string) => {
    if (path === "/dashboard") {
      return location.pathname === "/dashboard";
    }

    return (
      location.pathname === path ||
      location.pathname.startsWith(`${path}/`)
    );
  };

  // Render Lucide icons or text icons.
  const renderIcon = (icon: LucideIcon | string) => {
    if (typeof icon === "string") {
      return <span>{icon}</span>;
    }

    const Icon = icon;
    return <Icon size={19} strokeWidth={1.8} />;
  };

  return (
    <div className="min-h-screen bg-[#F5F8F6] text-[#24352D]">
      <div className="flex min-h-screen">

        {/* Sidebar */}
        <aside className="hidden w-64 shrink-0 border-r border-[#E1EAE4] bg-white lg:flex lg:flex-col">

          {/* Logo */}
          <div className="border-b border-[#E1EAE4] px-6 py-6">
            <Link to="/" className="text-xl font-bold text-[#315C4A]">
              XCA
            </Link>

            <p className="mt-1 text-xs text-gray-500">
              Extra-Curricular Activities
            </p>
          </div>

          {/* Navigation */}
          <div className="px-5 py-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">
              {roleLabels[role]} workspace
            </p>

            <nav className="mt-4 space-y-1">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-3 rounded-lg px-4 py-3 text-sm font-medium transition ${
                    isActive(item.path)
                      ? "bg-[#E8F1EC] text-[#315C4A]"
                      : "text-gray-600 hover:bg-gray-50 hover:text-[#315C4A]"
                  }`}
                >
                  {renderIcon(item.icon)}
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>

          {/* Back to website */}
          <div className="mt-auto border-t border-[#E1EAE4] p-5">
            <Link
              to="/"
              className="flex items-center gap-3 rounded-lg px-4 py-3 text-sm text-gray-600 hover:bg-gray-50"
            >
              <span>↗</span>
              Back to website
            </Link>
          </div>
        </aside>

        {/* Main content */}
        <main className="min-w-0 flex-1">

          {/* Header */}
          <header className="border-b border-[#E1EAE4] bg-white px-5 py-4 sm:px-8">
            <div className="flex items-center justify-between gap-4">
              <div>
                <Link
                  to="/"
                  className="text-lg font-bold text-[#315C4A] lg:hidden"
                >
                  XCA
                </Link>

                <h1 className="text-xl font-bold sm:text-2xl">
                  {title}
                </h1>

                <p className="mt-1 text-sm text-gray-500">
                  {subtitle}
                </p>
              </div>

              {/* User role and avatar */}
              <div className="flex items-center gap-3">
                <span className="hidden rounded-full bg-[#E8F1EC] px-3 py-1.5 text-xs font-semibold text-[#315C4A] sm:inline-block">
                  {roleLabels[role]}
                </span>

                <div className="grid h-10 w-10 place-items-center rounded-full bg-[#315C4A] font-semibold text-white">
                  {role === "user"
                    ? "U"
                    : role === "coordinator"
                      ? "C"
                      : "A"}
                </div>
              </div>
            </div>

            {/* Mobile navigation */}
            <nav className="mt-4 flex gap-2 overflow-x-auto pb-1 lg:hidden">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium ${
                    isActive(item.path)
                      ? "bg-[#315C4A] text-white"
                      : "bg-gray-100 text-gray-600"
                  }`}
                >
                  {renderIcon(item.icon)}
                  {item.label}
                </Link>
              ))}
            </nav>
          </header>

          {/* Page content */}
          <div className="mx-auto w-full max-w-7xl p-5 sm:p-8">
            {children}
          </div>

        </main>
      </div>
    </div>
  );
}
