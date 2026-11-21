
import { Link } from "react-router-dom";
import DashboardLayout from "../../components/dashboard/DashboardLayout";

const navItems = [
  { label: "Overview", path: "/admin/dashboard", icon: "⌂" },
  { label: "Users", path: "/admin/users", icon: "♙" },
  { label: "Coordinators", path: "/admin/coordinators", icon: "♧" },
  { label: "Activities", path: "/admin/activities", icon: "▣" },
  { label: "Approvals", path: "/admin/approvals", icon: "✓" },
];

const stats = [
  { label: "Total Users", value: "1,250", icon: "♙" },
  { label: "Coordinators", value: "18", icon: "♧" },
  { label: "Total Activities", value: "86", icon: "▣" },
  { label: "Pending Approvals", value: "07", icon: "◷" },
];

const recentUsers = [
  {
    name: "Student One",
    email: "student1@example.com",
    role: "User",
  },
  {
    name: "Coordinator One",
    email: "coordinator1@example.com",
    role: "Coordinator",
  },
  {
    name: "Student Two",
    email: "student2@example.com",
    role: "User",
  },
];

export default function AdminDashboard() {
  return (
    <DashboardLayout
      role="admin"
      title="Admin Dashboard"
      subtitle="Monitor and manage the entire platform."
      navItems={navItems}
    >
      <section className="rounded-2xl bg-[#315C4A] p-6 text-white sm:p-8">
        <p className="text-sm text-white/75">Administration workspace</p>
        <h2 className="mt-2 text-2xl font-bold sm:text-3xl">
          Platform Overview
        </h2>
        <p className="mt-2 max-w-xl text-sm leading-6 text-white/80">
          Manage users, coordinators, activities and platform operations from
          one place.
        </p>
        <Link
          to="/admin/users"
          className="mt-5 inline-block rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-[#315C4A] hover:bg-gray-100"
        >
          Manage Users
        </Link>
      </section>

      {/* Statistics */}
      <section className="mt-7 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl border border-[#E1EAE4] bg-white p-5"
          >
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">{stat.label}</p>
              <span className="text-xl text-[#315C4A]">{stat.icon}</span>
            </div>
            <p className="mt-3 text-3xl font-bold">{stat.value}</p>
          </div>
        ))}
      </section>

      {/* Recent users */}
      <section className="mt-7 rounded-xl border border-[#E1EAE4] bg-white p-5">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div>
            <h3 className="font-bold">Recently Added Users</h3>
            <p className="mt-1 text-sm text-gray-500">
              Latest accounts registered on the platform
            </p>
          </div>
          <Link
            to="/admin/users"
            className="text-sm font-semibold text-[#315C4A] hover:underline"
          >
            View all users
          </Link>
        </div>

        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[550px] text-left text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-gray-500">
                <th className="px-3 py-3 font-medium">Name</th>
                <th className="px-3 py-3 font-medium">Email</th>
                <th className="px-3 py-3 font-medium">Role</th>
                <th className="px-3 py-3 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {recentUsers.map((user) => (
                <tr key={user.email} className="border-b border-gray-50">
                  <td className="px-3 py-4 font-semibold">{user.name}</td>
                  <td className="px-3 py-4 text-gray-500">{user.email}</td>
                  <td className="px-3 py-4">
                    <span className="rounded-full bg-[#E8F1EC] px-3 py-1 text-xs font-medium text-[#315C4A]">
                      {user.role}
                    </span>
                  </td>
                  <td className="px-3 py-4">
                    <Link
                      to="/admin/users"
                      className="font-semibold text-[#315C4A] hover:underline"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Admin actions */}
      <section className="mt-6">
        <h3 className="font-bold">Platform Management</h3>
        <p className="mt-1 text-sm text-gray-500">
          Quick access to administration tools
        </p>

        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[
            {
              title: "Manage Users",
              description: "View accounts and manage user roles.",
              path: "/admin/users",
              icon: "♙",
            },
            {
              title: "Manage Coordinators",
              description: "Review and manage coordinators.",
              path: "/admin/coordinators",
              icon: "♧",
            },
            {
              title: "Manage Activities",
              description: "Monitor all platform activities.",
              path: "/admin/activities",
              icon: "▣",
            },
            {
              title: "Review Approvals",
              description: "Review pending activity requests.",
              path: "/admin/approvals",
              icon: "✓",
            },
          ].map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className="rounded-xl border border-[#E1EAE4] bg-white p-5 transition hover:-translate-y-0.5 hover:border-[#315C4A]"
            >
              <span className="text-2xl text-[#315C4A]">{item.icon}</span>
              <h4 className="mt-3 font-bold">{item.title}</h4>
              <p className="mt-1 text-sm leading-5 text-gray-500">
                {item.description}
              </p>
            </Link>
          ))}
        </div>
      </section>
    </DashboardLayout>
  );
}
