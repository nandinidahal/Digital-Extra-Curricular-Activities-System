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

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!identifier || !password) return setError("Enter your email or username and your password.");
    setBusy(true);
    setError("");
    try {
      const user = await login(identifier, password);
      navigate(dashboardPath(user.role));
    } catch (err: any) {
      setError(err.response?.data?.detail ?? "Could not log in. Check your details and try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="container-page grid place-items-center py-16">
      <form onSubmit={handleSubmit} className="w-full max-w-md rounded-2xl border border-pine-100 bg-white p-8">
        <h1 className="text-2xl font-bold">Welcome back</h1>
        <p className="mt-1 text-sm text-ink/70">Log in to see your activities and certificates.</p>

        {error && <p role="alert" className="mt-4 rounded-md bg-red-50 p-3 text-sm text-brick">{error}</p>}

        <label htmlFor="identifier" className="mt-5 block text-sm font-medium">Email or username</label>
        <input id="identifier" value={identifier} onChange={(e) => setIdentifier(e.target.value)}
          className="mt-1 w-full rounded-lg border border-pine-100 px-3 py-2.5" autoComplete="username" />

        <label htmlFor="password" className="mt-4 block text-sm font-medium">Password</label>
        <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
          className="mt-1 w-full rounded-lg border border-pine-100 px-3 py-2.5" autoComplete="current-password" />

        <button disabled={busy} className="btn-primary mt-6 w-full disabled:opacity-60">
          {busy ? "Logging in…" : "Log in"}
        </button>

        <p className="mt-4 text-center text-sm text-ink/70">
          New here? <Link to="/register" className="font-semibold text-pine-700">Create a student account</Link>
        </p>
      </form>
    </section>
  );
}
