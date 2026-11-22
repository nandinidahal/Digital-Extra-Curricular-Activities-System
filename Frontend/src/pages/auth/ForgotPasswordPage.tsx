import { CheckCircle2, KeyRound, Mail } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/common/Button";
import { Input, PasswordInput } from "@/components/common/Field";
import { OtpInput } from "@/components/common/OtpInput";
import { PasswordStrength } from "@/components/common/PasswordStrength";
import { useCooldown } from "@/hooks/useCooldown";
import { AuthLayout } from "@/layouts/AuthLayout";
import { authApi } from "@/services/api/auth";
import { errorMessage, toApiError } from "@/services/api/errors";

type Step = "email" | "code" | "password" | "done";

/** Backend flow: forgot-password (email) -> verify-reset-otp (reset_token) -> reset-password. */
export default function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useCooldown();

  const requestCode = async (e?: FormEvent) => {
    e?.preventDefault();
    setErrors({});
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setErrors({ email: "Enter a valid email address." });
    setBusy(true);
    try {
      const result = await authApi.forgotPassword(email.trim());
      toast.success(result.message);
      setStep("code");
      setCooldown(60);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const verifyCode = async (e: FormEvent) => {
    e.preventDefault();
    setErrors({});
    if (otp.length !== 6) return setErrors({ otp: "Enter the 6-digit code." });
    setBusy(true);
    try {
      const result = await authApi.verifyResetOtp(email.trim(), otp);
      setToken(result.data.reset_token);
      setStep("password");
    } catch (err) {
      const apiError = toApiError(err);
      setErrors({ otp: apiError.fieldErrors.otp?.[0] ?? apiError.message });
    } finally {
      setBusy(false);
    }
  };

  const resetPassword = async (e: FormEvent) => {
    e.preventDefault();
    const local: Record<string, string> = {};
    if (password.length < 8) local.new_password = "Use at least 8 characters.";
    if (password !== confirm) local.confirm_password = "Passwords do not match.";
    setErrors(local);
    if (Object.keys(local).length) return;
    setBusy(true);
    try {
      await authApi.resetPassword(token, password, confirm);
      setStep("done");
    } catch (err) {
      const apiError = toApiError(err);
      if (apiError.code === "reset_token_invalid") {
        toast.error(apiError.message);
        setStep("email");
        return;
      }
      const fieldErrors = Object.fromEntries(Object.entries(apiError.fieldErrors).map(([k, v]) => [k, v[0]]));
      setErrors(fieldErrors);
      if (!Object.keys(fieldErrors).length) toast.error(apiError.message);
    } finally {
      setBusy(false);
    }
  };

  const steps = { email: "Reset your password", code: "Check your email", password: "Choose a new password", done: "Password updated" };

  return (
    <AuthLayout
      title={steps[step]}
      subtitle={
        step === "email" ? "Enter the email you registered with and we'll send you a 6-digit code."
          : step === "code" ? <>If an account exists for <strong className="text-slate-700">{email}</strong>, a code is on its way.</>
            : step === "password" ? "Your new password signs you out of every other device." : undefined
      }
      footer={<>Remembered it? <Link to="/login" className="font-semibold text-brand-700 hover:underline">Back to login</Link></>}
    >
      {step === "email" && (
        <form onSubmit={requestCode} className="space-y-5" noValidate>
          <Input label="Email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} error={errors.email} />
          <Button type="submit" size="lg" block loading={busy} icon={<Mail className="h-4 w-4" />}>Send code</Button>
        </form>
      )}
      {step === "code" && (
        <form onSubmit={verifyCode} className="space-y-5" noValidate>
          <OtpInput value={otp} onChange={setOtp} error={errors.otp} />
          <Button type="submit" size="lg" block loading={busy}>Verify code</Button>
          <p className="text-center text-sm text-slate-500">
            <button type="button" disabled={cooldown > 0 || busy} onClick={() => requestCode()} className="font-semibold text-brand-700 hover:underline disabled:text-slate-400 disabled:no-underline">
              {cooldown > 0 ? `Resend code in ${cooldown}s` : "Resend code"}
            </button>
          </p>
        </form>
      )}
      {step === "password" && (
        <form onSubmit={resetPassword} className="space-y-5" noValidate>
          <div>
            <PasswordInput label="New password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} error={errors.new_password} />
            <PasswordStrength password={password} />
          </div>
          <PasswordInput label="Confirm new password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} error={errors.confirm_password} />
          <Button type="submit" size="lg" block loading={busy} icon={<KeyRound className="h-4 w-4" />}>Reset password</Button>
        </form>
      )}
      {step === "done" && (
        <div className="space-y-5 text-center">
          <CheckCircle2 className="mx-auto h-14 w-14 text-emerald-500" />
          <p className="text-sm text-slate-600">Your password has been reset. You can now log in with your new password.</p>
          <Button size="lg" block onClick={() => navigate(`/login?email=${encodeURIComponent(email)}`)}>Go to login</Button>
        </div>
      )}
    </AuthLayout>
  );
}
