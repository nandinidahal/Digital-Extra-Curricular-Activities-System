import { zodResolver } from "@hookform/resolvers/zod";
import { UserPlus } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";
import { Button } from "@/components/common/Button";
import { Input, PasswordInput } from "@/components/common/Field";
import { PasswordStrength } from "@/components/common/PasswordStrength";
import { AuthLayout } from "@/layouts/AuthLayout";
import { authApi } from "@/services/api/auth";
import { applyServerErrors } from "@/utils/forms";

// Mirrors accounts/validators.py and accounts/serializers.py (the server re-checks everything).
const today = new Date();
const minAgeDate = new Date(today.getFullYear() - 13, today.getMonth(), today.getDate());

const schema = z
  .object({
    full_name: z.string().trim().min(2, "Enter your full name.").max(150),
    username: z.string().trim().regex(/^[A-Za-z0-9_.]{3,30}$/, "3-30 characters: letters, numbers, _ and . only."),
    email: z.string().trim().email("Enter a valid email address.").max(254),
    phone_number: z.string().trim().refine((v) => /^\+?[1-9]\d{7,14}$/.test(v.replace(/[\s\-().]/g, "")), "Use international format, e.g. +9779812345678."),
    country: z.string().trim().min(2, "Enter your country.").max(100),
    date_of_birth: z.string().min(1, "Enter your date of birth.").refine((v) => new Date(v) <= minAgeDate, "You must be at least 13 years old."),
    password: z.string().min(8, "Use at least 8 characters.").max(128).refine((v) => !/^\d+$/.test(v), "Password cannot be only numbers."),
    confirm_password: z.string(),
  })
  .refine((v) => v.password === v.confirm_password, { message: "Passwords do not match.", path: ["confirm_password"] });

type Values = z.infer<typeof schema>;
const FIELDS = ["full_name", "username", "email", "phone_number", "country", "date_of_birth", "password", "confirm_password"] as const;

export default function RegisterPage() {
  const navigate = useNavigate();
  const { register, handleSubmit, setError, watch, formState: { errors, isSubmitting } } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { full_name: "", username: "", email: "", phone_number: "", country: "", date_of_birth: "", password: "", confirm_password: "" },
  });

  const onSubmit = async (values: Values) => {
    try {
      const result = await authApi.register({ ...values, phone_number: values.phone_number.replace(/[\s\-().]/g, "") });
      toast.success(result.message);
      navigate(`/verify-email?email=${encodeURIComponent(values.email)}&sent=1`, { replace: true });
    } catch (error) {
      applyServerErrors(error, setError, FIELDS);
    }
  };

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Join DEAS to share activities, discover opportunities and build your portfolio."
      footer={<>Already have an account? <Link to="/login" className="font-semibold text-brand-700 hover:underline">Log in</Link></>}
    >
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <Input label="Full name" required autoComplete="name" error={errors.full_name?.message} {...register("full_name")} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Username" required autoComplete="username" error={errors.username?.message} {...register("username")} />
          <Input label="Email" required type="email" autoComplete="email" error={errors.email?.message} {...register("email")} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Phone number" required type="tel" autoComplete="tel" placeholder="+9779812345678" error={errors.phone_number?.message} {...register("phone_number")} />
          <Input label="Country" required autoComplete="country-name" error={errors.country?.message} {...register("country")} />
        </div>
        <Input label="Date of birth" required type="date" max={minAgeDate.toISOString().slice(0, 10)} error={errors.date_of_birth?.message} {...register("date_of_birth")} />
        <div>
          <PasswordInput label="Password" required autoComplete="new-password" error={errors.password?.message} {...register("password")} />
          <PasswordStrength password={watch("password")} />
        </div>
        <PasswordInput label="Confirm password" required autoComplete="new-password" error={errors.confirm_password?.message} {...register("confirm_password")} />
        <Button type="submit" size="lg" block loading={isSubmitting} icon={<UserPlus className="h-4 w-4" />}>Create account</Button>
        <p className="text-center text-xs text-slate-500">We will email you a 6-digit code to verify your address.</p>
      </form>
    </AuthLayout>
  );
}
