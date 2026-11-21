
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { dashboardPath } from "../../utils/format";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!identifier.trim() || !password) {
      setError("Enter your email or username and your password.");
      return;
    }

    setBusy(true);
    setError("");

    try {
      const user = await login(identifier.trim(), password);

      navigate(dashboardPath(user.role), { replace: true });
    } catch (err: unknown) {
      let errorMessage =
        "Could not log in. Check your details and try again.";

      if (typeof err === "object" && err !== null && "response" in err) {
        const response = (
          err as {
            response?: {
              data?: {
                detail?: string;
                message?: string;
                non_field_errors?: string[];
              };
            };
          }
        ).response;

        errorMessage =
          response?.data?.detail ||
          response?.data?.message ||
          response?.data?.non_field_errors?.[0] ||
          errorMessage;
      } else if (err instanceof Error) {
        errorMessage = err.message;
      }

      setError(errorMessage);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="container-page grid place-items-center py-16">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md rounded-2xl border border-pine-100 bg-white p-8"
      >
        <h1 className="text-2xl font-bold">Welcome back</h1>

        <p className="mt-1 text-sm text-ink/70">
          Log in to see your activities and certificates.
        </p>

        {error && (
          <p
            role="alert"
            className="mt-4 rounded-md bg-red-50 p-3 text-sm text-brick"
          >
            {error}
          </p>
        )}

        <label
          htmlFor="identifier"
          className="mt-5 block text-sm font-medium"
        >
          Email or username
        </label>

        <input
          id="identifier"
          type="text"
          value={identifier}
          onChange={(e) => setIdentifier(e.target.value)}
          className="mt-1 w-full rounded-lg border border-pine-100 px-3 py-2.5"
          autoComplete="username"
          required
        />

        <label
          htmlFor="password"
          className="mt-4 block text-sm font-medium"
        >
          Password
        </label>

        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 w-full rounded-lg border border-pine-100 px-3 py-2.5"
          autoComplete="current-password"
          required
        />

        <div className="mt-3 text-right">
          <Link
            to="/forgot-password"
            className="text-sm font-semibold text-pine-700 hover:underline"
          >
            Forgot password?
          </Link>
        </div>

        <button
          type="submit"
          disabled={busy}
          className="btn-primary mt-6 w-full disabled:opacity-60"
        >
          {busy ? "Logging in…" : "Log in"}
        </button>

        <p className="mt-4 text-center text-sm text-ink/70">
          New here?{" "}
          <Link
            to="/register"
            className="font-semibold text-pine-700"
          >
            Create a student account
          </Link>
        </p>
      </form>
    </section>
  );
}
