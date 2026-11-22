import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { EmptyState, PageLoader } from "./components/common/Feedback";
import { useAuth } from "./contexts/AuthContext";
import { AppLayout } from "./layouts/AppLayout";
import { PublicLayout } from "./layouts/PublicLayout";
import { RequireAuth, RequireGuest, RequireModerator } from "./routes/guards";

const LandingPage = lazy(() => import("./pages/public/LandingPage"));
const LoginPage = lazy(() => import("./pages/auth/LoginPage"));
const RegisterPage = lazy(() => import("./pages/auth/RegisterPage"));
const VerifyEmailPage = lazy(() => import("./pages/auth/VerifyEmailPage"));
const ForgotPasswordPage = lazy(() => import("./pages/auth/ForgotPasswordPage"));
const HomePage = lazy(() => import("./pages/home/HomePage"));
const PostPage = lazy(() => import("./pages/home/PostPage"));
const AnnouncementsPage = lazy(() => import("./pages/announcements/AnnouncementsPage"));
const AnnouncementDetailPage = lazy(() => import("./pages/announcements/AnnouncementDetailPage"));
const AnnouncementFormPage = lazy(() => import("./pages/announcements/AnnouncementFormPage"));
const AchievementsPage = lazy(() => import("./pages/achievements/AchievementsPage"));
const AchievementDetailPage = lazy(() => import("./pages/achievements/AchievementDetailPage"));
const AchievementFormPage = lazy(() => import("./pages/achievements/AchievementFormPage"));
const FriendsPage = lazy(() => import("./pages/friends/FriendsPage"));
const MessagesPage = lazy(() => import("./pages/messaging/MessagesPage"));
const NotificationsPage = lazy(() => import("./pages/notifications/NotificationsPage"));
const ProfilePage = lazy(() => import("./pages/profile/ProfilePage"));
const EditProfilePage = lazy(() => import("./pages/profile/EditProfilePage"));
const SettingsPage = lazy(() => import("./pages/settings/SettingsPage"));
const ModerationPage = lazy(() => import("./pages/moderation/ModerationPage"));

/** "/" is the public landing page for visitors and the feed for logged-in users. */
function Root() {
  const { status } = useAuth();
  if (status === "loading") return <PageLoader />;
  return status === "authenticated" ? <Navigate to="/home" replace /> : <LandingPage />;
}

/** Notification links use /achievements/review/<id>; reviewers handle it on the detail page. */
function ReviewRedirect() {
  const { id } = useParams();
  return <Navigate to={`/achievements/${id}`} replace />;
}

function NotFound() {
  return (
    <div className="mx-auto max-w-lg py-20">
      <EmptyState title="Page not found" description="The page you are looking for does not exist or was moved." />
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route index element={<Root />} />
        </Route>

        <Route element={<RequireGuest />}>
          <Route path="login" element={<LoginPage />} />
          <Route path="register" element={<RegisterPage />} />
        </Route>
        <Route path="verify-email" element={<VerifyEmailPage />} />
        <Route path="forgot-password" element={<ForgotPasswordPage />} />

        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>
            <Route path="home" element={<HomePage />} />
            <Route path="social/posts/:postId" element={<PostPage />} />

            <Route path="announcements" element={<AnnouncementsPage />} />
            <Route path="announcements/new" element={<AnnouncementFormPage />} />
            <Route path="announcements/:id" element={<AnnouncementDetailPage />} />
            <Route path="announcements/:id/edit" element={<AnnouncementFormPage />} />

            <Route path="achievements" element={<AchievementsPage />} />
            <Route path="achievements/new" element={<AchievementFormPage />} />
            <Route path="achievements/review/:id" element={<ReviewRedirect />} />
            <Route path="achievements/:id" element={<AchievementDetailPage />} />
            <Route path="achievements/:id/edit" element={<AchievementFormPage />} />

            <Route path="friends" element={<FriendsPage />} />
            <Route path="friends/:tab" element={<FriendsPage />} />

            <Route path="messages" element={<MessagesPage />} />
            <Route path="messages/:conversationId" element={<MessagesPage />} />

            <Route path="notifications" element={<NotificationsPage />} />

            <Route path="profile" element={<ProfilePage />} />
            <Route path="profile/edit" element={<EditProfilePage />} />
            <Route path="profile/:userId" element={<ProfilePage />} />

            <Route path="settings" element={<SettingsPage />} />
            <Route path="settings/:section" element={<SettingsPage />} />

            <Route element={<RequireModerator />}>
              <Route path="moderation" element={<ModerationPage />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  );
}
