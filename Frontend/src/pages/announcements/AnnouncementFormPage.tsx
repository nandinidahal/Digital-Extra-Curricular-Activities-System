import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Globe2, ImagePlus, MapPin, MonitorPlay, Save, Send, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/common/Button";
import { ErrorState, PageLoader } from "@/components/common/Feedback";
import { Input, Select, Textarea, Toggle } from "@/components/common/Field";
import { PageHeader } from "@/components/common/PageHeader";
import { qk } from "@/hooks/queryKeys";
import { announcementsApi, type AnnouncementInput } from "@/services/api/announcements";
import { errorMessage, toApiError } from "@/services/api/errors";
import type { ActivityType, AnnouncementDetail, Visibility } from "@/types/api";
import { cn } from "@/utils/cn";
import { checkImage, IMAGE_ACCEPT, LIMITS } from "@/utils/files";
import { fromLocalInput, toLocalInput } from "@/utils/format";

interface FormState {
  title: string;
  short_description: string;
  description: string;
  category: string;
  activity_type: ActivityType;
  location: string;
  online_link: string;
  start: string;
  end: string;
  deadline: string;
  registration_link: string;
  organizer_name: string;
  organizer_email: string;
  organizer_phone: string;
  contact_information: string;
  show_contact_details: boolean;
  eligibility_criteria: string;
  requirements: string;
  visibility: Visibility;
}

const empty: FormState = {
  title: "", short_description: "", description: "", category: "", activity_type: "physical", location: "", online_link: "",
  start: "", end: "", deadline: "", registration_link: "", organizer_name: "", organizer_email: "", organizer_phone: "",
  contact_information: "", show_contact_details: false, eligibility_criteria: "", requirements: "", visibility: "public",
};

function fromAnnouncement(a: AnnouncementDetail): FormState {
  return {
    title: a.title, short_description: a.short_description, description: a.description, category: a.category?.id ?? "",
    activity_type: a.activity_type, location: a.location, online_link: a.online_link ?? "",
    start: toLocalInput(a.start_datetime), end: toLocalInput(a.end_datetime), deadline: toLocalInput(a.registration_deadline),
    registration_link: a.registration_link, organizer_name: a.organizer_name, organizer_email: a.organizer_email ?? "",
    organizer_phone: a.organizer_phone ?? "", contact_information: a.contact_information ?? "",
    show_contact_details: !!a.show_contact_details, eligibility_criteria: a.eligibility_criteria, requirements: a.requirements,
    visibility: a.visibility,
  };
}

const URL_RE = /^https?:\/\/[^\s]+\.[^\s]+/i;

/** Client checks mirroring announcements/services.validate_consistency + validate_for_publication. */
function validate(f: FormState, publishing: boolean): Record<string, string> {
  const e: Record<string, string> = {};
  if (!f.title.trim()) e.title = "A title is required.";
  if (f.online_link && !URL_RE.test(f.online_link)) e.online_link = "Use a link starting with http:// or https://.";
  if (f.registration_link && !URL_RE.test(f.registration_link)) e.registration_link = "Use a link starting with http:// or https://.";
  if (f.organizer_email && !/^\S+@\S+\.\S+$/.test(f.organizer_email)) e.organizer_email = "Enter a valid email address.";
  if (f.end && !f.start) e.start = "Set a start when an end is given.";
  if (f.start && f.end && new Date(f.end) < new Date(f.start)) e.end = "The end cannot be before the start.";
  if (f.start && f.deadline && new Date(f.deadline) > new Date(f.start)) e.deadline = "Registration must close on or before the start.";
  if (publishing) {
    if (!f.short_description.trim()) e.short_description = "Required to publish.";
    if (!f.description.trim()) e.description = "Required to publish.";
    if (!f.category) e.category = "Choose a category to publish.";
    if (!f.start) e.start = "Required to publish.";
    if (f.activity_type !== "online" && !f.location.trim()) e.location = "Physical and hybrid activities need a location.";
    if (f.activity_type !== "physical" && !f.online_link) e.online_link = "Online and hybrid activities need a link.";
  }
  return e;
}

const FIELD_MAP: Record<string, keyof FormState> = { start_datetime: "start", end_datetime: "end", registration_deadline: "deadline" };

export default function AnnouncementFormPage() {
  const { id } = useParams();
  const editing = !!id;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(empty);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [cover, setCover] = useState<File | null>(null);
  const [removeCover, setRemoveCover] = useState(false);
  const [busy, setBusy] = useState<"draft" | "publish" | "save" | null>(null);

  const categories = useQuery({ queryKey: qk.categories, queryFn: async () => (await announcementsApi.categories()).data.results, staleTime: 600_000 });
  const existing = useQuery({ queryKey: qk.announcement(id ?? ""), queryFn: async () => (await announcementsApi.get(id!)).data.announcement, enabled: editing });

  useEffect(() => {
    if (existing.data) setForm(fromAnnouncement(existing.data));
  }, [existing.data]);

  const coverPreview = useMemo(() => (cover ? URL.createObjectURL(cover) : null), [cover]);
  useEffect(() => () => { if (coverPreview) URL.revokeObjectURL(coverPreview); }, [coverPreview]);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => ({ ...e, [key]: "" }));
  };

  if (editing && existing.isPending) return <PageLoader />;
  if (editing && existing.isError) return <ErrorState error={existing.error} title="Cannot edit this announcement" />;
  if (editing && existing.data && !existing.data.is_owner) return <ErrorState title="Only the author can edit this announcement" />;

  const isPublished = existing.data?.status === "published";

  const submit = async (mode: "draft" | "publish" | "save") => {
    const publishing = mode === "publish" || (mode === "save" && isPublished);
    const local = validate(form, publishing);
    setErrors(local);
    if (Object.values(local).some(Boolean)) {
      toast.error("Please fix the highlighted fields.");
      return;
    }
    const input: AnnouncementInput = {
      title: form.title.trim(),
      short_description: form.short_description.trim(),
      description: form.description.trim(),
      category: form.category || null,
      activity_type: form.activity_type,
      location: form.location.trim(),
      online_link: form.online_link.trim(),
      start_datetime: fromLocalInput(form.start),
      end_datetime: fromLocalInput(form.end),
      registration_deadline: fromLocalInput(form.deadline),
      registration_link: form.registration_link.trim(),
      organizer_name: form.organizer_name.trim(),
      organizer_email: form.organizer_email.trim(),
      organizer_phone: form.organizer_phone.trim(),
      contact_information: form.contact_information.trim(),
      show_contact_details: form.show_contact_details,
      eligibility_criteria: form.eligibility_criteria.trim(),
      requirements: form.requirements.trim(),
      visibility: form.visibility,
      ...(cover ? { cover_image: cover } : {}),
      ...(editing && removeCover && !cover ? { remove_cover_image: true } : {}),
    };
    if (!editing) input.status = mode === "publish" ? "published" : "draft";
    if (editing && existing.data) {
      // PATCH only what changed, so untouched dates are not re-sent (a re-sent date would count
      // as an edit and notify everyone who bookmarked the announcement).
      const initial = fromAnnouncement(existing.data);
      for (const key of Object.keys(input) as (keyof AnnouncementInput)[]) {
        const formKey = (FIELD_MAP[key] ?? key) as keyof FormState;
        if (formKey in initial && initial[formKey] === form[formKey]) delete input[key];
      }
    }
    setBusy(mode);
    try {
      const result = editing ? await announcementsApi.update(id!, input) : await announcementsApi.create(input);
      let announcement = result.data.announcement;
      if (editing && mode === "publish") announcement = (await announcementsApi.publish(id!)).data.announcement;
      queryClient.setQueryData(qk.announcement(announcement.id), announcement);
      void queryClient.invalidateQueries({ queryKey: ["announcements", "list"] });
      toast.success(mode === "publish" ? "Announcement published." : editing ? "Changes saved." : "Draft saved.");
      navigate(`/announcements/${announcement.id}`, { replace: true });
    } catch (error) {
      const e = toApiError(error);
      const mapped: Record<string, string> = {};
      for (const [field, messages] of Object.entries(e.fieldErrors)) mapped[FIELD_MAP[field] ?? field] = messages[0];
      setErrors(mapped);
      toast.error(Object.keys(mapped).length ? "Please fix the highlighted fields." : errorMessage(error));
    } finally {
      setBusy(null);
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void submit(editing ? "save" : "publish");
  };

  const currentCover = coverPreview ?? (!removeCover ? existing.data?.cover_image : null);
  const activityOptions: { value: ActivityType; label: string; icon: typeof MapPin }[] = [
    { value: "physical", label: "In person", icon: MapPin },
    { value: "online", label: "Online", icon: MonitorPlay },
    { value: "hybrid", label: "Hybrid", icon: Globe2 },
  ];

  return (
    <div className="mx-auto max-w-3xl">
      <Link to={editing ? `/announcements/${id}` : "/announcements"} className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"><ArrowLeft className="h-4 w-4" /> Back</Link>
      <PageHeader title={editing ? "Edit announcement" : "Create announcement"} description={editing ? undefined : "Save a draft any time. Publishing checks that all key details are filled in."} />
      <form onSubmit={onSubmit} noValidate className="space-y-6">
        <section className="card space-y-5 p-5 sm:p-6">
          <h2 className="font-semibold">Basics</h2>
          <Input label="Title" required maxLength={200} value={form.title} onChange={(e) => set("title", e.target.value)} error={errors.title} placeholder="e.g. Inter-college Robotics Challenge 2026" />
          <Input label="Short description" maxLength={300} value={form.short_description} onChange={(e) => set("short_description", e.target.value)} error={errors.short_description} hint="One line shown on cards." />
          <Textarea label="Full description" rows={7} maxLength={10000} value={form.description} onChange={(e) => set("description", e.target.value)} error={errors.description} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Select label="Category" value={form.category} onChange={(e) => set("category", e.target.value)} error={errors.category} placeholder="Choose a category"
              options={(categories.data ?? []).map((c) => ({ value: c.id, label: c.name })).concat(existing.data?.category && !categories.data?.some((c) => c.id === existing.data!.category!.id) ? [{ value: existing.data.category.id, label: `${existing.data.category.name} (inactive)` }] : [])} />
            <Select label="Who can see it" value={form.visibility} onChange={(e) => set("visibility", e.target.value as Visibility)} options={[{ value: "public", label: "Public (anyone, even logged out)" }, { value: "members_only", label: "Members only (logged-in users)" }, { value: "private", label: "Only me" }]} />
          </div>
        </section>

        <section className="card space-y-5 p-5 sm:p-6">
          <h2 className="font-semibold">When and where</h2>
          <div role="radiogroup" aria-label="Activity type" className="grid grid-cols-3 gap-2">
            {activityOptions.map(({ value, label, icon: Icon }) => (
              <button key={value} type="button" role="radio" aria-checked={form.activity_type === value} onClick={() => set("activity_type", value)}
                className={cn("flex flex-col items-center gap-1.5 rounded-xl border px-3 py-3 text-sm font-medium transition", form.activity_type === value ? "border-brand-500 bg-brand-50 text-brand-800 ring-2 ring-brand-100" : "border-slate-200 text-slate-600 hover:border-slate-300")}>
                <Icon className="h-5 w-5" /> {label}
              </button>
            ))}
          </div>
          {form.activity_type !== "online" && <Input label="Location" maxLength={255} value={form.location} onChange={(e) => set("location", e.target.value)} error={errors.location} placeholder="Venue, city" />}
          {form.activity_type !== "physical" && <Input label="Online meeting / event link" type="url" maxLength={500} value={form.online_link} onChange={(e) => set("online_link", e.target.value)} error={errors.online_link} placeholder="https://" hint="Only logged-in members can see this link." />}
          <div className="grid gap-4 sm:grid-cols-3">
            <Input label="Starts" type="datetime-local" value={form.start} onChange={(e) => set("start", e.target.value)} error={errors.start} />
            <Input label="Ends" type="datetime-local" value={form.end} onChange={(e) => set("end", e.target.value)} error={errors.end} />
            <Input label="Registration deadline" type="datetime-local" value={form.deadline} onChange={(e) => set("deadline", e.target.value)} error={errors.deadline} />
          </div>
          <Input label="Registration link" type="url" maxLength={500} value={form.registration_link} onChange={(e) => set("registration_link", e.target.value)} error={errors.registration_link} placeholder="https://" />
        </section>

        <section className="card space-y-5 p-5 sm:p-6">
          <h2 className="font-semibold">Details</h2>
          <Textarea label="Eligibility" rows={3} maxLength={3000} value={form.eligibility_criteria} onChange={(e) => set("eligibility_criteria", e.target.value)} error={errors.eligibility_criteria} placeholder="Who can take part?" />
          <Textarea label="Requirements" rows={3} maxLength={3000} value={form.requirements} onChange={(e) => set("requirements", e.target.value)} error={errors.requirements} placeholder="What should participants bring or prepare?" />
        </section>

        <section className="card space-y-5 p-5 sm:p-6">
          <h2 className="font-semibold">Organizer</h2>
          <div className="grid gap-4 sm:grid-cols-3">
            <Input label="Name" maxLength={150} value={form.organizer_name} onChange={(e) => set("organizer_name", e.target.value)} error={errors.organizer_name} />
            <Input label="Email" type="email" value={form.organizer_email} onChange={(e) => set("organizer_email", e.target.value)} error={errors.organizer_email} />
            <Input label="Phone" type="tel" maxLength={20} value={form.organizer_phone} onChange={(e) => set("organizer_phone", e.target.value)} error={errors.organizer_phone} />
          </div>
          <Textarea label="Other contact information" rows={2} maxLength={1000} value={form.contact_information} onChange={(e) => set("contact_information", e.target.value)} error={errors.contact_information} />
          <Toggle checked={form.show_contact_details} onChange={(v) => set("show_contact_details", v)} label="Show contact details to logged-in members" description="Visitors never see email, phone or contact text. When off, only you and moderators see them." />
        </section>

        <section className="card space-y-4 p-5 sm:p-6">
          <h2 className="font-semibold">Cover image</h2>
          {currentCover ? (
            <div className="relative overflow-hidden rounded-xl">
              <img src={currentCover} alt="Cover preview" className="h-52 w-full object-cover" />
              <button type="button" onClick={() => { setCover(null); setRemoveCover(true); }} className="absolute top-2 right-2 inline-flex items-center gap-1.5 rounded-full bg-slate-900/70 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-900"><Trash2 className="h-3.5 w-3.5" /> Remove</button>
            </div>
          ) : (
            <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-brand-300 px-4 py-10 text-sm font-medium text-brand-700 hover:bg-brand-50">
              <ImagePlus className="h-6 w-6" /> Upload a cover (JPEG, PNG or WebP, max 5 MB)
              <input type="file" accept={IMAGE_ACCEPT} className="sr-only" onChange={(e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                const problem = checkImage(file, LIMITS.announcementCover);
                if (problem) toast.error(problem);
                else { setCover(file); setRemoveCover(false); }
                e.target.value = "";
              }} />
            </label>
          )}
          {errors.cover_image && <p className="text-xs font-medium text-rose-600">{errors.cover_image}</p>}
        </section>

        <div className="sticky bottom-20 z-10 flex flex-wrap justify-end gap-2 rounded-2xl border border-slate-200 bg-white/95 p-3 shadow-pop backdrop-blur lg:bottom-4">
          {editing ? (
            <>
              <Button type="button" variant="outline" onClick={() => navigate(-1)}>Cancel</Button>
              {existing.data?.status === "draft" && <Button type="button" variant="outline" loading={busy === "publish"} disabled={!!busy} icon={<Send className="h-4 w-4" />} onClick={() => submit("publish")}>Save and publish</Button>}
              <Button type="submit" loading={busy === "save"} disabled={!!busy} icon={<Save className="h-4 w-4" />}>Save changes</Button>
            </>
          ) : (
            <>
              <Button type="button" variant="outline" loading={busy === "draft"} disabled={!!busy} icon={<Save className="h-4 w-4" />} onClick={() => submit("draft")}>Save draft</Button>
              <Button type="submit" loading={busy === "publish"} disabled={!!busy} icon={<Send className="h-4 w-4" />}>Publish</Button>
            </>
          )}
        </div>
      </form>
    </div>
  );
}
