import { zodResolver } from "@hookform/resolvers/zod";
import { LogIn } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";
import { Button } from "@/components/common/Button";
import { Input, PasswordInput } from "@/components/common/Field";
import { useAuth } from "@/contexts/AuthContext";
import { AuthLayout } from "@/layouts/AuthLayout";
import { safeNext } from "@/routes/guards";
import { toApiError } from "@/services/api/errors";
import { applyServerErrors } from "@/utils/forms";

const schema = z.object({
  email: z.string().trim().min(1, "Enter your email.").email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
  remember: z.boolean(),
});
type Values = z.infer<typeof schema>;

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [unverifiedEmail, setUnverifiedEmail] = useState<string | null>(null);
  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { email: params.get("email") ?? "", password: "", remember: true },
  });

  const onSubmit = async (values: Values) => {
    setUnverifiedEmail(null);
    try {
      const user = await login(values.email, values.password, values.remember);
      toast.success(`Welcome back, ${user.full_name.split(" ")[0]}!`);
      navigate(next, { replace: true });
    } catch (error) {
      const e = toApiError(error);
      if (e.code === "email_not_verified") {
        setUnverifiedEmail(values.email);
        return;
      }
      if (e.code === "invalid_credentials") {
        setError("password", { message: e.message });
        return;
      }
      applyServerErrors(error, setError, ["email", "password"]);
    }
  };

  return (
    <AuthLayout
      title="Welcome back"
      subtitle={next !== "/home" ? "Log in to continue to the page you requested." : "Log in to see your feed, friends and opportunities."}
      footer={<>New to DEAS? <Link to={`/register${next !== "/home" ? `?next=${encodeURIComponent(next)}` : ""}`} className="font-semibold text-brand-700 hover:underline">Create an account</Link></>}
    >
      {unverifiedEmail && (
        <div role="alert" className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          Your email is not verified yet.{" "}
          <Link to={`/verify-email?email=${encodeURIComponent(unverifiedEmail)}`} className="font-semibold underline">Verify it now</Link> to log in.
        </div>
      )}
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <Input label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register("email")} />
        <PasswordInput label="Password" autoComplete="current-password" error={errors.password?.message} {...register("password")} />
        <div className="flex items-center justify-between text-sm">
          <label className="inline-flex items-center gap-2 text-slate-600">
            <input type="checkbox" className="h-4 w-4 rounded border-slate-300 accent-brand-700" {...register("remember")} />
            Keep me signed in
          </label>
          <Link to="/forgot-password" className="font-medium text-brand-700 hover:underline">Forgot password?</Link>
        </div>
        <Button type="submit" size="lg" block loading={isSubmitting} icon={<LogIn className="h-4 w-4" />}>Log in</Button>
      </form>
    </AuthLayout>
  );
}
