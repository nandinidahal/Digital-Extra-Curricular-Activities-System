
import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

export default function VerifyEmailPage() {
  const location = useLocation();
  const navigate = useNavigate();

  const email = location.state?.email || "";

  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [resending, setResending] = useState(false);

  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

  // Handle API error messages from Django
  const getErrorMessage = (data: Record<string, unknown>) => {
    return Object.entries(data)
      .map(([key, value]) => {
        const text = Array.isArray(value)
          ? value.join(", ")
          : typeof value === "string"
            ? value
            : JSON.stringify(value);

        return `${key.replace(/_/g, " ")}: ${text}`;
      })
      .join(" ");
  };

  // Verify email OTP
  const handleVerify = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    setError("");
    setMessage("");

    if (!email) {
      setError("Email address is missing. Please register again.");
      return;
    }

    if (!/^\d{6}$/.test(otp)) {
      setError("Please enter a valid 6-digit verification code.");
      return;
    }

    setBusy(true);

    try {
      const response = await fetch(
        `${API_BASE_URL}/auth/verify-email/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            email,
            otp,
          }),
        }
      );

      const data: Record<string, unknown> = await response.json();

      if (!response.ok) {
        throw new Error(
          getErrorMessage(data) || "Email verification failed."
        );
      }

      setMessage("Your email has been verified successfully!");

      // Redirect to login after successful verification
      navigate("/login", {
        state: {
          email,
          message: "Email verified successfully. Please log in.",
        },
      });
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong. Please try again."
      );
    } finally {
      setBusy(false);
    }
  };

  // Resend verification OTP
  const handleResendOTP = async () => {
    setError("");
    setMessage("");

    if (!email) {
      setError("Email address is missing. Please register again.");
      return;
    }

    setResending(true);

    try {
      const response = await fetch(
        `${API_BASE_URL}/auth/resend-otp/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ email }),
        }
      );

      const data: Record<string, unknown> = await response.json();

      if (!response.ok) {
        throw new Error(
          getErrorMessage(data) || "Could not resend the verification code."
        );
      }

      setMessage(
        typeof data.message === "string"
          ? data.message
          : "A new verification code has been sent to your email."
      );

      setOtp("");
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not resend verification code."
      );
    } finally {
      setResending(false);
    }
  };

  return (
    <section className="container-page grid min-h-screen place-items-center py-16">
      <div className="w-full max-w-md rounded-2xl border border-pine-100 bg-white p-8 shadow-sm">

        {/* Email Icon */}
        <div className="mx-auto mb-5 grid h-16 w-16 place-items-center rounded-full bg-pine-50 text-pine-700">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="32"
            height="32"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="3" y="5" width="18" height="14" rx="2" />
            <path d="m3 7 9 6 9-6" />
          </svg>
        </div>

        <h1 className="text-center text-2xl font-bold">
          Verify your email
        </h1>

        <p className="mt-2 text-center text-sm text-ink/70">
          We've sent a 6-digit verification code to your email address.
          Enter the code below to activate your account.
        </p>

        {/* Email Address */}
        <div className="mt-6 rounded-lg bg-pine-50 p-3 text-center">
          <p className="text-xs text-ink/60">
            Verification email sent to
          </p>
          <p className="mt-1 break-all font-semibold text-pine-700">
            {email || "Email address unavailable"}
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div
            role="alert"
            className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
          >
            {error}
          </div>
        )}

        {/* Success Message */}
        {message && (
          <div
            role="status"
            className="mt-4 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700"
          >
            {message}
          </div>
        )}

        {/* Verification Form */}
        <form onSubmit={handleVerify}>
          <label
            htmlFor="otp"
            className="mt-6 block text-sm font-medium"
          >
            Enter verification code
          </label>

          <input
            id="otp"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            placeholder="Enter 6-digit code"
            value={otp}
            onChange={(e) =>
              setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))
            }
            className="mt-2 w-full rounded-lg border border-pine-100 px-4 py-3 text-center text-xl tracking-[0.5em] outline-none focus:border-pine-600"
          />

          <button
            type="submit"
            disabled={busy || !email}
            className="btn-primary mt-5 w-full disabled:opacity-60"
          >
            {busy ? "Verifying..." : "Verify Email"}
          </button>
        </form>

        {/* Resend Code */}
        <div className="mt-5 text-center">
          <p className="text-sm text-ink/70">
            Didn't receive the code?
          </p>

          <button
            type="button"
            onClick={handleResendOTP}
            disabled={resending || !email}
            className="mt-2 text-sm font-semibold text-pine-700 hover:underline disabled:opacity-50"
          >
            {resending ? "Sending..." : "Resend verification code"}
          </button>
        </div>

        <div className="mt-6 border-t border-pine-100 pt-5 text-center">
          <Link
            to="/login"
            className="text-sm font-semibold text-pine-700 hover:underline"
          >
            Back to Login
          </Link>
        </div>

      </div>
    </section>
  );
}
