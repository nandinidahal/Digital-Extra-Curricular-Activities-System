import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Bookmark, Compass, FolderOpen, Megaphone, Plus, Search, SlidersHorizontal, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AnnouncementCard, AnnouncementCardSkeleton } from "@/components/announcements/AnnouncementCard";
import { Button } from "@/components/common/Button";
import { EmptyState, ErrorState } from "@/components/common/Feedback";
import { Input, Select } from "@/components/common/Field";
import { LoadMore } from "@/components/common/LoadMore";
import { PageHeader } from "@/components/common/PageHeader";
import { Tabs } from "@/components/common/Tabs";
import { useBookmark } from "@/hooks/useBookmark";
import { useDebounce } from "@/hooks/useDebounce";
import { qk } from "@/hooks/queryKeys";
import { announcementsApi, type AnnouncementFilters } from "@/services/api/announcements";
import type { AnnouncementStatus } from "@/types/api";
import { cn } from "@/utils/cn";
import { fromLocalInput } from "@/utils/format";
import { activityTypeLabels } from "@/utils/labels";

type Tab = "explore" | "mine" | "bookmarks";

const FILTER_KEYS = ["activity_type", "when", "registration_open", "location", "start_from", "start_to", "ordering"] as const;

export default function AnnouncementsPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) || "explore";
  const [search, setSearch] = useState(params.get("q") ?? "");
  const q = useDebounce(search.trim());
  const [showFilters, setShowFilters] = useState(FILTER_KEYS.some((k) => params.get(k)));
  const { toggle, pending } = useBookmark();

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const categories = useQuery({ queryKey: qk.categories, queryFn: async () => (await announcementsApi.categories()).data.results, staleTime: 600_000 });

  const filters: AnnouncementFilters = useMemo(() => ({
    q: q || undefined,
    category: params.get("category") ?? "",
    activity_type: (params.get("activity_type") ?? "") as AnnouncementFilters["activity_type"],
    when: (params.get("when") ?? "") as AnnouncementFilters["when"],
    registration_open: params.get("registration_open") === "true",
    location: params.get("location") ?? "",
    start_from: fromLocalInput(params.get("start_from") ?? "") ?? undefined,
    start_to: fromLocalInput(params.get("start_to") ?? "") ?? undefined,
    ordering: (params.get("ordering") || undefined) as AnnouncementFilters["ordering"],
  }), [params, q]);
  const myStatus = (params.get("status") ?? "") as AnnouncementStatus | "";

  const list = useInfiniteQuery({
    queryKey: qk.announcements({ tab, filters, myStatus }),
    queryFn: async ({ pageParam }) => {
      if (tab === "mine") return (await announcementsApi.mine(myStatus, pageParam)).data;
      // Text search uses the dedicated (authenticated, rate-limited) search endpoint.
      return (filters.q ? await announcementsApi.search({ ...filters, page: pageParam }) : await announcementsApi.list({ ...filters, page: pageParam })).data;
    },
    initialPageParam: 1,
    getNextPageParam: (last) => (last.pagination.next ? last.pagination.page + 1 : undefined),
    enabled: tab !== "bookmarks",
  });
  const bookmarks = useInfiniteQuery({
    queryKey: ["announcements", "bookmarks"],
    queryFn: async ({ pageParam }) => (await announcementsApi.bookmarks(pageParam)).data,
    initialPageParam: 1,
    getNextPageParam: (last) => (last.pagination.next ? last.pagination.page + 1 : undefined),
    enabled: tab === "bookmarks",
  });

  const items = list.data?.pages.flatMap((p) => p.results) ?? [];
  const bookmarkItems = bookmarks.data?.pages.flatMap((p) => p.results) ?? [];
  const total = list.data?.pages[0]?.pagination.count;
  const activeFilterCount = FILTER_KEYS.filter((k) => params.get(k)).length + (params.get("category") ? 1 : 0);

  return (
    <div>
      <PageHeader
        icon={<Megaphone className="h-5 w-5" />}
        title="Announcements"
        description="Workshops, competitions, volunteering and events shared by the DEAS community."
        actions={<Link to="/announcements/new"><Button icon={<Plus className="h-4 w-4" />}>Create announcement</Button></Link>}
      />
      <Tabs<Tab>
        className="mb-5"
        value={tab}
        onChange={(value) => setParam("tab", value === "explore" ? "" : value)}
        items={[
          { value: "explore", label: <><Compass className="h-4 w-4" /> Explore</> },
          { value: "mine", label: <><FolderOpen className="h-4 w-4" /> My announcements</> },
          { value: "bookmarks", label: <><Bookmark className="h-4 w-4" /> Bookmarks</> },
        ]}
      />

      {tab === "explore" && (
        <div className="mb-6 space-y-4">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <label htmlFor="ann-search" className="sr-only">Search announcements</label>
              <input id="ann-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by title, description, organizer or place…" maxLength={100} className="input h-11 pl-10" />
              {search && <button onClick={() => setSearch("")} className="absolute top-1/2 right-3 -translate-y-1/2 rounded-full p-1 text-slate-400 hover:text-slate-700" aria-label="Clear search"><X className="h-4 w-4" /></button>}
            </div>
            <Button variant={showFilters ? "secondary" : "outline"} className="h-11" onClick={() => setShowFilters((s) => !s)} icon={<SlidersHorizontal className="h-4 w-4" />} aria-expanded={showFilters}>
              <span className="hidden sm:inline">Filters</span>{activeFilterCount > 0 && <span className="rounded-full bg-brand-600 px-1.5 text-xs text-white">{activeFilterCount}</span>}
            </Button>
          </div>

          <div className="scroll-thin -mx-1 flex gap-2 overflow-x-auto px-1 pb-1" role="group" aria-label="Categories">
            <button onClick={() => setParam("category", "")} className={cn("chip shrink-0 px-3.5 py-1.5 text-sm transition", !params.get("category") ? "bg-brand-700 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200 hover:ring-brand-300")}>All</button>
            {categories.data?.map((c) => (
              <button key={c.id} onClick={() => setParam("category", params.get("category") === c.slug ? "" : c.slug)} aria-pressed={params.get("category") === c.slug}
                className={cn("chip shrink-0 px-3.5 py-1.5 text-sm transition", params.get("category") === c.slug ? "bg-brand-700 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200 hover:ring-brand-300")}>
                {c.name}
              </button>
            ))}
          </div>

          {showFilters && (
            <div className="card grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
              <Select label="Activity type" value={params.get("activity_type") ?? ""} onChange={(e) => setParam("activity_type", e.target.value)} placeholder="Any" options={Object.entries(activityTypeLabels).map(([v, l]) => ({ value: v, label: l }))} />
              <Select label="When" value={params.get("when") ?? ""} onChange={(e) => setParam("when", e.target.value)} placeholder="Any time" options={[{ value: "upcoming", label: "Upcoming" }, { value: "ongoing", label: "Happening now" }, { value: "past", label: "Past" }]} />
              <Input label="Location" value={params.get("location") ?? ""} onChange={(e) => setParam("location", e.target.value)} placeholder="e.g. Kathmandu" maxLength={100} />
              <Select label="Sort by" value={params.get("ordering") ?? ""} onChange={(e) => setParam("ordering", e.target.value)} placeholder="Newest first" options={[{ value: "start", label: "Start date (soonest)" }, { value: "-start", label: "Start date (latest)" }, { value: "deadline", label: "Registration deadline" }, { value: "title", label: "Title (A–Z)" }, { value: "oldest", label: "Oldest first" }]} />
              <Input label="Starts after" type="datetime-local" value={params.get("start_from") ?? ""} onChange={(e) => setParam("start_from", e.target.value)} />
              <Input label="Starts before" type="datetime-local" value={params.get("start_to") ?? ""} onChange={(e) => setParam("start_to", e.target.value)} />
              <label className="flex items-center gap-2 self-end pb-2.5 text-sm text-slate-700">
                <input type="checkbox" className="h-4 w-4 rounded accent-brand-700" checked={params.get("registration_open") === "true"} onChange={(e) => setParam("registration_open", e.target.checked ? "true" : "")} />
                Registration still open
              </label>
              <div className="flex items-end justify-end">
                <Button variant="ghost" size="sm" onClick={() => { const next = new URLSearchParams(); setParams(next, { replace: true }); setSearch(""); }}>Clear all</Button>
              </div>
            </div>
          )}
          {total !== undefined && <p className="text-sm text-slate-500">{total} result{total === 1 ? "" : "s"}</p>}
        </div>
      )}

      {tab === "mine" && (
        <Tabs<AnnouncementStatus | "">
          className="mb-5"
          value={myStatus}
          onChange={(v) => setParam("status", v)}
          items={[{ value: "", label: "All" }, { value: "draft", label: "Drafts" }, { value: "published", label: "Published" }, { value: "archived", label: "Archived" }]}
        />
      )}

      {tab === "bookmarks" ? (
        bookmarks.isPending ? <Grid>{Array.from({ length: 3 }).map((_, i) => <AnnouncementCardSkeleton key={i} />)}</Grid>
          : bookmarks.isError ? <ErrorState error={bookmarks.error} onRetry={() => void bookmarks.refetch()} />
            : bookmarkItems.length === 0 ? <EmptyState icon={<Bookmark className="h-6 w-6" />} title="No bookmarks yet" description="Tap the bookmark icon on an announcement to save it here. You'll get a reminder before it starts." />
              : (
                <>
                  <Grid>
                    {bookmarkItems.map((b) => b.announcement ? (
                      <AnnouncementCard key={b.id} announcement={b.announcement} onOpen={() => navigate(`/announcements/${b.announcement!.id}`)} onToggleBookmark={() => toggle(b.announcement!).then(() => void bookmarks.refetch())} bookmarkPending={pending === b.announcement_id} />
                    ) : (
                      <div key={b.id} className="card flex flex-col items-start justify-between gap-3 p-5">
                        <p className="text-sm text-slate-500">This announcement is no longer available.</p>
                        <Button size="sm" variant="outline" onClick={() => toggle({ id: b.announcement_id, is_bookmarked: true }).then(() => void bookmarks.refetch())}>Remove bookmark</Button>
                      </div>
                    ))}
                  </Grid>
                  <LoadMore hasMore={!!bookmarks.hasNextPage} loading={bookmarks.isFetchingNextPage} onLoad={() => void bookmarks.fetchNextPage()} />
                </>
              )
      ) : list.isPending ? (
        <Grid>{Array.from({ length: 6 }).map((_, i) => <AnnouncementCardSkeleton key={i} />)}</Grid>
      ) : list.isError ? (
        <ErrorState error={list.error} onRetry={() => void list.refetch()} title="Could not load announcements" />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Megaphone className="h-6 w-6" />}
          title={tab === "mine" ? "You haven't created announcements yet" : "No announcements match"}
          description={tab === "mine" ? "Share an event, workshop or opportunity with the community." : "Try another search term or remove some filters."}
          action={tab === "mine" ? <Link to="/announcements/new"><Button icon={<Plus className="h-4 w-4" />}>Create announcement</Button></Link> : undefined}
        />
      ) : (
        <>
          <Grid>
            {items.map((a) => (
              <AnnouncementCard
                key={a.id}
                announcement={a}
                onOpen={() => navigate(`/announcements/${a.id}`)}
                onToggleBookmark={a.status === "published" ? () => void toggle(a) : undefined}
                bookmarkPending={pending === a.id}
                showAuthor={tab !== "mine"}
              />
            ))}
          </Grid>
          <LoadMore hasMore={!!list.hasNextPage} loading={list.isFetchingNextPage} onLoad={() => void list.fetchNextPage()} />
        </>
      )}
    </div>
  );
}

function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">{children}</div>;
}
