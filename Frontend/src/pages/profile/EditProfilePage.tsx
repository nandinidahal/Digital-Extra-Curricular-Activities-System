import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Camera, ImagePlus, Save, Trash2 } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Avatar } from "@/components/common/Avatar";
import { Button } from "@/components/common/Button";
import { PageLoader } from "@/components/common/Feedback";
import { Input, Select, TagInput, Textarea } from "@/components/common/Field";
import { PageHeader } from "@/components/common/PageHeader";
import { useAuth } from "@/contexts/AuthContext";
import { qk } from "@/hooks/queryKeys";
import { authApi } from "@/services/api/auth";
import { errorMessage, toApiError } from "@/services/api/errors";
import { profilesApi, type ProfileUpdate } from "@/services/api/profiles";
import type { EducationLevel, OwnProfile } from "@/types/api";
import { checkImage, IMAGE_ACCEPT, LIMITS } from "@/utils/files";
import { educationLabels } from "@/utils/labels";

type ProfileFields = Required<Pick<ProfileUpdate, "headline" | "bio" | "institution" | "education_level" | "field_of_study" | "location" | "website" | "linkedin_url" | "github_url" | "portfolio_url">> & { interests: string[]; skills: string[] };

const pick = (p: OwnProfile): ProfileFields => ({
  headline: p.headline, bio: p.bio, institution: p.institution, education_level: p.education_level, field_of_study: p.field_of_study,
  location: p.location, website: p.website, linkedin_url: p.linkedin_url, github_url: p.github_url, portfolio_url: p.portfolio_url,
  interests: p.interests, skills: p.skills,
});

function ImageUploader({ kind, current, onDone }: { kind: "picture" | "cover"; current: string | null; onDone: (p: OwnProfile) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const limit = kind === "picture" ? LIMITS.profilePicture : LIMITS.profileCover;
  const upload = async (file: File) => {
    const problem = checkImage(file, limit);
    if (problem) return toast.error(problem);
    setBusy(true);
    try {
      const r = kind === "picture" ? await profilesApi.uploadPicture(file) : await profilesApi.uploadCover(file);
      onDone(r.data.profile);
      toast.success(r.message);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    setBusy(true);
    try {
      const r = kind === "picture" ? await profilesApi.removePicture() : await profilesApi.removeCover();
      onDone(r.data.profile);
      toast.success(r.message);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-wrap gap-2">
      <Button size="sm" variant="outline" loading={busy} onClick={() => input.current?.click()} icon={kind === "picture" ? <Camera className="h-4 w-4" /> : <ImagePlus className="h-4 w-4" />}>
        {current ? "Change" : "Upload"} {kind === "picture" ? "photo" : "cover"}
      </Button>
      {current && <Button size="sm" variant="ghost" disabled={busy} onClick={remove} icon={<Trash2 className="h-4 w-4" />}>Remove</Button>}
      <input ref={input} type="file" accept={IMAGE_ACCEPT} className="sr-only" onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); e.target.value = ""; }} />
    </div>
  );
}

export default function EditProfilePage() {
  const { user, profile, setProfile, setUser } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [fields, setFields] = useState<ProfileFields | null>(null);
  const [account, setAccount] = useState({ full_name: user?.full_name ?? "", username: user?.username ?? "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (profile && !fields) setFields(pick(profile));
  }, [profile, fields]);

  if (!profile || !fields || !user) return <PageLoader />;

  const set = <K extends keyof ProfileFields>(key: K, value: ProfileFields[K]) => {
    setFields((f) => (f ? { ...f, [key]: value } : f));
    setErrors((e) => ({ ...e, [key]: "" }));
  };
  const updated = (p: OwnProfile) => {
    setProfile(p);
    queryClient.setQueryData(qk.profile(user.id), p);
  };

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErrors({});
    const initial = pick(profile);
    const profileChanges = Object.fromEntries(
      Object.entries(fields).filter(([k, v]) => JSON.stringify(v) !== JSON.stringify(initial[k as keyof ProfileFields])),
    ) as ProfileUpdate;
    const accountChanges = Object.fromEntries(
      Object.entries(account).map(([k, v]) => [k, v.trim()]).filter(([k, v]) => v !== user[k as "full_name" | "username"]),
    );
    try {
      if (Object.keys(accountChanges).length) {
        const r = await authApi.updateMe(accountChanges);
        setUser(r.data.user);
      }
      if (Object.keys(profileChanges).length) {
        const r = await profilesApi.update(profileChanges);
        updated(r.data.profile);
      }
      toast.success("Profile updated.");
      void queryClient.invalidateQueries({ queryKey: ["social"] });
      navigate("/profile");
    } catch (error) {
      const err = toApiError(error);
      const mapped = Object.fromEntries(Object.entries(err.fieldErrors).map(([k, v]) => [k.split(".")[0], v[0]]));
      setErrors(mapped);
      toast.error(Object.keys(mapped).length ? "Please fix the highlighted fields." : errorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/profile" className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"><ArrowLeft className="h-4 w-4" /> Back to profile</Link>
      <PageHeader title="Edit profile" description={`Profile ${profile.profile_completion.percentage}% complete. Who sees what is set in Settings → Privacy.`} />

      <section className="card mb-6 overflow-hidden">
        <div className="relative h-36 bg-gradient-to-r from-brand-800 to-brand-500 sm:h-44">
          {profile.cover_photo && <img src={profile.cover_photo} alt="Cover" className="h-full w-full object-cover" />}
          <div className="absolute right-3 bottom-3 rounded-xl bg-white/90 p-1.5 backdrop-blur">
            <ImageUploader kind="cover" current={profile.cover_photo} onDone={updated} />
          </div>
        </div>
        <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
          <Avatar src={profile.profile_picture} name={user.full_name} size="xl" className="-mt-16 sm:-mt-14" />
          <div>
            <p className="text-sm text-slate-500">Profile photo: JPEG, PNG or WebP up to 2 MB. Cover up to 5 MB.</p>
            <div className="mt-2"><ImageUploader kind="picture" current={profile.profile_picture} onDone={updated} /></div>
          </div>
        </div>
      </section>

      <form onSubmit={save} noValidate className="space-y-6">
        <section className="card space-y-5 p-5 sm:p-6">
          <h2 className="font-semibold">Basic information</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Full name" maxLength={150} value={account.full_name} onChange={(e) => setAccount((a) => ({ ...a, full_name: e.target.value }))} error={errors.full_name} />
            <Input label="Username" maxLength={30} value={account.username} onChange={(e) => setAccount((a) => ({ ...a, username: e.target.value }))} error={errors.username} hint="Letters, numbers, _ and ." />
          </div>
          <Input label="Headline" maxLength={120} value={fields.headline} onChange={(e) => set("headline", e.target.value)} error={errors.headline} placeholder="e.g. Computer science student · Robotics club lead" />
          <Textarea label="Bio" maxLength={500} rows={4} value={fields.bio} onChange={(e) => set("bio", e.target.value)} error={errors.bio} hint={`${fields.bio.length}/500`} />
          <Input label="Location" maxLength={100} value={fields.location} onChange={(e) => set("location", e.target.value)} error={errors.location} />
        </section>

        <section className="card space-y-5 p-5 sm:p-6">
          <h2 className="font-semibold">Education</h2>
          <Input label="Institution" maxLength={150} value={fields.institution} onChange={(e) => set("institution", e.target.value)} error={errors.institution} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Select label="Education level" value={fields.education_level} onChange={(e) => set("education_level", e.target.value as EducationLevel)} error={errors.education_level} options={Object.entries(educationLabels).map(([v, l]) => ({ value: v, label: l }))} />
            <Input label="Field of study" maxLength={150} value={fields.field_of_study} onChange={(e) => set("field_of_study", e.target.value)} error={errors.field_of_study} />
          </div>
        </section>

        <section className="card space-y-5 p-5 sm:p-6">
          <h2 className="font-semibold">Skills and interests</h2>
          <TagInput label="Skills" value={fields.skills} onChange={(v) => set("skills", v)} max={30} error={errors.skills} />
          <TagInput label="Interests" value={fields.interests} onChange={(v) => set("interests", v)} max={20} error={errors.interests} />
        </section>

        <section className="card space-y-5 p-5 sm:p-6">
          <h2 className="font-semibold">Links</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Website" type="url" value={fields.website} onChange={(e) => set("website", e.target.value)} error={errors.website} placeholder="https://" />
            <Input label="Portfolio" type="url" value={fields.portfolio_url} onChange={(e) => set("portfolio_url", e.target.value)} error={errors.portfolio_url} placeholder="https://" />
            <Input label="LinkedIn" type="url" value={fields.linkedin_url} onChange={(e) => set("linkedin_url", e.target.value)} error={errors.linkedin_url} placeholder="https://linkedin.com/in/…" />
            <Input label="GitHub" type="url" value={fields.github_url} onChange={(e) => set("github_url", e.target.value)} error={errors.github_url} placeholder="https://github.com/…" />
          </div>
        </section>

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => navigate("/profile")}>Cancel</Button>
          <Button type="submit" loading={busy} icon={<Save className="h-4 w-4" />}>Save profile</Button>
        </div>
      </form>
    </div>
  );
}
