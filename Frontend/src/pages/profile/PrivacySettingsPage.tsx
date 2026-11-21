
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  LoaderCircle,
  Save,
  ShieldCheck,
  Lock,
  Globe,
  Mail,
  CalendarDays,
  FileText,
} from "lucide-react";

import DashboardLayout from "../../components/dashboard/DashboardLayout";
import profileService from "../../services/profileService";
import type { PrivacySettings } from "../../types/profile";

import {
  LayoutDashboard,
  ClipboardList,
  GraduationCap,
  CircleUserRound,
} from "lucide-react";

const navItems = [
  { label: "Overview", path: "/dashboard", icon: LayoutDashboard },
  { label: "My Activities", path: "/dashboard/activities", icon: ClipboardList },
  { label: "Certificates", path: "/dashboard/certificates", icon: GraduationCap },
  { label: "My Profile", path: "/dashboard/profile", icon: CircleUserRound },
];

const defaultSettings: PrivacySettings = {
  profile_visibility: "private",
  email_visibility: "private",
  date_of_birth_visibility: "private",
  bio_visibility: "public",
};

type VisibilityFieldProps = {
  title: string;
  description: string;
  icon: React.ReactNode;
  value: "public" | "private";
  onChange: (value: "public" | "private") => void;
};

function VisibilityField({
  title,
  description,
  icon,
  value,
  onChange,
}: VisibilityFieldProps) {
  return (
    <div className="flex flex-col gap-4 border-b border-gray-100 py-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3">
        <span className="mt-1 text-[#315C4A]">{icon}</span>

        <div>
          <h3 className="text-sm font-semibold text-gray-800">
            {title}
          </h3>
          <p className="mt-1 text-sm text-gray-500">
            {description}
          </p>
        </div>
      </div>

      <select
        value={value}
        onChange={(event) =>
          onChange(event.target.value as "public" | "private")
        }
        className="rounded-lg border border-gray-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-[#315C4A]"
      >
        <option value="public">Public</option>
        <option value="private">Private</option>
      </select>
    </div>
  );
}

export default function PrivacySettingsPage() {
  const [settings, setSettings] =
    useState<PrivacySettings>(defaultSettings);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const data = await profileService.getPrivacySettings();

        // Supports either direct privacy fields or a nested privacy object.
        const privacy = data.privacy ?? data;

        setSettings({
          profile_visibility:
            privacy.profile_visibility ?? "private",
          email_visibility:
            privacy.email_visibility ?? "private",
          date_of_birth_visibility:
            privacy.date_of_birth_visibility ?? "private",
          bio_visibility:
            privacy.bio_visibility ?? "public",
        });
      } catch (err) {
        console.error("Privacy settings error:", err);
        setError("Unable to load privacy settings.");
      } finally {
        setLoading(false);
      }
    };

    loadSettings();
  }, []);

  const updateSetting = (
    field: keyof PrivacySettings,
    value: "public" | "private"
  ) => {
    setSettings((previous) => ({
      ...previous,
      [field]: value,
    }));

    setSuccess("");
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setSaving(true);
    setError("");
    setSuccess("");

    try {
      await profileService.updatePrivacySettings(settings);
      setSuccess("Privacy settings updated successfully.");
    } catch (err) {
      console.error("Privacy update error:", err);
      setError("Unable to save privacy settings. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout
      role="user"
      title="Privacy Settings"
      subtitle="Control who can see your profile information."
      navItems={navItems}
    >
      <div className="mx-auto max-w-3xl space-y-6">
        <Link
          to="/dashboard/profile"
          className="inline-flex items-center gap-2 text-sm font-medium text-[#315C4A] hover:underline"
        >
          <ArrowLeft size={17} />
          Back to Profile
        </Link>

        <section className="rounded-xl border border-[#E1EAE4] bg-white p-6 sm:p-8">
          <div className="mb-6 flex items-center gap-3">
            <div className="rounded-lg bg-[#E8F1EC] p-3 text-[#315C4A]">
              <ShieldCheck size={24} />
            </div>

            <div>
              <h2 className="text-xl font-bold text-gray-800">
                Privacy Preferences
              </h2>
              <p className="mt-1 text-sm text-gray-500">
                Choose which information is visible to others.
              </p>
            </div>
          </div>

          {loading ? (
            <div className="flex justify-center py-12">
              <LoaderCircle
                size={30}
                className="animate-spin text-[#315C4A]"
              />
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              {error && (
                <p className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-600">
                  {error}
                </p>
              )}

              {success && (
                <p className="mb-4 rounded-lg bg-green-50 p-3 text-sm text-green-700">
                  {success}
                </p>
              )}

              <VisibilityField
                title="Profile Visibility"
                description="Control whether other people can view your public profile."
                icon={<Globe size={20} />}
                value={settings.profile_visibility}
                onChange={(value) =>
                  updateSetting("profile_visibility", value)
                }
              />

              <VisibilityField
                title="Email Visibility"
                description="Choose whether your email address is visible on your public profile."
                icon={<Mail size={20} />}
                value={settings.email_visibility}
                onChange={(value) =>
                  updateSetting("email_visibility", value)
                }
              />

              <VisibilityField
                title="Date of Birth Visibility"
                description="Control who can see your date of birth."
                icon={<CalendarDays size={20} />}
                value={settings.date_of_birth_visibility}
                onChange={(value) =>
                  updateSetting("date_of_birth_visibility", value)
                }
              />

              <VisibilityField
                title="Bio Visibility"
                description="Choose whether other people can read your profile introduction."
                icon={<FileText size={20} />}
                value={settings.bio_visibility}
                onChange={(value) =>
                  updateSetting("bio_visibility", value)
                }
              />

              <div className="mt-6 flex justify-end">
                <button
                  type="submit"
                  disabled={saving}
                  className="flex items-center gap-2 rounded-lg bg-[#315C4A] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#264A3B] disabled:opacity-60"
                >
                  {saving ? (
                    <LoaderCircle
                      size={17}
                      className="animate-spin"
                    />
                  ) : (
                    <Save size={17} />
                  )}

                  {saving ? "Saving..." : "Save Settings"}
                </button>
              </div>
            </form>
          )}
        </section>

        <div className="flex items-start gap-3 rounded-xl bg-[#E8F1EC] p-4">
          <Lock size={19} className="mt-0.5 shrink-0 text-[#315C4A]" />
          <p className="text-sm leading-6 text-gray-600">
            Private information is restricted according to your
            account's privacy settings. Your account information
            and authentication details are managed separately.
          </p>
        </div>
      </div>
    </DashboardLayout>
  );
}
