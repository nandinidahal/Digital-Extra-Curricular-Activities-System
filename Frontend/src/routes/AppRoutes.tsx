import { Route, Routes } from "react-router-dom";
import MainLayout from "../components/layout/MainLayout";
import ProtectedRoute from "./ProtectedRoute";
import HomePage from "../pages/public/HomePage";
import LoginPage from "../pages/public/LoginPage";
import PlaceholderPage from "../pages/PlaceholderPage";

// Pages that are not built yet use PlaceholderPage. Replace them one by one.
const page = (title: string) => <PlaceholderPage title={title} />;

export default function AppRoutes() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        {/* Public */}
        <Route path="/" element={<HomePage />} />
        <Route path="/activities" element={page("All activities")} />
        <Route path="/activities/:id" element={page("Activity details")} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={page("Create your account")} />
        <Route path="/verify/:code" element={page("Verify a certificate")} />

        {/* Student */}
        <Route element={<ProtectedRoute role="student" />}>
          <Route path="/student/dashboard" element={page("Student dashboard")} />
          <Route path="/student/activities" element={page("My activities")} />
          <Route path="/student/achievements" element={page("My achievements")} />
          <Route path="/student/certificates" element={page("My certificates")} />
          <Route path="/student/notifications" element={page("Notifications")} />
          <Route path="/student/profile" element={page("My profile")} />
        </Route>

        {/* Coordinator */}
        <Route element={<ProtectedRoute role="coordinator" />}>
          <Route path="/coordinator/dashboard" element={page("Coordinator dashboard")} />
          <Route path="/coordinator/activities" element={page("Manage activities")} />
          <Route path="/coordinator/registrations" element={page("Registrations")} />
          <Route path="/coordinator/attendance" element={page("Attendance")} />
          <Route path="/coordinator/achievements" element={page("Achievements")} />
        </Route>

        {/* Admin */}
        <Route element={<ProtectedRoute role="admin" />}>
          <Route path="/admin/dashboard" element={page("Admin dashboard")} />
          <Route path="/admin/users" element={page("Users")} />
          <Route path="/admin/categories" element={page("Categories")} />
          <Route path="/admin/activities" element={page("All activities")} />
          <Route path="/admin/reports" element={page("Reports")} />
          <Route path="/admin/announcements" element={page("Announcements")} />
        </Route>

        <Route path="*" element={page("Page not found")} />
      </Route>
    </Routes>
  );
}
