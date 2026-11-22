import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Globe2, Lock, Save, Upload, Users } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/common/Button";
import { ErrorState, PageLoader } from "@/components/common/Feedback";
import { FilePicker } from "@/components/common/FilePicker";
import { Input, Select, TagInput, Textarea } from "@/components/common/Field";
import { PageHeader } from "@/components/common/PageHeader";
import { qk } from "@/hooks/queryKeys";
import { achievementsApi, type AchievementInput } from "@/services/api/achievements";
import { errorMessage, toApiError } from "@/services/api/errors";
import type { Achievement, AchievementLevel, AchievementType, Visibility } from "@/types/api";
import { cn } from "@/utils/cn";
import { checkImageOrPdf, EVIDENCE_ACCEPT, LIMITS } from "@/utils/files";
import { achievementTypeLabels, levelLabels } from "@/utils/labels";

interface FormState {
  title: string;
  description: string;
  category: string;
  achievement_type: AchievementType;
  organization: string;
  event_name: string;
  achievement_date: string;
  location: string;
  level: AchievementLevel;
  position: string;
  skills: string[];
  visibility: Visibility;
}

const empty: FormState = {
  title: "", description: "", category: "", achievement_type: "certificate", organization: "", event_name: "",
  achievement_date: "", location: "", level: "institutional", position: "", skills: [], visibility: "public",
};

const fromAchievement = (a: Achievement): FormState => ({
  title: a.title, description: a.description, category: a.category?.id ?? "", achievement_type: a.achievement_type,
  organization: a.organization, event_name: a.event_name, achievement_date: a.achievement_date, location: a.location,
  level: a.level, position: a.position, skills: a.skills, visibility: a.visibility,
});

const MATERIAL: (keyof FormState)[] = ["title", "description", "category", "achievement_type", "organization", "event_name", "achievement_date", "location", "level", "position"];

const visibilityOptions: { value: Visibility; label: string; text: string; icon: typeof Globe2 }[] = [
  { value: "public", label: "Public", text: "Anyone can see it on your profile once verified.", icon: Globe2 },
  { value: "members_only", label: "Members only", text: "Only logged-in DEAS members can see it.", icon: Users },
  { value: "private", label: "Private", text: "Only you (and reviewers who verify it).", icon: Lock },
];

export default function AchievementFormPage() {
  const { id } = useParams();
  const editing = !!id;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(empty);
  const [files, setFiles] = useState<File[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const categories = useQuery({ queryKey: qk.achievementCategories, queryFn: async () => (await achievementsApi.categories()).data.results, staleTime: 600_000 });
  const existing = useQuery({ queryKey: qk.achievement(id ?? ""), queryFn: async () => (await achievementsApi.get(id!)).data.achievement, enabled: editing });
  useEffect(() => {
    if (existing.data) setForm(fromAchievement(existing.data));
  }, [existing.data]);

  if (editing && existing.isPending) return <PageLoader />;
  if (editing && existing.isError) return <ErrorState error={existing.error} title="Cannot edit this achievement" />;
  if (editing && existing.data && !existing.data.is_owner) return <ErrorState title="Only the owner can edit this achievement" />;

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => ({ ...e, [key]: "" }));
  };

  const today = new Date().toISOString().slice(0, 10);
  const materialChange = editing && existing.data?.verification_status === "verified" &&
    MATERIAL.some((k) => JSON.stringify(form[k]) !== JSON.stringify(fromAchievement(existing.data!)[k]));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const local: Record<string, string> = {};
    if (!form.title.trim()) local.title = "A title is required.";
    if (!form.achievement_date) local.achievement_date = "Enter the date of the achievement.";
    else if (form.achievement_date > today) local.achievement_date = "The date cannot be in the future.";
    setErrors(local);
    if (Object.keys(local).length) return;

    const input: AchievementInput = {
      title: form.title.trim(), description: form.description.trim(), category: form.category || null,
      achievement_type: form.achievement_type, organization: form.organization.trim(), event_name: form.event_name.trim(),
      achievement_date: form.achievement_date, location: form.location.trim(), level: form.level, position: form.position.trim(),
      skills: form.skills, visibility: form.visibility,
    };
    if (editing && existing.data) {
      const initial = fromAchievement(existing.data);
      for (const key of Object.keys(input) as (keyof AchievementInput)[]) {
        if (key in initial && JSON.stringify(initial[key as keyof FormState]) === JSON.stringify(form[key as keyof FormState])) delete input[key];
      }
    }
    setBusy(true);
    try {
      const result = editing ? await achievementsApi.update(id!, input) : await achievementsApi.create(input);
      const saved = result.data.achievement;
      if (!editing && files.length) {
        try {
          await achievementsApi.uploadEvidence(saved.id, files);
        } catch (error) {
          toast.error(`Achievement saved, but the files could not be uploaded: ${errorMessage(error)}`);
        }
      }
      toast.success(result.message);
      void queryClient.invalidateQueries({ queryKey: ["achievements"] });
      navigate(`/achievements/${saved.id}`, { replace: true });
    } catch (error) {
      const err = toApiError(error);
      setErrors(Object.fromEntries(Object.entries(err.fieldErrors).map(([k, v]) => [k.split(".")[0], v[0]])));
      toast.error(Object.keys(err.fieldErrors).length ? "Please fix the highlighted fields." : errorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <Link to={editing ? `/achievements/${id}` : "/achievements"} className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"><ArrowLeft className="h-4 w-4" /> Back</Link>
      <PageHeader title={editing ? "Edit achievement" : "Add an achievement"} description={editing ? undefined : "New achievements are reviewed by a coordinator before they show as verified."} />
      <form onSubmit={submit} noValidate className="space-y-6">
        <section className="card space-y-5 p-5 sm:p-6">
          <Input label="Title" required maxLength={200} value={form.title} onChange={(e) => set("title", e.target.value)} error={errors.title} placeholder="e.g. National Science Olympiad – Gold medal" />
          <Textarea label="Description" rows={5} maxLength={5000} value={form.description} onChange={(e) => set("description", e.target.value)} error={errors.description} placeholder="What did you do, and what did you learn?" />
          <div className="grid gap-4 sm:grid-cols-3">
            <Select label="Type" value={form.achievement_type} onChange={(e) => set("achievement_type", e.target.value as AchievementType)} options={Object.entries(achievementTypeLabels).map(([v, l]) => ({ value: v, label: l }))} />
            <Select label="Level" value={form.level} onChange={(e) => set("level", e.target.value as AchievementLevel)} options={Object.entries(levelLabels).map(([v, l]) => ({ value: v, label: l }))} />
            <Select label="Category" value={form.category} onChange={(e) => set("category", e.target.value)} error={errors.category} placeholder="Choose" options={(categories.data ?? []).map((c) => ({ value: c.id, label: c.name }))} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Organization" maxLength={200} value={form.organization} onChange={(e) => set("organization", e.target.value)} error={errors.organization} placeholder="Who awarded it?" />
            <Input label="Event" maxLength={200} value={form.event_name} onChange={(e) => set("event_name", e.target.value)} error={errors.event_name} />
            <Input label="Date" required type="date" max={today} value={form.achievement_date} onChange={(e) => set("achievement_date", e.target.value)} error={errors.achievement_date} />
            <Input label="Position or rank" maxLength={100} value={form.position} onChange={(e) => set("position", e.target.value)} error={errors.position} placeholder="e.g. 1st place, Finalist" />
          </div>
          <Input label="Location" maxLength={255} value={form.location} onChange={(e) => set("location", e.target.value)} error={errors.location} />
          <TagInput label="Skills" value={form.skills} onChange={(v) => set("skills", v)} max={20} error={errors.skills} placeholder="e.g. Teamwork, Python — press Enter" />
        </section>

        <section className="card p-5 sm:p-6">
          <h2 className="mb-1 font-semibold">Who can see it</h2>
          <p className="mb-4 text-sm text-slate-500">Enforced by the server. Unverified achievements are never shown to others.</p>
          <div role="radiogroup" className="grid gap-3 sm:grid-cols-3">
            {visibilityOptions.map(({ value, label, text, icon: Icon }) => (
              <button key={value} type="button" role="radio" aria-checked={form.visibility === value} onClick={() => set("visibility", value)}
                className={cn("rounded-xl border p-4 text-left transition", form.visibility === value ? "border-brand-500 bg-brand-50 ring-2 ring-brand-100" : "border-slate-200 hover:border-slate-300")}>
                <Icon className={cn("h-5 w-5", form.visibility === value ? "text-brand-700" : "text-slate-400")} />
                <p className="mt-2 text-sm font-semibold text-slate-900">{label}</p>
                <p className="mt-0.5 text-xs text-slate-500">{text}</p>
              </button>
            ))}
          </div>
        </section>

        {!editing && (
          <section className="card p-5 sm:p-6">
            <h2 className="mb-1 font-semibold">Certificate or evidence</h2>
            <p className="mb-4 text-sm text-slate-500">Optional now, but it helps the reviewer. Files stay private to you and reviewers.</p>
            <FilePicker files={files} onChange={setFiles} accept={EVIDENCE_ACCEPT} max={LIMITS.evidenceFiles} validate={(f) => checkImageOrPdf(f, LIMITS.evidenceImage, LIMITS.evidencePdf)} label="Add files (JPEG, PNG, WebP ≤5 MB · PDF ≤10 MB)" icon={<Upload className="h-4 w-4" />} />
          </section>
        )}

        {materialChange && <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">Changing these details sends this verified achievement back for re-verification (and removes it from featured).</p>}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => navigate(-1)}>Cancel</Button>
          <Button type="submit" loading={busy} icon={<Save className="h-4 w-4" />}>{editing ? "Save changes" : "Submit for verification"}</Button>
        </div>
      </form>
    </div>
  );
}
