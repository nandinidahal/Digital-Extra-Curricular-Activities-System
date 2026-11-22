import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive, ArrowLeft, Bookmark, BookmarkCheck, CalendarClock, CalendarDays, ExternalLink, Flag, Lock, Mail,
  MapPin, Pencil, Phone, Repeat2, RotateCcw, Send, Trash2, UserRound, Video,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ActivityIcon, StatusBadge } from "@/components/announcements/AnnouncementCard";
import { Avatar } from "@/components/common/Avatar";
import { Button } from "@/components/common/Button";
import { Badge, ErrorState, PageLoader } from "@/components/common/Feedback";
import { Textarea } from "@/components/common/Field";
import { Modal, useConfirm } from "@/components/common/Modal";
import { ReportDialog } from "@/components/social/ReportDialog";
import { useAuth } from "@/contexts/AuthContext";
import { qk } from "@/hooks/queryKeys";
import { useBookmark } from "@/hooks/useBookmark";
import { announcementsApi } from "@/services/api/announcements";
import { errorMessage, toApiError } from "@/services/api/errors";
import { socialApi } from "@/services/api/social";
import type { AnnouncementDetail } from "@/types/api";
import { formatDateTime } from "@/utils/format";
import { activityTypeLabels, announcementReportReasons, visibilityLabels } from "@/utils/labels";

function InfoRow({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700">{icon}</span>
      <div className="min-w-0">
        <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">{label}</p>
        <div className="mt-0.5 text-sm break-words text-slate-800">{children}</div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="mb-2 text-base font-semibold">{title}</h2>
      <p className="prose-plain text-[15px] leading-relaxed text-slate-700">{children}</p>
    </section>
  );
}

function ShareToFeed({ announcement, open, onClose }: { announcement: AnnouncementDetail; open: boolean; onClose: () => void }) {
  const [caption, setCaption] = useState("");
  const [busy, setBusy] = useState(false);
  const queryClient = useQueryClient();
  const share = async () => {
    setBusy(true);
    try {
      await socialApi.shareResource("announcement", announcement.id, caption.trim());
      toast.success("Shared to your feed.");
      void queryClient.invalidateQueries({ queryKey: ["social"] });
      onClose();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal open={open} onClose={onClose} title="Share to your feed" size="sm" footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button loading={busy} onClick={share} icon={<Repeat2 className="h-4 w-4" />}>Share</Button></>}>
      <Textarea label="Say something about it (optional)" rows={3} maxLength={500} value={caption} onChange={(e) => setCaption(e.target.value)} />
    </Modal>
  );
}

export default function AnnouncementDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const { isModerator } = useAuth();
  const { toggle, pending } = useBookmark();
  const [reporting, setReporting] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const query = useQuery({ queryKey: qk.announcement(id), queryFn: async () => (await announcementsApi.get(id)).data.announcement });

  if (query.isPending) return <PageLoader />;
  if (query.isError) {
    const e = toApiError(query.error);
    return (
      <div className="mx-auto max-w-xl py-10">
        <ErrorState error={query.error} title={e.status === 404 ? "Announcement not available" : "Could not load this announcement"} onRetry={e.status === 404 ? undefined : () => void query.refetch()} />
        <div className="mt-4 text-center"><Link to="/announcements" className="text-sm font-semibold text-brand-700 hover:underline">Back to announcements</Link></div>
      </div>
    );
  }
  const a = query.data;
  const isOwner = a.is_owner;

  const lifecycle = async (action: "publish" | "archive" | "restore") => {
    if (action === "archive" && !(await confirm({ title: "Archive this announcement?", description: "It will disappear from public listings and search. People who bookmarked it are notified.", confirmLabel: "Archive", tone: "primary" }))) return;
    setBusy(action);
    try {
      const r = await announcementsApi[action](a.id);
      queryClient.setQueryData(qk.announcement(a.id), r.data.announcement);
      void queryClient.invalidateQueries({ queryKey: ["announcements", "list"] });
      toast.success(r.message);
    } catch (error) {
      const err = toApiError(error);
      const fields = Object.entries(err.fieldErrors);
      if (action === "publish" && fields.length) {
        toast.error("Complete these before publishing:", { description: fields.map(([f, m]) => `${f.replace(/_/g, " ")}: ${m[0]}`).join("\n"), duration: 9000 });
      } else toast.error(errorMessage(error));
    } finally {
      setBusy(null);
    }
  };

  const remove = async () => {
    if (!(await confirm({ title: "Delete this announcement?", description: "This permanently deletes it, including bookmarks and reports. This cannot be undone.", confirmLabel: "Delete" }))) return;
    setBusy("delete");
    try {
      await announcementsApi.remove(a.id);
      toast.success("Announcement deleted.");
      void queryClient.invalidateQueries({ queryKey: ["announcements"] });
      navigate("/announcements", { replace: true });
    } catch (error) {
      toast.error(errorMessage(error));
      setBusy(null);
    }
  };

  const canShare = a.status === "published" && a.visibility === "public";

  return (
    <div className="mx-auto max-w-6xl">
      <Link to="/announcements" className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"><ArrowLeft className="h-4 w-4" /> All announcements</Link>

      <div className="card overflow-hidden">
        <div className="relative h-48 bg-gradient-to-br from-brand-700 to-brand-500 sm:h-72">
          {a.cover_image && <img src={a.cover_image} alt="" className="h-full w-full object-cover" />}
        </div>
        <div className="p-5 sm:p-8">
          <div className="flex flex-wrap items-center gap-1.5">
            {a.category && <Badge tone="brand">{a.category.name}</Badge>}
            <Badge icon={<ActivityIcon type={a.activity_type} className="h-3 w-3" />}>{activityTypeLabels[a.activity_type]}</Badge>
            {a.visibility !== "public" && <Badge tone="info" icon={<Lock className="h-3 w-3" />}>{visibilityLabels[a.visibility]}</Badge>}
            <StatusBadge status={a.status} />
            {a.is_edited && <Badge>Updated</Badge>}
          </div>
          <h1 className="mt-3 text-2xl leading-tight font-bold sm:text-3xl">{a.title}</h1>
          {a.short_description && <p className="mt-2 text-lg text-slate-600">{a.short_description}</p>}

          <div className="mt-5 flex flex-wrap gap-2">
            {a.status === "published" && (
              <Button variant={a.is_bookmarked ? "subtle" : "outline"} loading={pending === a.id} onClick={() => toggle(a)} icon={a.is_bookmarked ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}>
                {a.is_bookmarked ? "Bookmarked" : "Bookmark"}
              </Button>
            )}
            {canShare && <Button variant="outline" onClick={() => setSharing(true)} icon={<Repeat2 className="h-4 w-4" />}>Share to feed</Button>}
            {isOwner && a.status === "draft" && <Button loading={busy === "publish"} onClick={() => lifecycle("publish")} icon={<Send className="h-4 w-4" />}>Publish</Button>}
            {isOwner && a.status !== "archived" && <Link to={`/announcements/${a.id}/edit`}><Button variant="outline" icon={<Pencil className="h-4 w-4" />}>Edit</Button></Link>}
            {isOwner && a.status === "archived" && <Button variant="outline" loading={busy === "restore"} onClick={() => lifecycle("restore")} icon={<RotateCcw className="h-4 w-4" />}>Restore as draft</Button>}
            {(isOwner || isModerator) && a.status !== "archived" && <Button variant="ghost" loading={busy === "archive"} onClick={() => lifecycle("archive")} icon={<Archive className="h-4 w-4" />}>Archive</Button>}
            {(isOwner || isModerator) && <Button variant="ghost" className="text-rose-600 hover:bg-rose-50 hover:text-rose-700" loading={busy === "delete"} onClick={remove} icon={<Trash2 className="h-4 w-4" />}>Delete</Button>}
            {!isOwner && a.status === "published" && <Button variant="ghost" onClick={() => setReporting(true)} icon={<Flag className="h-4 w-4" />}>Report</Button>}
          </div>
          {isOwner && a.status === "draft" && <p className="mt-3 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">This is a draft. Only you can see it until you publish it.</p>}
          {a.status === "archived" && <p className="mt-3 rounded-xl bg-slate-100 px-4 py-3 text-sm text-slate-700">This announcement is archived{a.archived_at ? ` (${formatDateTime(a.archived_at)})` : ""} and hidden from listings.</p>}
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="card space-y-7 p-5 sm:p-8">
          {a.description ? <Section title="About this activity">{a.description}</Section> : <p className="text-sm text-slate-500">No description yet.</p>}
          {a.eligibility_criteria && <Section title="Who can join">{a.eligibility_criteria}</Section>}
          {a.requirements && <Section title="Requirements">{a.requirements}</Section>}
        </div>
        <aside className="space-y-4">
          <div className="card space-y-4 p-5">
            {a.start_datetime && <InfoRow icon={<CalendarDays className="h-4 w-4" />} label="When">{formatDateTime(a.start_datetime)}{a.end_datetime && <><br /><span className="text-slate-500">until {formatDateTime(a.end_datetime)}</span></>}</InfoRow>}
            {a.location && <InfoRow icon={<MapPin className="h-4 w-4" />} label="Location">{a.location}</InfoRow>}
            {(a.activity_type !== "physical") && (
              <InfoRow icon={<Video className="h-4 w-4" />} label="Online">
                {a.online_link ? <a href={a.online_link} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline">Join link <ExternalLink className="h-3.5 w-3.5" /></a>
                  : a.requires_login_for_online_link ? "Log in to see the meeting link." : "Link not provided yet."}
              </InfoRow>
            )}
            {a.registration_deadline && <InfoRow icon={<CalendarClock className="h-4 w-4" />} label="Register by">{formatDateTime(a.registration_deadline)}</InfoRow>}
            {a.registration_link && (
              <a href={a.registration_link} target="_blank" rel="noopener noreferrer nofollow" className="block">
                <Button block icon={<ExternalLink className="h-4 w-4" />}>Register now</Button>
              </a>
            )}
          </div>
          <div className="card space-y-4 p-5">
            <h2 className="text-sm font-semibold">Organizer</h2>
            {a.organizer_name && <InfoRow icon={<UserRound className="h-4 w-4" />} label="Name">{a.organizer_name}</InfoRow>}
            {a.organizer_email && <InfoRow icon={<Mail className="h-4 w-4" />} label="Email"><a href={`mailto:${a.organizer_email}`} className="text-brand-700 hover:underline">{a.organizer_email}</a></InfoRow>}
            {a.organizer_phone && <InfoRow icon={<Phone className="h-4 w-4" />} label="Phone"><a href={`tel:${a.organizer_phone}`} className="text-brand-700 hover:underline">{a.organizer_phone}</a></InfoRow>}
            {a.contact_information && <p className="prose-plain text-sm text-slate-700">{a.contact_information}</p>}
            {a.contact_details_hidden && <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">The organizer keeps contact details private. Use the registration link to get in touch.</p>}
            <Link to={`/profile/${a.author.id}`} className="flex items-center gap-3 border-t border-slate-100 pt-4 hover:opacity-90">
              <Avatar src={a.author.profile_picture} name={a.author.full_name} size="sm" />
              <span className="min-w-0 text-sm"><span className="block text-xs text-slate-500">Posted by</span><span className="font-medium text-slate-800">{a.author.full_name}</span></span>
            </Link>
            {a.published_at && <p className="text-xs text-slate-400">Published {formatDateTime(a.published_at)}{a.is_edited ? ` · updated ${formatDateTime(a.updated_at)}` : ""}</p>}
          </div>
        </aside>
      </div>

      <ReportDialog open={reporting} onClose={() => setReporting(false)} title="Report announcement" reasons={announcementReportReasons} onSubmit={(r, d) => announcementsApi.report(a.id, r, d)} />
      <ShareToFeed announcement={a} open={sharing} onClose={() => setSharing(false)} />
    </div>
  );
}
