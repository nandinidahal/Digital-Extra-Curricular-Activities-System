import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle, ArrowLeft, Award, BadgeCheck, Building2, CalendarDays, Download, FileText, History, Lock, MapPin,
  Megaphone, Pencil, Repeat2, Send, ShieldCheck, Star, StarOff, Trash2, Upload, X, XCircle,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { VerificationBadge, VisibilityBadge } from "@/components/achievements/AchievementCard";
import { Avatar } from "@/components/common/Avatar";
import { Button } from "@/components/common/Button";
import { Badge, ErrorState, PageLoader } from "@/components/common/Feedback";
import { FilePicker } from "@/components/common/FilePicker";
import { Select, Textarea } from "@/components/common/Field";
import { Modal, useConfirm } from "@/components/common/Modal";
import { useAuth } from "@/contexts/AuthContext";
import { qk } from "@/hooks/queryKeys";
import { achievementsApi } from "@/services/api/achievements";
import { errorMessage, toApiError } from "@/services/api/errors";
import { socialApi } from "@/services/api/social";
import type { Achievement, Evidence, Visibility } from "@/types/api";
import { checkImageOrPdf, EVIDENCE_ACCEPT, LIMITS } from "@/utils/files";
import { formatBytes, formatDate, formatDateTime } from "@/utils/format";
import { achievementTypeLabels, levelLabels, verificationLabels, visibilityLabels } from "@/utils/labels";

function Detail({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 text-slate-400">{icon}</span>
      <div><p className="text-xs text-slate-500">{label}</p><p className="text-sm font-medium text-slate-800">{children}</p></div>
    </div>
  );
}

function EvidenceGallery({ achievement, canManage, onChanged }: { achievement: Achievement; canManage: boolean; onChanged: () => void }) {
  const confirm = useConfirm();
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<Evidence | null>(null);
  const evidence = achievement.evidence ?? [];
  const remaining = LIMITS.evidenceFiles - evidence.length;

  const upload = async () => {
    if (!files.length) return;
    if (achievement.verification_status === "verified" && !(await confirm({ title: "Send for re-verification?", description: "Adding evidence to a verified achievement sends it back to a reviewer and removes it from featured.", confirmLabel: "Upload", tone: "primary" }))) return;
    setUploading(true);
    try {
      await achievementsApi.uploadEvidence(achievement.id, files);
      toast.success(`${files.length} file${files.length === 1 ? "" : "s"} uploaded.`);
      setFiles([]);
      onChanged();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setUploading(false);
    }
  };

  const remove = async (item: Evidence) => {
    if (!(await confirm({ title: "Remove this file?", description: achievement.verification_status === "verified" ? "The achievement will be sent back for verification." : "The file will be deleted.", confirmLabel: "Remove" }))) return;
    try {
      await achievementsApi.deleteEvidence(item.id);
      toast.success("Evidence removed.");
      onChanged();
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  return (
    <section className="card p-5 sm:p-6">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold">Certificates and evidence</h2>
          <p className="mt-0.5 flex items-center gap-1 text-xs text-slate-500"><Lock className="h-3 w-3" /> Private: only you and reviewers can open these files.</p>
        </div>
        <span className="text-xs text-slate-500">{evidence.length}/{LIMITS.evidenceFiles}</span>
      </div>
      {evidence.length === 0 ? (
        <p className="rounded-xl bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">No files yet.{canManage ? " Upload a certificate or photo to help the reviewer." : ""}</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {evidence.map((item) => (
            <div key={item.id} className="group relative overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
              {item.kind === "image" && item.download_url ? (
                <button onClick={() => setPreview(item)} className="block aspect-[4/3] w-full" aria-label={`Open ${item.original_name}`}>
                  <img src={item.download_url} alt={item.original_name} className="h-full w-full object-cover" loading="lazy" />
                </button>
              ) : (
                <a href={item.download_url ?? "#"} target="_blank" rel="noopener noreferrer" className="flex aspect-[4/3] flex-col items-center justify-center gap-2 p-3 text-center hover:bg-slate-100">
                  <FileText className="h-8 w-8 text-rose-500" />
                  <span className="line-clamp-2 text-xs font-medium text-slate-700">{item.original_name}</span>
                </a>
              )}
              <div className="flex items-center justify-between gap-2 border-t border-slate-200 bg-white px-2.5 py-1.5 text-[11px] text-slate-500">
                <span className="truncate">{formatBytes(item.size)}</span>
                <span className="flex gap-1">
                  {item.download_url && <a href={item.download_url} className="rounded p-1 hover:bg-slate-100 hover:text-slate-800" aria-label="Download"><Download className="h-3.5 w-3.5" /></a>}
                  {canManage && <button onClick={() => remove(item)} className="rounded p-1 hover:bg-rose-50 hover:text-rose-600" aria-label="Remove file"><Trash2 className="h-3.5 w-3.5" /></button>}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
      {canManage && remaining > 0 && (
        <div className="mt-4 space-y-3">
          <FilePicker files={files} onChange={setFiles} accept={EVIDENCE_ACCEPT} max={remaining} validate={(f) => checkImageOrPdf(f, LIMITS.evidenceImage, LIMITS.evidencePdf)} label="Add certificate or photo (JPEG, PNG, WebP ≤5 MB · PDF ≤10 MB)" icon={<Upload className="h-4 w-4" />} />
          {files.length > 0 && <Button loading={uploading} onClick={upload} icon={<Upload className="h-4 w-4" />}>Upload {files.length} file{files.length === 1 ? "" : "s"}</Button>}
        </div>
      )}
      {preview && preview.download_url && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/90 p-4" role="dialog" aria-modal="true" onClick={() => setPreview(null)}>
          <button className="absolute top-4 right-4 rounded-full bg-white/10 p-2 text-white" aria-label="Close"><X className="h-6 w-6" /></button>
          <img src={preview.download_url} alt={preview.original_name} className="max-h-full max-w-full rounded-lg" />
        </div>
      )}
    </section>
  );
}

function HistoryTimeline({ id }: { id: string }) {
  const query = useQuery({ queryKey: ["achievements", "history", id], queryFn: async () => (await achievementsApi.history(id)).data.history });
  const labels: Record<string, string> = {
    submitted: "Submitted for verification", resubmitted: "Resubmitted with more information", verified: "Verified",
    rejected: "Rejected", more_information_required: "More information requested", reverification_required: "Sent back for re-verification after changes",
  };
  if (!query.data?.length) return null;
  return (
    <section className="card p-5 sm:p-6">
      <h2 className="mb-4 flex items-center gap-2 font-semibold"><History className="h-4 w-4" /> Verification history</h2>
      <ol className="relative space-y-5 border-l border-slate-200 pl-5">
        {query.data.map((h) => (
          <li key={h.id} className="relative">
            <span className="absolute top-1 -left-[25px] h-2.5 w-2.5 rounded-full bg-brand-600 ring-4 ring-white" />
            <p className="text-sm font-medium text-slate-900">{labels[h.decision] ?? h.decision}</p>
            <p className="text-xs text-slate-500">{formatDateTime(h.created_at)} · {h.actor_role === "system" ? "System" : h.reviewer?.full_name ?? h.reviewer?.username ?? "Unknown"}</p>
            {h.comments && <p className="prose-plain mt-1.5 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">{h.comments}</p>}
          </li>
        ))}
      </ol>
    </section>
  );
}

function ReviewPanel({ achievement, onDone }: { achievement: Achievement; onDone: () => void }) {
  const [comments, setComments] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const act = async (decision: "verify" | "reject" | "request") => {
    if (decision !== "verify" && !comments.trim()) {
      toast.error("Please explain the decision to the user.");
      return;
    }
    setBusy(decision);
    try {
      if (decision === "verify") await achievementsApi.verify(achievement.id, comments.trim());
      else if (decision === "reject") await achievementsApi.reject(achievement.id, comments.trim());
      else await achievementsApi.requestInformation(achievement.id, comments.trim());
      toast.success(decision === "verify" ? "Achievement verified." : decision === "reject" ? "Achievement rejected." : "More information requested.");
      setComments("");
      onDone();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(null);
    }
  };
  return (
    <section className="card border-brand-200 bg-brand-50/40 p-5 sm:p-6">
      <h2 className="flex items-center gap-2 font-semibold"><ShieldCheck className="h-4 w-4 text-brand-700" /> Review this submission</h2>
      <p className="mt-1 text-sm text-slate-600">Check the evidence, then record your decision. The owner is notified by the app and by email.</p>
      <Textarea wrapperClassName="mt-4" label="Comments for the owner" hint="Required when rejecting or requesting more information." rows={3} maxLength={2000} value={comments} onChange={(e) => setComments(e.target.value)} />
      <div className="mt-4 flex flex-wrap gap-2">
        <Button loading={busy === "verify"} disabled={!!busy} onClick={() => act("verify")} icon={<BadgeCheck className="h-4 w-4" />}>Verify</Button>
        <Button variant="outline" loading={busy === "request"} disabled={!!busy} onClick={() => act("request")} icon={<AlertCircle className="h-4 w-4" />}>Request info</Button>
        <Button variant="danger" loading={busy === "reject"} disabled={!!busy} onClick={() => act("reject")} icon={<XCircle className="h-4 w-4" />}>Reject</Button>
      </div>
    </section>
  );
}

export default function AchievementDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { user, isModerator, isAdmin } = useAuth();
  const [busy, setBusy] = useState<string | null>(null);
  const [resubmitOpen, setResubmitOpen] = useState(false);
  const [note, setNote] = useState("");
  const [shareOpen, setShareOpen] = useState(false);
  const [caption, setCaption] = useState("");

  const query = useQuery({ queryKey: qk.achievement(id), queryFn: async () => (await achievementsApi.get(id)).data.achievement });
  const refresh = () => {
    void query.refetch();
    void queryClient.invalidateQueries({ queryKey: ["achievements"] });
  };

  if (query.isPending) return <PageLoader />;
  if (query.isError) {
    const e = toApiError(query.error);
    return <div className="mx-auto max-w-xl py-10"><ErrorState error={query.error} title={e.status === 404 ? "Achievement not available" : "Could not load this achievement"} /></div>;
  }
  const a = query.data;
  const isOwner = a.is_owner;
  const canReview = isModerator && !isOwner && (a.verification_status === "pending" || a.verification_status === "more_information_required");
  const privateView = isOwner || isModerator;

  const run = async (key: string, action: () => Promise<{ message: string }>) => {
    setBusy(key);
    try {
      const r = await action();
      toast.success(r.message);
      refresh();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(null);
    }
  };

  const changeVisibility = (visibility: Visibility) => run("visibility", () => achievementsApi.update(a.id, { visibility }));

  const remove = async () => {
    if (!(await confirm({ title: "Delete this achievement?", description: "Its evidence files and verification history are deleted too. This cannot be undone.", confirmLabel: "Delete" }))) return;
    setBusy("delete");
    try {
      await achievementsApi.remove(a.id);
      toast.success("Achievement deleted.");
      void queryClient.invalidateQueries({ queryKey: ["achievements"] });
      navigate("/achievements", { replace: true });
    } catch (error) {
      toast.error(errorMessage(error));
      setBusy(null);
    }
  };

  const share = async () => {
    setBusy("share");
    try {
      await socialApi.shareResource("achievement", a.id, caption.trim());
      toast.success("Shared to your feed.");
      setShareOpen(false);
      setCaption("");
      void queryClient.invalidateQueries({ queryKey: ["social"] });
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Link to="/achievements" className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"><ArrowLeft className="h-4 w-4" /> Achievements</Link>

      <div className="card overflow-hidden">
        <div className="relative bg-gradient-to-br from-brand-800 via-brand-700 to-brand-500 px-6 py-8 text-white sm:px-8">
          <div className="absolute top-0 right-10 h-full w-24 bg-white/5" aria-hidden />
          <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center">
            <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-white/95 text-brand-800 shadow"><Award className="h-8 w-8" /></span>
            <div className="min-w-0">
              <p className="text-xs font-semibold tracking-widest text-brand-100 uppercase">{levelLabels[a.level]} · {achievementTypeLabels[a.achievement_type]}{a.position ? ` · ${a.position}` : ""}</p>
              <h1 className="mt-1 text-2xl leading-tight font-bold text-white sm:text-3xl">{a.title}</h1>
              <Link to={`/profile/${a.user.id}`} className="mt-3 inline-flex items-center gap-2 text-sm text-brand-50 hover:text-white">
                <Avatar src={a.user.profile_picture} name={a.user.full_name} size="xs" /> {a.user.full_name}
              </Link>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-6 py-4 sm:px-8">
          <VerificationBadge status={a.verification_status} />
          {a.is_featured && <Badge tone="warning" icon={<Star className="h-3 w-3 fill-current" />}>Featured</Badge>}
          {a.category && <Badge tone="brand">{a.category.name}</Badge>}
          {privateView && <VisibilityBadge visibility={a.visibility} />}
          <div className="ml-auto flex flex-wrap gap-2">
            {isOwner && <Link to={`/achievements/${a.id}/edit`}><Button size="sm" variant="outline" icon={<Pencil className="h-4 w-4" />}>Edit</Button></Link>}
            {(isOwner || isAdmin) && a.verification_status === "verified" && (
              a.is_featured
                ? <Button size="sm" variant="outline" loading={busy === "feature"} onClick={() => run("feature", () => achievementsApi.unfeature(a.id))} icon={<StarOff className="h-4 w-4" />}>Unfeature</Button>
                : <Button size="sm" variant="outline" loading={busy === "feature"} onClick={() => run("feature", () => achievementsApi.feature(a.id))} icon={<Star className="h-4 w-4" />}>Feature</Button>
            )}
            {a.verification_status === "verified" && a.visibility === "public" && <Button size="sm" variant="outline" onClick={() => setShareOpen(true)} icon={<Repeat2 className="h-4 w-4" />}>Share</Button>}
            {isOwner && (a.verification_status === "rejected" || a.verification_status === "more_information_required") && (
              <Button size="sm" onClick={() => setResubmitOpen(true)} icon={<Send className="h-4 w-4" />}>Resubmit</Button>
            )}
            {(isOwner || isAdmin) && <Button size="sm" variant="ghost" className="text-rose-600 hover:bg-rose-50" loading={busy === "delete"} onClick={remove} icon={<Trash2 className="h-4 w-4" />}>Delete</Button>}
          </div>
        </div>

        {isOwner && a.verification_status !== "verified" && (
          <div className={`mx-6 mt-5 rounded-xl px-4 py-3 text-sm sm:mx-8 ${a.verification_status === "rejected" ? "bg-rose-50 text-rose-900" : a.verification_status === "more_information_required" ? "bg-sky-50 text-sky-900" : "bg-amber-50 text-amber-900"}`}>
            <p className="font-semibold">{verificationLabels[a.verification_status]}</p>
            <p className="mt-0.5">
              {a.verification_status === "pending" && "A reviewer will check this soon. Until it is verified, only you and reviewers can see it."}
              {a.verification_status === "rejected" && (a.rejection_reason ? `Reason: ${a.rejection_reason}` : "See the history below for the reviewer's comments.")}
              {a.verification_status === "more_information_required" && "Check the reviewer's comment below, add details or evidence, then resubmit."}
            </p>
          </div>
        )}

        <div className="grid gap-6 p-6 sm:p-8 md:grid-cols-[minmax(0,1fr)_16rem]">
          <div>
            {a.description ? <p className="prose-plain text-[15px] leading-relaxed text-slate-700">{a.description}</p> : <p className="text-sm text-slate-500">No description.</p>}
            {a.skills.length > 0 && (
              <div className="mt-5">
                <p className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Skills</p>
                <div className="flex flex-wrap gap-1.5">{a.skills.map((s) => <span key={s} className="chip bg-brand-50 text-brand-800">{s}</span>)}</div>
              </div>
            )}
          </div>
          <div className="space-y-4">
            <Detail icon={<CalendarDays className="h-4 w-4" />} label="Date">{formatDate(a.achievement_date)}</Detail>
            {a.organization && <Detail icon={<Building2 className="h-4 w-4" />} label="Organization">{a.organization}</Detail>}
            {a.event_name && <Detail icon={<Award className="h-4 w-4" />} label="Event">{a.event_name}</Detail>}
            {a.location && <Detail icon={<MapPin className="h-4 w-4" />} label="Location">{a.location}</Detail>}
            {a.related_announcement && (
              <Detail icon={<Megaphone className="h-4 w-4" />} label="Related announcement">
                {a.related_announcement.available && a.related_announcement.id ? <Link to={`/announcements/${a.related_announcement.id}`} className="text-brand-700 hover:underline">{a.related_announcement.title}</Link> : "No longer available"}
              </Detail>
            )}
            {a.verified_at && <Detail icon={<BadgeCheck className="h-4 w-4" />} label="Verified">{formatDate(a.verified_at)}{a.verified_by ? ` by @${a.verified_by.username}` : ""}</Detail>}
            {isOwner && (
              <Select label="Visibility" value={a.visibility} disabled={busy === "visibility"} onChange={(e) => changeVisibility(e.target.value as Visibility)}
                options={(["public", "members_only", "private"] as Visibility[]).map((v) => ({ value: v, label: visibilityLabels[v] }))}
                hint={a.visibility === "private" ? "Only you (and reviewers) can see it." : "Others see it once it is verified."} />
            )}
          </div>
        </div>
      </div>

      {canReview && <ReviewPanel achievement={a} onDone={refresh} />}
      {privateView && <EvidenceGallery achievement={a} canManage={isOwner} onChanged={refresh} />}
      {privateView && <HistoryTimeline id={a.id} />}
      {!privateView && user && <p className="text-center text-xs text-slate-400">Certificates and evidence files are private to the owner and reviewers.</p>}

      <Modal open={resubmitOpen} onClose={() => setResubmitOpen(false)} title="Resubmit for verification" size="sm"
        footer={<><Button variant="outline" onClick={() => setResubmitOpen(false)}>Cancel</Button><Button loading={busy === "resubmit"} onClick={async () => { await run("resubmit", () => achievementsApi.resubmit(a.id, note.trim())); setResubmitOpen(false); setNote(""); }}>Resubmit</Button></>}>
        <Textarea label="Note for the reviewer (optional)" rows={3} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} placeholder="What did you add or change?" />
      </Modal>
      <Modal open={shareOpen} onClose={() => setShareOpen(false)} title="Share to your feed" size="sm"
        footer={<><Button variant="outline" onClick={() => setShareOpen(false)}>Cancel</Button><Button loading={busy === "share"} onClick={share} icon={<Repeat2 className="h-4 w-4" />}>Share</Button></>}>
        <Textarea label="Caption (optional)" rows={3} maxLength={500} value={caption} onChange={(e) => setCaption(e.target.value)} />
      </Modal>
    </div>
  );
}
