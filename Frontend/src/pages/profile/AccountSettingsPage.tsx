
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  LoaderCircle,
  Mail,
  ShieldCheck,
  CalendarDays,
  UserRound,
  AlertTriangle,
  CheckCircle,
  Send,
  KeyRound,
} from "lucide-react";

import DashboardLayout from "../../components/dashboard/DashboardLayout";
import profileService from "../../services/profileService";
import type { AccountInformation } from "../../types/profile";

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

export default function AccountSettingsPage() {
  const navigate = useNavigate();

  const [account, setAccount] =
    useState<AccountInformation | null>(null);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [newEmail, setNewEmail] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [otp, setOtp] = useState("");

  const [otpSent, setOtpSent] = useState(false);
  const [showDeactivate, setShowDeactivate] = useState(false);

  const [deactivatePassword, setDeactivatePassword] =
    useState("");

  useEffect(() => {
    const loadAccount = async () => {
      try {
        const data = await profileService.getAccountInformation();
        setAccount(data);
      } catch (err) {
        console.error("Account loading error:", err);
        setError("Unable to load account information.");
      } finally {
        setLoading(false);
      }
    };

    loadAccount();
  }, []);

  const refreshAccount = async () => {
    const data = await profileService.getAccountInformation();
    setAccount(data);
  };

  const handleRequestEmailChange = async (
    event: FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault();

    setSaving(true);
    setError("");
    setSuccess("");

    try {
      await profileService.requestEmailChange(
        newEmail,
        currentPassword
      );

      setOtpSent(true);
      setSuccess(
        "Verification code sent. Please check your new email address."
      );
      setCurrentPassword("");
    } catch (err) {
      console.error("Email change request error:", err);
      setError("Unable to request email change. Check your details.");
    } finally {
      setSaving(false);
    }
  };

  const handleConfirmEmail = async (
    event: FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault();

    setSaving(true);
    setError("");
    setSuccess("");

    try {
      await profileService.confirmEmailChange(otp);

      setOtpSent(false);
      setOtp("");
      setNewEmail("");

      await refreshAccount();

      setSuccess("Your email address has been updated successfully.");
    } catch (err) {
      console.error("Email confirmation error:", err);
      setError("Invalid or expired verification code.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeactivate = async (
    event: FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault();

    setSaving(true);
    setError("");

    try {
      await profileService.deactivateAccount(
        deactivatePassword,
        true
      );

      localStorage.removeItem("xca_access");
      localStorage.removeItem("xca_refresh");

      navigate("/login", { replace: true });
    } catch (err) {
      console.error("Account deactivation error:", err);
      setError("Unable to deactivate account. Check your password.");
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <DashboardLayout
        role="user"
        title="Account Settings"
        subtitle="Manage your account information."
        navItems={navItems}
      >
        <div className="flex justify-center py-16">
          <LoaderCircle
            size={32}
            className="animate-spin text-[#315C4A]"
          />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="user"
      title="Account Settings"
      subtitle="Manage your account, email and security."
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

        {error && (
          <div className="rounded-lg bg-red-50 p-4 text-sm text-red-600">
            {error}
          </div>
        )}

        {success && (
          <div className="flex items-start gap-2 rounded-lg bg-green-50 p-4 text-sm text-green-700">
            <CheckCircle size={18} className="shrink-0" />
            {success}
          </div>
        )}

        {/* Account Information */}
        <section className="rounded-xl border border-[#E1EAE4] bg-white p-6">
          <div className="mb-6 flex items-center gap-3">
            <div className="rounded-lg bg-[#E8F1EC] p-3 text-[#315C4A]">
              <UserRound size={23} />
            </div>

            <div>
              <h2 className="text-lg font-bold text-gray-800">
                Account Information
              </h2>
              <p className="text-sm text-gray-500">
                Your account details.
              </p>
            </div>
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <p className="text-xs text-gray-400">Username</p>
              <p className="mt-1 text-sm font-medium">
                {account?.username || "Not available"}
              </p>
            </div>

            <div>
              <p className="text-xs text-gray-400">Account Role</p>
              <p className="mt-1 text-sm font-medium capitalize">
                {account?.role || "Not available"}
              </p>
            </div>

            <div>
              <p className="text-xs text-gray-400">Account Status</p>
              <p className="mt-1 text-sm font-medium capitalize">
                {account?.account_status || "Not available"}
              </p>
            </div>

            <div>
              <p className="text-xs text-gray-400">Email Verification</p>
              <p className="mt-1 flex items-center gap-2 text-sm font-medium">
                <ShieldCheck size={16} className="text-[#315C4A]" />
                {account?.is_email_verified
                  ? "Verified"
                  : "Not verified"}
              </p>
            </div>

            <div>
              <p className="text-xs text-gray-400">Account Created</p>
              <p className="mt-1 flex items-center gap-2 text-sm font-medium">
                <CalendarDays size={16} />
                {account?.account_created_at
                  ? new Date(
                      account.account_created_at
                    ).toLocaleDateString()
                  : "Not available"}
              </p>
            </div>

            <div>
              <p className="text-xs text-gray-400">Last Login</p>
              <p className="mt-1 text-sm font-medium">
                {account?.last_login
                  ? new Date(
                      account.last_login
                    ).toLocaleString()
                  : "Not available"}
              </p>
            </div>
          </div>
        </section>

        {/* Email Change */}
        <section className="rounded-xl border border-[#E1EAE4] bg-white p-6">
          <div className="mb-5 flex items-center gap-3">
            <div className="rounded-lg bg-[#E8F1EC] p-3 text-[#315C4A]">
              <Mail size={23} />
            </div>

            <div>
              <h2 className="text-lg font-bold text-gray-800">
                Email Address
              </h2>
              <p className="text-sm text-gray-500">
                Change your registered email address.
              </p>
            </div>
          </div>

          <div className="mb-5 rounded-lg bg-gray-50 p-4">
            <p className="text-xs text-gray-400">
              Current Email
            </p>
            <p className="mt-1 text-sm font-semibold text-gray-800">
              {account?.email}
            </p>

            {account?.pending_email && (
              <p className="mt-2 text-xs text-amber-700">
                Pending email: {account.pending_email}
              </p>
            )}
          </div>

          {!otpSent ? (
            <form
              onSubmit={handleRequestEmailChange}
              className="space-y-4"
            >
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  New Email Address
                </label>

                <input
                  type="email"
                  value={newEmail}
                  onChange={(event) =>
                    setNewEmail(event.target.value)
                  }
                  required
                  placeholder="Enter new email address"
                  className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm outline-none focus:border-[#315C4A]"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  Current Password
                </label>

                <input
                  type="password"
                  value={currentPassword}
                  onChange={(event) =>
                    setCurrentPassword(event.target.value)
                  }
                  required
                  placeholder="Enter your current password"
                  className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm outline-none focus:border-[#315C4A]"
                />
              </div>

              <button
                type="submit"
                disabled={saving}
                className="flex items-center gap-2 rounded-lg bg-[#315C4A] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#264A3B] disabled:opacity-60"
              >
                {saving ? (
                  <LoaderCircle size={17} className="animate-spin" />
                ) : (
                  <Send size={17} />
                )}

                {saving ? "Sending..." : "Send Verification Code"}
              </button>
            </form>
          ) : (
            <form
              onSubmit={handleConfirmEmail}
              className="space-y-4"
            >
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  Verification Code
                </label>

                <input
                  type="text"
                  value={otp}
                  onChange={(event) =>
                    setOtp(event.target.value)
                  }
                  required
                  maxLength={6}
                  placeholder="Enter the 6-digit OTP"
                  className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm outline-none focus:border-[#315C4A]"
                />
              </div>

              <div className="flex flex-wrap gap-3">
                <button
                  type="submit"
                  disabled={saving}
                  className="flex items-center gap-2 rounded-lg bg-[#315C4A] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#264A3B] disabled:opacity-60"
                >
                  {saving ? (
                    <LoaderCircle size={17} className="animate-spin" />
                  ) : (
                    <KeyRound size={17} />
                  )}

                  {saving ? "Verifying..." : "Verify Email"}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setOtpSent(false);
                    setOtp("");
                    setError("");
                    setSuccess("");
                  }}
                  className="rounded-lg border border-gray-200 px-5 py-2.5 text-sm font-medium text-gray-600 hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </section>

        {/* Deactivate Account */}
        <section className="rounded-xl border border-red-200 bg-white p-6">
          <div className="mb-5 flex items-center gap-3">
            <div className="rounded-lg bg-red-50 p-3 text-red-600">
              <AlertTriangle size={23} />
            </div>

            <div>
              <h2 className="text-lg font-bold text-gray-800">
                Deactivate Account
              </h2>
              <p className="text-sm text-gray-500">
                Temporarily deactivate your account.
              </p>
            </div>
          </div>

          <p className="mb-5 text-sm leading-6 text-gray-600">
            Deactivating your account will restrict access until
            you reactivate it using your existing account credentials.
          </p>

          {!showDeactivate ? (
            <button
              type="button"
              onClick={() => {
                setShowDeactivate(true);
                setError("");
              }}
              className="rounded-lg border border-red-300 px-5 py-2.5 text-sm font-semibold text-red-600 hover:bg-red-50"
            >
              Deactivate Account
            </button>
          ) : (
            <form
              onSubmit={handleDeactivate}
              className="space-y-4"
            >
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  Confirm Your Password
                </label>

                <input
                  type="password"
                  value={deactivatePassword}
                  onChange={(event) =>
                    setDeactivatePassword(event.target.value)
                  }
                  required
                  placeholder="Enter your current password"
                  className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm outline-none focus:border-red-400"
                />
              </div>

              <div className="flex flex-wrap gap-3">
                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-lg bg-red-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-60"
                >
                  {saving ? "Deactivating..." : "Confirm Deactivation"}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setShowDeactivate(false);
                    setDeactivatePassword("");
                    setError("");
                  }}
                  className="rounded-lg border border-gray-200 px-5 py-2.5 text-sm font-medium text-gray-600 hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </section>
      </div>
    </DashboardLayout>
  );
}
