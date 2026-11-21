// import { Route, Routes } from "react-router-dom";
// import MainLayout from "../components/layout/MainLayout";
// import ProtectedRoute from "./ProtectedRoute";
// import HomePage from "../pages/public/HomePage";
// import LoginPage from "../pages/public/LoginPage";
// // import  CreateAccount  from "../pages/public/CreateAccount";
// import PlaceholderPage from "../pages/PlaceholderPage";
// import CreateAccount from "../pages/public/CreateAccount";
// import ActivityDetail from "../components/common/ActivityDetail";
// import Dashboard from "../pages/public/Dashboard";
// import  VerifyEmailPage from "../pages/public/VerifyEmailPage"

// import UserDashboard from "../pages/dashboards/UserDashboard"
// // import CoordinatorDashboard from "../pages/dashboards/CoordinatorDashboard"
// // import AdminDashboard from "../pages/dashboards/AdminDashboard"

// import ProfilePage from "../pages/profile/ProfilePage";
// import EditProfilePage from "../pages/profile/EditProfilePage";
// import PrivacySettingsPage from "../pages/profile/PrivacySettingsPage";
// import AccountSettingsPage from "../pages/profile/AccountSettingsPage";

// // Pages that are not built yet use PlaceholderPage. Replace them one by one.
// const page = (title: string) => <PlaceholderPage title={title} />;

// export default function AppRoutes() {
//   return (
//     <Routes>
//       <Route element={<MainLayout />}>
//         {/* Public */}
//         <Route path="/" element={<HomePage />} />
//         <Route path="/activities" element={page("All activities")} />
//         {/* <Route path="/activities/:id" element={page("Activity details")} /> */}
//         <Route path="/login" element={<LoginPage />} />
//         <Route path="/CreateAccount" element={<CreateAccount />} />
//         <Route path="/activities/:id" element={<ActivityDetail />} />
//         {/* <Route path="/register" element={page("Create your account")} /> */}
//         <Route path="/verify/:code" element={page("Verify a certificate")} />
//         <Route path="/dashboard-view" element={<Dashboard />} />
//         {/* <Route path="/dashboard" element={<UserDashboard />} /> */}
//         {/* <Route path="/coordinator/dashboard" element={<CoordinatorDashboard />} />
//         <Route path="/admin/dashboard" element={<AdminDashboard />} /> */}
//         <Route path="/dashboard" element={<UserDashboard />} />
//         {/* <Route path="/coordinator/dashboard"element={<CoordinatorDashboard />}/>
//         <Route path="/admin/dashboard" element={<AdminDashboard />} /> */}
//         <Route path="/verify-email" element={<VerifyEmailPage />} />

//         <Route path="/dashboard/profile" element={<ProfilePage />} />
//         <Route path="/dashboard/profile/edit" element={<EditProfilePage />} />
//         <Route path="/dashboard/profile/privacy" element={<PrivacySettingsPage />} />
//         <Route path="/dashboard/profile/account" element={<AccountSettingsPage />} />

        

//         {/* Student */}
//         <Route element={<ProtectedRoute role="student" />}>
//           <Route path="/student/dashboard" element={page("Student dashboard")} />
//           <Route path="/student/activities" element={page("My activities")} />
//           <Route path="/student/achievements" element={page("My achievements")} />
//           <Route path="/student/certificates" element={page("My certificates")} />
//           <Route path="/student/notifications" element={page("Notifications")} />
//           <Route path="/student/profile" element={page("My profile")} />
//         </Route>

//         {/* Coordinator */}
//         <Route element={<ProtectedRoute role="coordinator" />}>
//           <Route path="/coordinator/dashboard" element={page("Coordinator dashboard")} />
//           <Route path="/coordinator/activities" element={page("Manage activities")} />
//           <Route path="/coordinator/registrations" element={page("Registrations")} />
//           <Route path="/coordinator/attendance" element={page("Attendance")} />
//           <Route path="/coordinator/achievements" element={page("Achievements")} />
//         </Route>

//         {/* Admin */}
//         <Route element={<ProtectedRoute role="admin" />}>
//           <Route path="/admin/dashboard" element={page("Admin dashboard")} />
//           <Route path="/admin/users" element={page("Users")} />
//           <Route path="/admin/categories" element={page("Categories")} />
//           <Route path="/admin/activities" element={page("All activities")} />
//           <Route path="/admin/reports" element={page("Reports")} />
//           <Route path="/admin/announcements" element={page("Announcements")} />
//         </Route>

//         <Route path="*" element={page("Page not found")} />
//       </Route>
//     </Routes>
//   );
// }



import { Route, Routes } from "react-router-dom";

import MainLayout from "../components/layout/MainLayout";
import ProtectedRoute from "./ProtectedRoute";

import HomePage from "../pages/public/HomePage";
import LoginPage from "../pages/public/LoginPage";
import CreateAccount from "../pages/public/CreateAccount";
import ActivityDetail from "../components/common/ActivityDetail";
import Dashboard from "../pages/public/Dashboard";
import VerifyEmailPage from "../pages/public/VerifyEmailPage";
import PlaceholderPage from "../pages/PlaceholderPage";

import UserDashboard from "../pages/dashboards/UserDashboard";

import ProfilePage from "../pages/profile/ProfilePage";
import EditProfilePage from "../pages/profile/EditProfilePage";
import PrivacySettingsPage from "../pages/profile/PrivacySettingsPage";
import AccountSettingsPage from "../pages/profile/AccountSettingsPage";

// Achievement pages
import MyAchievementsPage from "../pages/achievements/MyAchievementsPage";
import AddAchievementPage from "../pages/achievements/AddAchievementPage";
import EditAchievementPage from "../pages/achievements/EditAchievementPage";
import AchievementDetailPage from "../pages/achievements/AchievementDetailPage";

// activities
import ActivitiesPage from "../pages/activities/ActivitiesPage";

// Pages that are not built yet
const page = (title: string) => <PlaceholderPage title={title} />;

export default function AppRoutes() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        {/* Public Routes */}
        <Route path="/" element={<HomePage />} />
        <Route path="/activities" element={page("All activities")} />
        <Route path="/activities/:id" element={<ActivityDetail />} />

        <Route path="/login" element={<LoginPage />} />
        <Route path="/CreateAccount" element={<CreateAccount />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/verify/:code" element={page("Verify a certificate")} />
        <Route path="/dashboard-view" element={<Dashboard />} />

        {/* User / Student Routes */}
        <Route element={<ProtectedRoute role="user" />}>
          <Route path="/dashboard" element={<UserDashboard />} />

          {/* Achievements */}
          <Route
            path="/dashboard/achievements"
            element={<MyAchievementsPage />}
          />

          <Route
            path="/dashboard/achievements/add"
            element={<AddAchievementPage />}
          />

          <Route
            path="/dashboard/achievements/:id"
            element={<AchievementDetailPage />}
          />

          <Route
            path="/dashboard/achievements/:id/edit"
            element={<EditAchievementPage />}
          />
          {/* activities  */}
          <Route
          path="/dashboard/activities"
          element={<ActivitiesPage />}
          />
          {/* Profile */}
          <Route path="/dashboard/profile" element={<ProfilePage />} />

          <Route
            path="/dashboard/profile/edit"
            element={<EditProfilePage />}
          />

          <Route
            path="/dashboard/profile/privacy"
            element={<PrivacySettingsPage />}
          />

          <Route
            path="/dashboard/profile/account"
            element={<AccountSettingsPage />}
          />

          {/* Other user pages */}
          <Route
            path="/dashboard/activities"
            element={page("My activities")}
          />

          {/* Certificates now opens My Achievements */}
          <Route
            path="/dashboard/certificates"
            element={<MyAchievementsPage />}
          />

          <Route
            path="/dashboard/notifications"
            element={page("Notifications")}
          />
        </Route>

        {/* Coordinator Routes */}
        <Route element={<ProtectedRoute role="coordinator" />}>
          <Route
            path="/coordinator/dashboard"
            element={page("Coordinator dashboard")}
          />

          <Route
            path="/coordinator/activities"
            element={page("Manage activities")}
          />

          <Route
            path="/coordinator/registrations"
            element={page("Registrations")}
          />

          <Route
            path="/coordinator/attendance"
            element={page("Attendance")}
          />

          <Route
            path="/coordinator/achievements"
            element={page("Achievements")}
          />
        </Route>

        {/* Admin Routes */}
        <Route element={<ProtectedRoute role="admin" />}>
          <Route
            path="/admin/dashboard"
            element={page("Admin dashboard")}
          />

          <Route path="/admin/users" element={page("Users")} />
          <Route path="/admin/categories" element={page("Categories")} />
          <Route path="/admin/activities" element={page("All activities")} />
          <Route path="/admin/reports" element={page("Reports")} />

          <Route
            path="/admin/announcements"
            element={page("Announcements")}
          />
        </Route>

        {/* Not Found */}
        <Route path="*" element={page("Page not found")} />
      </Route>
    </Routes>
  );
}
