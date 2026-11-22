import { MailCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/common/Button";
import { Input } from "@/components/common/Field";
import { OtpInput } from "@/components/common/OtpInput";
import { useCooldown } from "@/hooks/useCooldown";
import { AuthLayout } from "@/layouts/AuthLayout";
import { authApi } from "@/services/api/auth";
import { errorMessage, toApiError } from "@/services/api/errors";

export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [otp, setOtp] = useState("");
  const [error, setError] = useState<string>();
  const [submitting, setSubmitting] = useState(false);
  const [resending, setResending] = useState(false);
  const [cooldown, setCooldown] = useCooldown(params.get("sent") ? 60 : 0);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(undefined);
    if (otp.length !== 6) return setError("Enter the 6-digit code from the email.");
    setSubmitting(true);
    try {
      const result = await authApi.verifyEmail(email.trim(), otp);
      toast.success(result.message);
      navigate(`/login?email=${encodeURIComponent(email.trim())}`, { replace: true });
    } catch (err) {
      const apiError = toApiError(err);
      setError(apiError.fieldErrors.otp?.[0] ?? apiError.fieldErrors.email?.[0] ?? apiError.message);
    } finally {
      setSubmitting(false);
    }
  };

  const resend = async () => {
    if (!email.trim()) return setError("Enter your email address first.");
    setResending(true);
    try {
      const result = await authApi.resendOtp(email.trim());
      toast.success(result.message);
      setCooldown(60);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setResending(false);
    }
  };

  return (
    <AuthLayout
      title="Verify your email"
      subtitle={<>We sent a 6-digit code to <strong className="text-slate-700">{email || "your email"}</strong>. It expires in a few minutes.</>}
      footer={<>Already verified? <Link to="/login" className="font-semibold text-brand-700 hover:underline">Log in</Link></>}
    >
      <form onSubmit={submit} className="space-y-5" noValidate>
        {!params.get("email") && <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />}
        <OtpInput value={otp} onChange={setOtp} error={error} />
        <Button type="submit" size="lg" block loading={submitting} icon={<MailCheck className="h-4 w-4" />}>Verify email</Button>
        <p className="text-center text-sm text-slate-500">
          Didn&apos;t get it?{" "}
          <button type="button" onClick={resend} disabled={cooldown > 0 || resending} className="font-semibold text-brand-700 hover:underline disabled:text-slate-400 disabled:no-underline">
            {cooldown > 0 ? `Resend in ${cooldown}s` : resending ? "Sending…" : "Resend code"}
          </button>
        </p>
      </form>
    </AuthLayout>
  );
}
