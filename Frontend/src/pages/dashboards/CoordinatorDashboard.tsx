
import { Link } from "react-router-dom";
import DashboardLayout from "../../components/dashboard/DashboardLayout";

const navItems = [
  { label: "Overview", path: "/coordinator/dashboard", icon: "⌂" },
  { label: "My Activities", path: "/coordinator/activities", icon: "▣" },
  { label: "Registrations", path: "/coordinator/registrations", icon: "♙" },
  { label: "Attendance", path: "/coordinator/attendance", icon: "✓" },
];

const stats = [
  { label: "Total Activities", value: "12", icon: "▣" },
  { label: "Published Activities", value: "08", icon: "✓" },
  { label: "Pending Approvals", value: "03", icon: "◷" },
  { label: "Total Participants", value: "245", icon: "♙" },
];

const activities = [
  {
    title: "Web Development Workshop",
    date: "12 Nov 2026",
    participants: 45,
    status: "Published",
  },
  {
    title: "AI Innovation Exhibition",
    date: "18 Nov 2026",
    participants: 80,
    status: "Registration Open",
  },
  {
    title: "Leadership Development",
    date: "25 Nov 2026",
    participants: 30,
    status: "Pending Review",
  },
];

export default function CoordinatorDashboard() {
  return (
    <DashboardLayout
      role="coordinator"
      title="Coordinator Dashboard"
      subtitle="Manage your activities and monitor student participation."
      navItems={navItems}
    >
      <section className="rounded-2xl bg-[#315C4A] p-6 text-white sm:p-8">
        <p className="text-sm text-white/75">Coordinator workspace</p>
        <h2 className="mt-2 text-2xl font-bold sm:text-3xl">
          Manage Your Activities
        </h2>
        <p className="mt-2 max-w-xl text-sm leading-6 text-white/80">
          Create activities, manage registrations, monitor attendance and
          support students in their extra-curricular journey.
        </p>
        <Link
          to="/coordinator/activities"
          className="mt-5 inline-block rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-[#315C4A] hover:bg-gray-100"
        >
          Manage Activities
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

      {/* Activity management */}
      <section className="mt-7 rounded-xl border border-[#E1EAE4] bg-white p-5">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div>
            <h3 className="font-bold">Activity Management</h3>
            <p className="mt-1 text-sm text-gray-500">
              Review and manage your activities
            </p>
          </div>

          <Link
            to="/coordinator/activities"
            className="rounded-lg bg-[#315C4A] px-4 py-2.5 text-center text-sm font-semibold text-white hover:bg-[#244638]"
          >
            + Create Activity
          </Link>
        </div>

        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[650px] text-left text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-gray-500">
                <th className="px-3 py-3 font-medium">Activity</th>
                <th className="px-3 py-3 font-medium">Date</th>
                <th className="px-3 py-3 font-medium">Participants</th>
                <th className="px-3 py-3 font-medium">Status</th>
                <th className="px-3 py-3 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {activities.map((activity) => (
                <tr key={activity.title} className="border-b border-gray-50">
                  <td className="px-3 py-4 font-semibold">{activity.title}</td>
                  <td className="px-3 py-4 text-gray-500">{activity.date}</td>
                  <td className="px-3 py-4">{activity.participants}</td>
                  <td className="px-3 py-4">
                    <span className="rounded-full bg-[#E8F1EC] px-3 py-1 text-xs font-medium text-[#315C4A]">
                      {activity.status}
                    </span>
                  </td>
                  <td className="px-3 py-4">
                    <Link
                      to="/coordinator/activities"
                      className="font-semibold text-[#315C4A] hover:underline"
                    >
                      Manage
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Quick actions */}
      <section className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Link
          to="/coordinator/activities"
          className="rounded-xl border border-[#E1EAE4] bg-white p-5 hover:border-[#315C4A]"
        >
          <span className="text-2xl">＋</span>
          <h3 className="mt-3 font-bold">Create Activity</h3>
          <p className="mt-1 text-sm text-gray-500">
            Add a new extra-curricular activity.
          </p>
        </Link>

        <Link
          to="/coordinator/registrations"
          className="rounded-xl border border-[#E1EAE4] bg-white p-5 hover:border-[#315C4A]"
        >
          <span className="text-2xl">♙</span>
          <h3 className="mt-3 font-bold">Review Registrations</h3>
          <p className="mt-1 text-sm text-gray-500">
            View and manage student registrations.
          </p>
        </Link>

        <Link
          to="/coordinator/attendance"
          className="rounded-xl border border-[#E1EAE4] bg-white p-5 hover:border-[#315C4A]"
        >
          <span className="text-2xl">✓</span>
          <h3 className="mt-3 font-bold">Manage Attendance</h3>
          <p className="mt-1 text-sm text-gray-500">
            Track attendance for your activities.
          </p>
        </Link>
      </section>
    </DashboardLayout>
  );
}
