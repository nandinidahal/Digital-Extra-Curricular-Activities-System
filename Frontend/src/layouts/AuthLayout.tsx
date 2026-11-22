import { Award, Megaphone, MessageCircle, Users } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Logo } from "@/components/layout/Logo";

const points = [
  { icon: Megaphone, text: "Discover workshops, competitions and volunteering near you" },
  { icon: Award, text: "Build a verified portfolio of achievements and certificates" },
  { icon: Users, text: "Connect with friends who share your interests" },
  { icon: MessageCircle, text: "Message, plan and grow together" },
];

/** Split layout for login / register / OTP / password reset. */
export function AuthLayout({ title, subtitle, children, footer }: { title: string; subtitle?: ReactNode; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <aside className="relative hidden overflow-hidden bg-brand-800 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="absolute -top-24 -right-24 h-80 w-80 rounded-full bg-brand-600/40" aria-hidden />
        <div className="absolute -bottom-32 -left-20 h-96 w-96 rounded-full bg-brand-900/50" aria-hidden />
        <Link to="/" className="relative inline-flex items-center gap-2.5 text-white">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-lg font-bold text-brand-800">D</span>
          <span className="text-xl font-bold">DEAS</span>
        </Link>
        <div className="relative max-w-md">
          <p className="text-sm font-semibold tracking-widest text-accent-400 uppercase">From Screen Time to Life Time</p>
          <h2 className="mt-3 text-4xl leading-tight font-semibold text-white">Turn every activity into an achievement.</h2>
          <ul className="mt-8 space-y-4">
            {points.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3 text-brand-50">
                <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/10"><Icon className="h-4 w-4" /></span>
                <span className="text-[15px] leading-relaxed">{text}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-brand-200">Activity → Participation → Achievement → Certificate → Skills → Portfolio → Opportunities</p>
      </aside>
      <section className="flex flex-col px-5 py-8 sm:px-10">
        <div className="lg:hidden"><Logo /></div>
        <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-8">
          <h1 className="text-2xl font-semibold sm:text-3xl">{title}</h1>
          {subtitle && <p className="mt-2 text-sm text-slate-500">{subtitle}</p>}
          <div className="mt-8">{children}</div>
          {footer && <div className="mt-8 text-center text-sm text-slate-500">{footer}</div>}
        </div>
      </section>
    </div>
  );
}
