import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { Award, Ban, Bell, KeyRound, LogOut, Save, Shield, UserRound } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, NavLink, useParams } from "react-router-dom";
import { toast } from "sonner";
import { VerificationBadge } from "@/components/achievements/AchievementCard";
import { Avatar } from "@/components/common/Avatar";
import { Button } from "@/components/common/Button";
import { CardSkeleton, ErrorState, Spinner } from "@/components/common/Feedback";
import { Input, PasswordInput, Select, Toggle } from "@/components/common/Field";
import { LoadMore } from "@/components/common/LoadMore";
import { useConfirm } from "@/components/common/Modal";
import { PageHeader } from "@/components/common/PageHeader";
import { PasswordStrength } from "@/components/common/PasswordStrength";
import { useAuth } from "@/contexts/AuthContext";
import { qk } from "@/hooks/queryKeys";
import { achievementsApi } from "@/services/api/achievements";
import { authApi } from "@/services/api/auth";
import { errorMessage, toApiError } from "@/services/api/errors";
import { friendsApi } from "@/services/api/friends";
import { notificationsApi } from "@/services/api/notifications";
import { profilesApi } from "@/services/api/profiles";
import type { NotificationPreferences, ProfilePrivacy, Visibility } from "@/types/api";
import { cn } from "@/utils/cn";
import { formatDate } from "@/utils/format";
import { visibilityLabels } from "@/utils/labels";

const sections = [
  { key: "account", label: "Account", icon: UserRound },
  { key: "security", label: "Password & security", icon: KeyRound },
  { key: "privacy", label: "Privacy", icon: Shield },
  { key: "notifications", label: "Notifications", icon: Bell },
  { key: "blocked", label: "Blocked people", icon: Ban },
] as const;

function Panel({ title, description, children }: { title: string; description?: ReactNode; children: ReactNode }) {
  return (
    <section className="card p-5 sm:p-6">
      <h2 className="text-lg font-semibold">{title}</h2>
      {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      <div className="mt-5">{children}</div>
    </section>
  );
}

function AccountSection() {
  const { user, setUser, logout } = useAuth();
  const [form, setForm] = useState({ email: user!.email, phone_number: user!.phone_number, country: user!.country, date_of_birth: user!.date_of_birth ?? "", current_password: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const emailChanged = form.email.trim().toLowerCase() !== user!.email.toLowerCase();

  const save = async (e: FormEvent) => {
    e.preventDefault();
    const body: Record<string, string> = {};
    if (emailChanged) { body.email = form.email.trim(); body.current_password = form.current_password; }
    if (form.phone_number !== user!.phone_number) body.phone_number = form.phone_number.replace(/[\s\-().]/g, "");
    if (form.country !== user!.country) body.country = form.country.trim();
    if (form.date_of_birth && form.date_of_birth !== user!.date_of_birth) body.date_of_birth = form.date_of_birth;
    if (!Object.keys(body).length) return toast.info("Nothing to save.");
    setBusy(true);
    setErrors({});
    try {
      const r = await authApi.updateMe(body);
      setUser(r.data.user);
      setForm((f) => ({ ...f, current_password: "" }));
      toast.success(r.message);
    } catch (error) {
      const err = toApiError(error);
      setErrors(Object.fromEntries(Object.entries(err.fieldErrors).map(([k, v]) => [k, v[0]])));
      if (!Object.keys(err.fieldErrors).length) toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <Panel title="Account information" description="Your name and username are edited on your profile.">
        <div className="mb-5 flex items-center gap-3 rounded-xl bg-slate-50 p-4">
          <Avatar name={user!.full_name} />
          <div className="min-w-0 text-sm">
            <p className="font-semibold text-slate-900">{user!.full_name} <span className="font-normal text-slate-500">@{user!.username}</span></p>
            <p className="text-slate-500">Member since {formatDate(user!.created_at)} · {user!.role === "user" ? "Member" : user!.role === "admin" ? "Administrator" : "Coordinator"}</p>
          </div>
          <Link to="/profile/edit" className="ml-auto text-sm font-medium text-brand-700 hover:underline">Edit profile</Link>
        </div>
        <form onSubmit={save} className="space-y-4" noValidate>
          <Input label="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} error={errors.email} hint={user!.is_email_verified ? "Verified" : "Not verified yet"} />
          {emailChanged && <PasswordInput label="Current password" value={form.current_password} onChange={(e) => setForm({ ...form, current_password: e.target.value })} error={errors.current_password} hint="Required to change your email. We'll send a code to the new address." />}
          <div className="grid gap-4 sm:grid-cols-3">
            <Input label="Phone" type="tel" value={form.phone_number} onChange={(e) => setForm({ ...form, phone_number: e.target.value })} error={errors.phone_number} />
            <Input label="Country" value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} error={errors.country} />
            <Input label="Date of birth" type="date" value={form.date_of_birth} onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })} error={errors.date_of_birth} />
          </div>
          <div className="flex justify-end"><Button type="submit" loading={busy} icon={<Save className="h-4 w-4" />}>Save</Button></div>
        </form>
      </Panel>
      <Panel title="Log out" description="Signs you out on this device and revokes this session's refresh token.">
        <Button variant="outline" icon={<LogOut className="h-4 w-4" />} onClick={() => void logout()}>Log out</Button>
      </Panel>
    </div>
  );
}

function SecuritySection() {
  const { replaceTokens } = useAuth();
  const [form, setForm] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const local: Record<string, string> = {};
    if (!form.current_password) local.current_password = "Enter your current password.";
    if (form.new_password.length < 8) local.new_password = "Use at least 8 characters.";
    if (form.new_password !== form.confirm_password) local.confirm_password = "Passwords do not match.";
    setErrors(local);
    if (Object.keys(local).length) return;
    setBusy(true);
    try {
      const r = await authApi.changePassword(form.current_password, form.new_password, form.confirm_password);
      replaceTokens(r.data.tokens); // the old refresh tokens were revoked by the server
      setForm({ current_password: "", new_password: "", confirm_password: "" });
      toast.success(r.message);
    } catch (error) {
      const err = toApiError(error);
      setErrors(Object.fromEntries(Object.entries(err.fieldErrors).map(([k, v]) => [k, v[0]])));
      if (!Object.keys(err.fieldErrors).length) toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Panel title="Change password" description="Changing your password signs out every other device.">
      <form onSubmit={submit} className="max-w-md space-y-4" noValidate>
        <PasswordInput label="Current password" autoComplete="current-password" value={form.current_password} onChange={(e) => setForm({ ...form, current_password: e.target.value })} error={errors.current_password} />
        <div>
          <PasswordInput label="New password" autoComplete="new-password" value={form.new_password} onChange={(e) => setForm({ ...form, new_password: e.target.value })} error={errors.new_password} />
          <PasswordStrength password={form.new_password} />
        </div>
        <PasswordInput label="Confirm new password" autoComplete="new-password" value={form.confirm_password} onChange={(e) => setForm({ ...form, confirm_password: e.target.value })} error={errors.confirm_password} />
        <Button type="submit" loading={busy} icon={<KeyRound className="h-4 w-4" />}>Update password</Button>
      </form>
    </Panel>
  );
}

function PrivacySection() {
  const { profile, setProfile } = useAuth();
  const [saving, setSaving] = useState<string | null>(null);
  const update = async (patch: Partial<ProfilePrivacy>) => {
    const key = Object.keys(patch)[0];
    setSaving(key);
    try {
      const r = await profilesApi.updatePrivacy(patch);
      setProfile(r.data.profile);
      toast.success("Privacy updated.");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSaving(null);
    }
  };
  if (!profile) return <Spinner />;
  const p = profile.privacy;
  const flags: { key: keyof ProfilePrivacy; label: string }[] = [
    { key: "show_institution", label: "Show my institution" },
    { key: "show_education", label: "Show my education level and field" },
    { key: "show_location", label: "Show my location" },
    { key: "show_skills", label: "Show my skills" },
    { key: "show_interests", label: "Show my interests" },
    { key: "show_social_links", label: "Show my website and social links" },
  ];
  return (
    <div className="space-y-6">
      <Panel title="Profile visibility" description="Enforced by the server on every request.">
        <div role="radiogroup" className="grid gap-3 sm:grid-cols-3">
          {(["public", "members_only", "private"] as Visibility[]).map((v) => (
            <button key={v} role="radio" aria-checked={p.profile_visibility === v} disabled={!!saving} onClick={() => update({ profile_visibility: v })}
              className={cn("rounded-xl border p-4 text-left transition", p.profile_visibility === v ? "border-brand-500 bg-brand-50 ring-2 ring-brand-100" : "border-slate-200 hover:border-slate-300")}>
              <p className="text-sm font-semibold">{v === "public" ? "Public" : v === "members_only" ? "Members only" : "Private"}</p>
              <p className="mt-1 text-xs text-slate-500">
                {v === "public" ? "Anyone, including visitors, can view your profile." : v === "members_only" ? "Only logged-in DEAS members can view it." : "Only you. Others see a private-profile notice."}
              </p>
            </button>
          ))}
        </div>
        <div className="mt-5 divide-y divide-slate-100 border-t border-slate-100">
          {flags.map((f) => (
            <Toggle key={f.key} label={f.label} checked={p[f.key] as boolean} disabled={saving === f.key} onChange={(v) => update({ [f.key]: v })} />
          ))}
        </div>
      </Panel>
      <AchievementPrivacy />
      <Panel title="Posts" description="Each post has its own audience (Public, Members, Friends or Only me), chosen when you post and editable from the post's menu.">
        <Link to="/profile" className="text-sm font-medium text-brand-700 hover:underline">Review my posts</Link>
      </Panel>
    </div>
  );
}

function AchievementPrivacy() {
  const queryClient = useQueryClient();
  const query = useInfiniteQuery({
    queryKey: qk.achievements("privacy", {}),
    queryFn: async ({ pageParam }) => (await achievementsApi.mine({ page: pageParam })).data,
    initialPageParam: 1,
    getNextPageParam: (last) => (last.pagination.next ? last.pagination.page + 1 : undefined),
  });
  const [saving, setSaving] = useState<string | null>(null);
  const items = query.data?.pages.flatMap((p) => p.results) ?? [];
  const change = async (id: string, visibility: Visibility) => {
    setSaving(id);
    try {
      await achievementsApi.update(id, { visibility });
      toast.success("Achievement visibility updated.");
      void queryClient.invalidateQueries({ queryKey: ["achievements"] });
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSaving(null);
    }
  };
  return (
    <Panel title="Achievement visibility" description="Choose who can see each achievement once it is verified. Unverified achievements are only visible to you and reviewers.">
      {query.isPending ? <CardSkeleton lines={1} /> : query.isError ? <ErrorState error={query.error} /> : items.length === 0 ? (
        <p className="text-sm text-slate-500">You have no achievements yet. <Link to="/achievements/new" className="font-medium text-brand-700 hover:underline">Add one</Link></p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {items.map((a) => (
            <li key={a.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center">
              <Award className="hidden h-5 w-5 shrink-0 text-brand-700 sm:block" />
              <Link to={`/achievements/${a.id}`} className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-slate-800">{a.title}</span>
                <span className="mt-0.5 inline-block"><VerificationBadge status={a.verification_status} /></span>
              </Link>
              <Select aria-label={`Visibility of ${a.title}`} wrapperClassName="sm:w-48" className="h-9 py-1.5" value={a.visibility} disabled={saving === a.id}
                onChange={(e) => change(a.id, e.target.value as Visibility)} options={(["public", "members_only", "private"] as Visibility[]).map((v) => ({ value: v, label: visibilityLabels[v] }))} />
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={!!query.hasNextPage} loading={query.isFetchingNextPage} onLoad={() => void query.fetchNextPage()} />
    </Panel>
  );
}

function NotificationSection() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: qk.notificationPrefs, queryFn: async () => (await notificationsApi.preferences()).data.preferences });
  const [saving, setSaving] = useState<string | null>(null);
  const update = async (key: keyof NotificationPreferences, value: boolean) => {
    setSaving(key);
    try {
      const r = await notificationsApi.updatePreferences({ [key]: value });
      queryClient.setQueryData(qk.notificationPrefs, r.data.preferences);
      toast.success("Notification settings saved.");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSaving(null);
    }
  };
  if (query.isPending) return <CardSkeleton />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  const p = query.data;
  const rows: { key: keyof NotificationPreferences; label: string; description: string }[] = [
    { key: "friend_requests", label: "Friends", description: "Requests, acceptances and changes to your friends." },
    { key: "social_interactions", label: "Posts and comments", description: "Likes, comments, replies and shares." },
    { key: "messages", label: "Messages", description: "New messages (muted conversations never notify)." },
    { key: "announcements", label: "Announcements", description: "Friends' new announcements, updates and reminders for bookmarks." },
    { key: "achievements", label: "Achievements", description: "Verification decisions and featured achievements." },
    { key: "system_notifications", label: "System", description: "Platform announcements and maintenance." },
  ];
  return (
    <div className="space-y-6">
      <Panel title="What to notify me about" description="Security alerts (password changes, password resets) are always on.">
        <div className="divide-y divide-slate-100">
          {rows.map((r) => <Toggle key={r.key} label={r.label} description={r.description} checked={p[r.key] as boolean} disabled={saving === r.key} onChange={(v) => update(r.key, v)} />)}
        </div>
      </Panel>
      <Panel title="How to notify me">
        <div className="divide-y divide-slate-100">
          <Toggle label="Real-time updates" description="Live badge and pop-ups while DEAS is open." checked={p.realtime_notifications} disabled={saving === "realtime_notifications"} onChange={(v) => update("realtime_notifications", v)} />
          <Toggle label="Email for important events" description="Review decisions, event reminders and system notices. Security emails are always sent." checked={p.email_notifications} disabled={saving === "email_notifications"} onChange={(v) => update("email_notifications", v)} />
        </div>
      </Panel>
    </div>
  );
}

function BlockedSection() {
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const query = useInfiniteQuery({
    queryKey: ["friends", "blocked"],
    queryFn: async ({ pageParam }) => (await friendsApi.blocked(pageParam)).data,
    initialPageParam: 1,
    getNextPageParam: (last) => (last.pagination.next ? last.pagination.page + 1 : undefined),
  });
  const people = query.data?.pages.flatMap((p) => p.results) ?? [];
  return (
    <Panel title="Blocked people" description="They can't see your content, message you or send you friend requests. Unblocking does not restore a friendship.">
      {query.isPending ? <Spinner /> : people.length === 0 ? <p className="text-sm text-slate-500">You haven't blocked anyone.</p> : (
        <ul className="divide-y divide-slate-100">
          {people.map((p) => (
            <li key={p.user_id} className="flex items-center gap-3 py-3">
              <Avatar src={p.profile_picture} name={p.full_name} size="sm" />
              <span className="min-w-0 flex-1 truncate text-sm font-medium">{p.full_name}</span>
              <Button size="sm" variant="outline" onClick={async () => {
                if (!(await confirm({ title: `Unblock ${p.full_name}?`, confirmLabel: "Unblock", tone: "primary" }))) return;
                try {
                  const r = await friendsApi.unblock(p.user_id);
                  toast.success(r.message);
                  void queryClient.invalidateQueries({ queryKey: ["friends"] });
                } catch (error) {
                  toast.error(errorMessage(error));
                }
              }}>Unblock</Button>
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={!!query.hasNextPage} loading={query.isFetchingNextPage} onLoad={() => void query.fetchNextPage()} />
    </Panel>
  );
}

export default function SettingsPage() {
  const { section = "account" } = useParams();
  const active = sections.some((s) => s.key === section) ? section : "account";
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title="Settings" />
      <div className="grid gap-6 md:grid-cols-[14rem_minmax(0,1fr)]">
        <nav aria-label="Settings sections" className="scroll-thin -mx-1 flex gap-1 overflow-x-auto px-1 md:mx-0 md:flex-col md:overflow-visible md:px-0">
          {sections.map(({ key, label, icon: Icon }) => (
            <NavLink key={key} to={`/settings/${key}`} className={cn("inline-flex shrink-0 items-center gap-2.5 rounded-xl px-3.5 py-2.5 text-sm font-medium whitespace-nowrap transition", active === key ? "bg-white text-brand-800 shadow-card" : "text-slate-600 hover:bg-white/70")}>
              <Icon className="h-4 w-4" /> {label}
            </NavLink>
          ))}
        </nav>
        <div>
          {active === "account" && <AccountSection />}
          {active === "security" && <SecuritySection />}
          {active === "privacy" && <PrivacySection />}
          {active === "notifications" && <NotificationSection />}
          {active === "blocked" && <BlockedSection />}
        </div>
      </div>
    </div>
  );
}
