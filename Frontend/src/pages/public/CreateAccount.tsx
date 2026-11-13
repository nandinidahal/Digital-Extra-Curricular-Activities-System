
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

export default function CreateAccount() {
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (!fullName || !username || !email || !password || !confirmPassword) {
      return setError("Please fill in all fields.");
    }

    if (password !== confirmPassword) {
      return setError("Passwords do not match.");
    }

    if (password.length < 8) {
      return setError("Password must be at least 8 characters long.");
    }

    setBusy(true);
    setError("");

    try {
      // Connect your registration API here.
      // Example: await register({ fullName, username, email, password });

      navigate("/login");
    } catch (err: any) {
      setError(
        err.response?.data?.detail ??
          "Could not create your account. Please try again."
      );
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
        <h1 className="text-2xl font-bold">Create your account</h1>

        <p className="mt-1 text-sm text-ink/70">
          Join us to manage your activities and certificates.
        </p>

        {error && (
          <p
            role="alert"
            className="mt-4 rounded-md bg-red-50 p-3 text-sm text-brick"
          >
            {error}
          </p>
        )}

        <label htmlFor="fullName" className="mt-5 block text-sm font-medium">
          Full name
        </label>
        <input
          id="fullName"
          type="text"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          className="mt-1 w-full rounded-lg border border-pine-100 px-3 py-2.5"
          autoComplete="name"
        />

        <label htmlFor="username" className="mt-4 block text-sm font-medium">
          Username
        </label>
        <input
          id="username"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="mt-1 w-full rounded-lg border border-pine-100 px-3 py-2.5"
          autoComplete="username"
        />

        <label htmlFor="email" className="mt-4 block text-sm font-medium">
          Email address
        </label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mt-1 w-full rounded-lg border border-pine-100 px-3 py-2.5"
          autoComplete="email"
        />

        <label htmlFor="password" className="mt-4 block text-sm font-medium">
          Password
        </label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 w-full rounded-lg border border-pine-100 px-3 py-2.5"
          autoComplete="new-password"
        />

        <label
          htmlFor="confirmPassword"
          className="mt-4 block text-sm font-medium"
        >
          Confirm password
        </label>
        <input
          id="confirmPassword"
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          className="mt-1 w-full rounded-lg border border-pine-100 px-3 py-2.5"
          autoComplete="new-password"
        />

        <button
          type="submit"
          disabled={busy}
          className="btn-primary mt-6 w-full disabled:opacity-60"
        >
          {busy ? "Creating account…" : "Create account"}
        </button>

        <p className="mt-4 text-center text-sm text-ink/70">
          Already have an account?{" "}
          <Link to="/login" className="font-semibold text-pine-700">
            Log in
          </Link>
        </p>
      </form>
    </section>
  );
}
