
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

export default function CreateAccount() {
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [country, setCountry] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    // Validate required fields
    if (
      !fullName ||
      !username ||
      !email ||
      !password ||
      !confirmPassword ||
      !phoneNumber ||
      !country ||
      !dateOfBirth
    ) {
      setError("Please fill in all fields.");
      return;
    }

    // Check password confirmation
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    // Check password length
    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    setBusy(true);
    setError("");

    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_BASE_URL}/auth/register/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            full_name: fullName,
            username: username,
            email: email,
            phone_number: phoneNumber,
            country: country,
            date_of_birth: dateOfBirth,
            password: password,
            confirm_password: confirmPassword,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        const errorMessage =
          typeof data === "object"
            ? Object.entries(data)
                .map(([key, value]) => {
                  const message = Array.isArray(value)
                    ? value.join(", ")
                    : String(value);

                  return `${key}: ${message}`;
                })
                .join(" ")
            : "Registration failed.";

        throw new Error(errorMessage);
      }

      // Registration successful: continue to email verification.
      navigate("/verify-email", {
        state: { email },
      });

    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not create your account. Please try again."
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
        <h1 className="text-2xl font-bold">
          Create your account
        </h1>

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

        {/* Full Name */}
        <label
          htmlFor="fullName"
          className="mt-5 block text-sm font-medium"
        >
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

        {/* Username */}
        <label
          htmlFor="username"
          className="mt-4 block text-sm font-medium"
        >
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

        {/* Email */}
        <label
          htmlFor="email"
          className="mt-4 block text-sm font-medium"
        >
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

        {/* Phone Number */}
        <label
          htmlFor="phoneNumber"
          className="mt-4 block text-sm font-medium"
        >
          Phone Number
        </label>

        <input
          id="phoneNumber"
          type="tel"
          value={phoneNumber}
          onChange={(e) => setPhoneNumber(e.target.value)}
          className="mt-1 w-full rounded-lg border border-pine-100 px-3 py-2.5"
          autoComplete="tel"
        />

        {/* Country */}
        <label
          htmlFor="country"
          className="mt-4 block text-sm font-medium"
        >
          Country
        </label>

        <input
          id="country"
          type="text"
          value={country}
          onChange={(e) => setCountry(e.target.value)}
          className="mt-1 w-full rounded-lg border border-pine-100 px-3 py-2.5"
          autoComplete="country-name"
        />

        {/* Date of Birth */}
        <label
          htmlFor="dateOfBirth"
          className="mt-4 block text-sm font-medium"
        >
          Date of Birth
        </label>

        <input
          id="dateOfBirth"
          type="date"
          value={dateOfBirth}
          onChange={(e) => setDateOfBirth(e.target.value)}
          className="mt-1 w-full rounded-lg border border-pine-100 px-3 py-2.5"
          autoComplete="bday"
        />

        {/* Password */}
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
          autoComplete="new-password"
        />

        {/* Confirm Password */}
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

        {/* Submit Button */}
        <button
          type="submit"
          disabled={busy}
          className="btn-primary mt-6 w-full disabled:opacity-60"
        >
          {busy ? "Creating account…" : "Create account"}
        </button>

        <p className="mt-4 text-center text-sm text-ink/70">
          Already have an account?{" "}
          <Link
            to="/login"
            className="font-semibold text-pine-700"
          >
            Log in
          </Link>
        </p>
      </form>
    </section>
  );
}
