
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  LoaderCircle,
  Pencil,
  CalendarDays,
  Mail,
  Phone,
  MapPin,
  ShieldCheck,
  CircleUserRound,
  LayoutDashboard,
  ClipboardList,
  GraduationCap,
} from "lucide-react";

import DashboardLayout from "../../components/dashboard/DashboardLayout";
import ProfilePicture from "../../components/profile/ProfilePicture";
import profileService from "../../services/profileService";
import type { UserProfile } from "../../types/profile";

// Dashboard navigation
const navItems = [
  {
    label: "Overview",
    path: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    label: "My Activities",
    path: "/dashboard/activities",
    icon: ClipboardList,
  },
  {
    label: "Certificates",
    path: "/dashboard/certificates",
    icon: GraduationCap,
  },
  {
    label: "My Profile",
    path: "/dashboard/profile",
    icon: CircleUserRound,
  },
];

// Reusable information component
type InfoProps = {
  label: string;
  value: string;
  icon: ReactNode;
};

function Info({ label, value, icon }: InfoProps) {
  return (
    <div className="flex items-start gap-3">
      <span className="text-[#315C4A]">{icon}</span>

      <div>
        <p className="text-xs text-gray-400">{label}</p>
        <p className="mt-1 text-sm font-medium text-gray-800">
          {value || "Not provided"}
        </p>
      </div>
    </div>
  );
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Fetch logged-in user's profile
  useEffect(() => {
    const loadProfile = async () => {
      try {
        const data = await profileService.getMyProfile();
        setProfile(data);
      } catch (err) {
        console.error("Profile loading error:", err);
        setError("Unable to load your profile. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    loadProfile();
  }, []);

  // Update profile picture after upload or removal
  const updatePicture = (picture: string | null) => {
    setProfile((current) =>
      current
        ? {
            ...current,
            profile_picture_url: picture,
          }
        : current
    );
  };

  return (
    <DashboardLayout
      role="user"
      title="My Profile"
      subtitle="View and manage your personal information."
      navItems={navItems}
    >
      {loading ? (
        <div className="flex justify-center py-16">
          <LoaderCircle
            size={32}
            className="animate-spin text-[#315C4A]"
          />
        </div>
      ) : error ? (
        <div className="rounded-lg bg-red-50 p-4 text-sm text-red-600">
          {error}
        </div>
      ) : profile ? (
        <div className="space-y-6">

          {/* Profile Header */}
          <section className="rounded-xl border border-[#E1EAE4] bg-white p-6">
            <div className="flex flex-col items-center gap-6 sm:flex-row">

              <ProfilePicture
                picture={profile.profile_picture_url}
                onUpdated={updatePicture}
              />

              <div className="flex-1 text-center sm:text-left">
                <h2 className="text-2xl font-bold text-gray-800">
                  {profile.full_name}
                </h2>

                <p className="mt-1 text-sm text-gray-500">
                  @{profile.username}
                </p>

                <span className="mt-3 inline-block rounded-full bg-[#E8F1EC] px-3 py-1 text-xs font-semibold capitalize text-[#315C4A]">
                  {profile.role}
                </span>

                <p className="mt-3 flex items-center justify-center gap-2 text-sm text-gray-500 sm:justify-start">
                  <ShieldCheck size={16} />

                  {profile.is_email_verified
                    ? "Email verified"
                    : "Email not verified"}
                </p>
              </div>

              <Link
                to="/dashboard/profile/edit"
                className="flex items-center gap-2 rounded-lg bg-[#315C4A] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#264A3B]"
              >
                <Pencil size={16} />
                Edit Profile
              </Link>
            </div>
          </section>

          {/* Personal Information */}
          <section className="rounded-xl border border-[#E1EAE4] bg-white p-6">
            <h3 className="mb-6 text-lg font-bold text-gray-800">
              Personal Information
            </h3>

            <div className="grid gap-6 sm:grid-cols-2">
              <Info
                label="Full Name"
                value={profile.full_name}
                icon={<CircleUserRound size={19} />}
              />

              <Info
                label="Username"
                value={profile.username}
                icon={<CircleUserRound size={19} />}
              />

              <Info
                label="Email Address"
                value={profile.email}
                icon={<Mail size={19} />}
              />

              <Info
                label="Phone Number"
                value={profile.phone_number}
                icon={<Phone size={19} />}
              />

              <Info
                label="Country"
                value={profile.country}
                icon={<MapPin size={19} />}
              />

              <Info
                label="Date of Birth"
                value={
                  profile.date_of_birth
                    ? new Date(profile.date_of_birth).toLocaleDateString()
                    : ""
                }
                icon={<CalendarDays size={19} />}
              />
            </div>

            {/* Bio */}
            <div className="mt-7 border-t border-gray-100 pt-5">
              <p className="text-xs text-gray-400">
                About Me
              </p>

              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-gray-600">
                {profile.bio || "You have not added a bio yet."}
              </p>
            </div>
          </section>

          {/* Account Information */}
          <section className="rounded-xl border border-[#E1EAE4] bg-white p-6">
            <h3 className="text-lg font-bold text-gray-800">
              Account Information
            </h3>

            <div className="mt-5 grid gap-5 sm:grid-cols-2">
              <Info
                label="Account Role"
                value={profile.role}
                icon={<ShieldCheck size={19} />}
              />

              <Info
                label="Account Status"
                value={profile.account_status}
                icon={<ShieldCheck size={19} />}
              />

              <Info
                label="Member Since"
                value={
                  profile.account_created_at
                    ? new Date(
                        profile.account_created_at
                      ).toLocaleDateString()
                    : ""
                }
                icon={<CalendarDays size={19} />}
              />
            </div>
          </section>

          {/* Settings Links */}
          <section className="flex flex-wrap gap-3">
            <Link
              to="/dashboard/profile/privacy"
              className="rounded-lg border border-[#315C4A] px-4 py-3 text-sm font-semibold text-[#315C4A] transition hover:bg-[#E8F1EC]"
            >
              Privacy Settings
            </Link>

            <Link
              to="/dashboard/profile/account"
              className="rounded-lg border border-[#315C4A] px-4 py-3 text-sm font-semibold text-[#315C4A] transition hover:bg-[#E8F1EC]"
            >
              Account Settings
            </Link>
          </section>
        </div>
      ) : null}
    </DashboardLayout>
  );
}
