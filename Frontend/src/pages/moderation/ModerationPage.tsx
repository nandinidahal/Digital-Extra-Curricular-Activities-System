import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Award, BarChart3, Flag, Megaphone, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { VerificationBadge } from "@/components/achievements/AchievementCard";
import { Avatar } from "@/components/common/Avatar";
import { Button } from "@/components/common/Button";
import { Badge, CardSkeleton, EmptyState, ErrorState } from "@/components/common/Feedback";
import { Select, Textarea } from "@/components/common/Field";
import { LoadMore } from "@/components/common/LoadMore";
import { Modal } from "@/components/common/Modal";
import { PageHeader } from "@/components/common/PageHeader";
import { Tabs } from "@/components/common/Tabs";
import { achievementsApi } from "@/services/api/achievements";
import { announcementsApi } from "@/services/api/announcements";
import { errorMessage } from "@/services/api/errors";
import { socialApi } from "@/services/api/social";
import type { AnnouncementReport, SocialReport } from "@/types/api";
import { timeAgo } from "@/utils/format";
import { achievementTypeLabels, announcementReportReasons, levelLabels, socialReportReasons } from "@/utils/labels";

type Tab = "reviews" | "announcements" | "social" | "stats";

function pager<T>(key: unknown[], fn: (page: number) => Promise<{ data: { results: T[]; pagination: { next: string | null; page: number } } }>) {
  return {
    queryKey: key,
    queryFn: async ({ pageParam }: { pageParam: number }) => (await fn(pageParam)).data,
    initialPageParam: 1,
    getNextPageParam: (last: { pagination: { next: string | null; page: number } }) => (last.pagination.next ? last.pagination.page + 1 : undefined),
  };
}

function ReviewQueue() {
  const query = useInfiniteQuery(pager(["achievements", "pending"], achievementsApi.pending));
  const items = query.data?.pages.flatMap((p) => p.results) ?? [];
  if (query.isPending) return <CardSkeleton lines={1} />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  if (!items.length) return <EmptyState icon={<Award className="h-6 w-6" />} title="Review queue is empty" description="New and resubmitted achievements appear here, oldest first. Your own are never listed." />;
  return (
    <>
      <ul className="card divide-y divide-slate-100">
        {items.map((a) => (
          <li key={a.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
            <Avatar src={a.user.profile_picture} name={a.user.full_name} />
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-slate-900">{a.title}</p>
              <p className="text-sm text-slate-500">{a.user.full_name} · {levelLabels[a.level]} {achievementTypeLabels[a.achievement_type]} · submitted {timeAgo(a.submitted_at)}</p>
            </div>
            <VerificationBadge status={a.verification_status} />
            <Link to={`/achievements/${a.id}`}><Button size="sm">Review</Button></Link>
          </li>
        ))}
      </ul>
      <LoadMore hasMore={!!query.hasNextPage} loading={query.isFetchingNextPage} onLoad={() => void query.fetchNextPage()} />
    </>
  );
}

function ReviewDialog({ title, statuses, actions, open, onClose, onSubmit }: {
  title: string; statuses: { value: string; label: string }[]; actions: { value: string; label: string }[];
  open: boolean; onClose: () => void; onSubmit: (status: string, comments: string, action: string) => Promise<unknown>;
}) {
  const [status, setStatus] = useState(statuses[0].value);
  const [action, setAction] = useState("none");
  const [comments, setComments] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      await onSubmit(status, comments.trim(), action);
      toast.success("Report updated.");
      onClose();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal open={open} onClose={onClose} title={title} size="sm" footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button loading={busy} onClick={submit}>Save decision</Button></>}>
      <div className="space-y-4">
        <Select label="Status" value={status} onChange={(e) => { setStatus(e.target.value); if (e.target.value !== "resolved") setAction("none"); }} options={statuses} />
        {status === "resolved" && <Select label="Action" value={action} onChange={(e) => setAction(e.target.value)} options={actions} />}
        <Textarea label="Review comments" rows={3} maxLength={1000} value={comments} onChange={(e) => setComments(e.target.value)} />
      </div>
    </Modal>
  );
}

function AnnouncementReports() {
  const [status, setStatus] = useState("pending");
  const [reviewing, setReviewing] = useState<AnnouncementReport | null>(null);
  const query = useInfiniteQuery(pager(["announcements", "reports", status], (page) => announcementsApi.reports(status, page)));
  const items = query.data?.pages.flatMap((p) => p.results) ?? [];
  return (
    <>
      <Tabs className="mb-4" value={status} onChange={setStatus} items={[{ value: "pending", label: "Pending" }, { value: "reviewed", label: "Reviewed" }, { value: "resolved", label: "Resolved" }, { value: "rejected", label: "Rejected" }, { value: "", label: "All" }]} />
      {query.isPending ? <CardSkeleton lines={1} /> : query.isError ? <ErrorState error={query.error} /> : !items.length ? <EmptyState icon={<Flag className="h-6 w-6" />} title="No reports here" /> : (
        <ul className="card divide-y divide-slate-100">
          {items.map((r) => (
            <li key={r.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <Link to={`/announcements/${r.announcement.id}`} className="font-medium text-slate-900 hover:underline">{r.announcement.title}</Link>
                <p className="text-sm text-slate-500">{announcementReportReasons[r.reason]} · by @{r.reporter.username} · {timeAgo(r.created_at)}</p>
                {r.description && <p className="mt-1 text-sm text-slate-700">“{r.description}”</p>}
                {r.reviewed_by && <p className="mt-1 text-xs text-slate-500">Reviewed by @{r.reviewed_by.username}{r.action_taken !== "none" ? " · announcement archived" : ""}{r.review_comments ? ` · ${r.review_comments}` : ""}</p>}
              </div>
              <Badge tone={r.status === "pending" ? "warning" : r.status === "resolved" ? "success" : "neutral"}>{r.status}</Badge>
              {(r.status === "pending" || r.status === "reviewed") && <Button size="sm" onClick={() => setReviewing(r)}>Review</Button>}
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={!!query.hasNextPage} loading={query.isFetchingNextPage} onLoad={() => void query.fetchNextPage()} />
      {reviewing && (
        <ReviewDialog
          open
          title="Review announcement report"
          onClose={() => setReviewing(null)}
          statuses={[{ value: "resolved", label: "Resolved" }, { value: "rejected", label: "Rejected (no problem)" }, ...(reviewing.status === "pending" ? [{ value: "reviewed", label: "Reviewed (needs follow-up)" }] : [])]}
          actions={[{ value: "none", label: "No action" }, { value: "archived", label: "Archive the announcement" }]}
          onSubmit={async (s, c, a) => { await announcementsApi.reviewReport(reviewing.id, { status: s, review_comments: c, action: a as "none" | "archived" }); void query.refetch(); }}
        />
      )}
    </>
  );
}

function SocialReports() {
  const [status, setStatus] = useState("pending");
  const [reviewing, setReviewing] = useState<SocialReport | null>(null);
  const query = useInfiniteQuery(pager(["social-reports", status], (page) => socialApi.reports(status, page)));
  const items = query.data?.pages.flatMap((p) => p.results) ?? [];
  return (
    <>
      <Tabs className="mb-4" value={status} onChange={setStatus} items={[{ value: "pending", label: "Pending" }, { value: "reviewing", label: "Under review" }, { value: "resolved", label: "Resolved" }, { value: "dismissed", label: "Dismissed" }, { value: "", label: "All" }]} />
      {query.isPending ? <CardSkeleton lines={1} /> : query.isError ? <ErrorState error={query.error} /> : !items.length ? <EmptyState icon={<Flag className="h-6 w-6" />} title="No reports here" /> : (
        <ul className="card divide-y divide-slate-100">
          {items.map((r) => (
            <li key={r.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start">
              <div className="min-w-0 flex-1">
                <p className="text-sm text-slate-500"><Badge className="mr-2">{r.content_type}</Badge>{socialReportReasons[r.reason]} · by @{r.reporter.username} · {timeAgo(r.created_at)}</p>
                <blockquote className="prose-plain mt-2 line-clamp-3 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">{r.target.is_deleted ? <em>Content removed</em> : r.target.content || <em>(no text)</em>}</blockquote>
                {r.description && <p className="mt-1 text-sm text-slate-600">Reporter: “{r.description}”</p>}
                {!r.target.is_deleted && <Link to={`/social/posts/${r.target.post_id}`} className="mt-1 inline-block text-xs font-medium text-brand-700 hover:underline">Open post</Link>}
              </div>
              <Badge tone={r.status === "pending" ? "warning" : r.status === "resolved" ? "success" : "neutral"}>{r.status}</Badge>
              {(r.status === "pending" || r.status === "reviewing") && <Button size="sm" onClick={() => setReviewing(r)}>Review</Button>}
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={!!query.hasNextPage} loading={query.isFetchingNextPage} onLoad={() => void query.fetchNextPage()} />
      {reviewing && (
        <ReviewDialog
          open
          title={`Review ${reviewing.content_type} report`}
          onClose={() => setReviewing(null)}
          statuses={[{ value: "resolved", label: "Resolved" }, { value: "dismissed", label: "Dismissed" }, ...(reviewing.status === "pending" ? [{ value: "reviewing", label: "Mark under review" }] : [])]}
          actions={[{ value: "none", label: "No action" }, { value: "content_removed", label: `Remove the ${reviewing.content_type}` }]}
          onSubmit={async (s, c, a) => { await socialApi.reviewReport(reviewing.id, { status: s, review_comments: c, action: a as "none" | "content_removed" }); void query.refetch(); }}
        />
      )}
    </>
  );
}

function PlatformStats() {
  const query = useQuery({ queryKey: ["achievements", "stats", "platform"], queryFn: async () => (await achievementsApi.stats("platform")).data.statistics });
  if (query.isPending) return <CardSkeleton />;
  if (query.isError) return <ErrorState error={query.error} />;
  const s = query.data;
  const max = Math.max(1, ...s.by_category.map((c) => c.count));
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="card grid grid-cols-2 gap-4 p-5 sm:grid-cols-3">
        {[["Total", s.total], ["Verified", s.verified], ["Pending", s.pending], ["Need info", s.more_information_required], ["Rejected", s.rejected], ["Featured", s.featured]].map(([label, value]) => (
          <div key={label as string}><p className="text-2xl font-bold text-slate-900">{value}</p><p className="text-xs text-slate-500">{label}</p></div>
        ))}
      </div>
      <div className="card p-5">
        <h3 className="mb-3 text-sm font-semibold">Achievements by category</h3>
        <ul className="space-y-2">
          {s.by_category.map((c) => (
            <li key={c.category} className="text-sm">
              <div className="flex justify-between"><span className="text-slate-700">{c.category}</span><span className="text-slate-500">{c.count}</span></div>
              <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand-600" style={{ width: `${(c.count / max) * 100}%` }} /></div>
            </li>
          ))}
          {!s.by_category.length && <li className="text-sm text-slate-500">No data yet.</li>}
        </ul>
      </div>
    </div>
  );
}

export default function ModerationPage() {
  const [tab, setTab] = useState<Tab>("reviews");
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader icon={<ShieldCheck className="h-5 w-5" />} title="Moderation" description="Verify achievements and handle reports. Available to coordinators and administrators." />
      <Tabs<Tab>
        className="mb-5"
        value={tab}
        onChange={setTab}
        items={[
          { value: "reviews", label: <><Award className="h-4 w-4" /> Achievement reviews</> },
          { value: "announcements", label: <><Megaphone className="h-4 w-4" /> Announcement reports</> },
          { value: "social", label: <><Flag className="h-4 w-4" /> Post reports</> },
          { value: "stats", label: <><BarChart3 className="h-4 w-4" /> Statistics</> },
        ]}
      />
      {tab === "reviews" && <ReviewQueue />}
      {tab === "announcements" && <AnnouncementReports />}
      {tab === "social" && <SocialReports />}
      {tab === "stats" && <PlatformStats />}
    </div>
  );
}
