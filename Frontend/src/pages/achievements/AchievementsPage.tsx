import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Award, BadgeCheck, Clock, Compass, Plus, Search, ShieldCheck, Star, UserRound, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { AchievementCard } from "@/components/achievements/AchievementCard";
import { Button } from "@/components/common/Button";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/common/Feedback";
import { Select } from "@/components/common/Field";
import { LoadMore } from "@/components/common/LoadMore";
import { PageHeader } from "@/components/common/PageHeader";
import { Tabs } from "@/components/common/Tabs";
import { useAuth } from "@/contexts/AuthContext";
import { useDebounce } from "@/hooks/useDebounce";
import { qk } from "@/hooks/queryKeys";
import { achievementsApi, type AchievementFilters } from "@/services/api/achievements";
import type { AchievementLevel, VerificationStatus } from "@/types/api";
import { levelLabels, verificationLabels } from "@/utils/labels";

type Tab = "mine" | "explore" | "featured";

function Stat({ icon, label, value, tone }: { icon: ReactNode; label: string; value: number | undefined; tone: string }) {
  return (
    <div className="card flex items-center gap-3 p-4">
      <span className={`flex h-10 w-10 items-center justify-center rounded-xl ${tone}`}>{icon}</span>
      <div><p className="text-xl leading-none font-bold text-slate-900">{value ?? "–"}</p><p className="mt-1 text-xs text-slate-500">{label}</p></div>
    </div>
  );
}

export default function AchievementsPage() {
  const { isModerator } = useAuth();
  const [tab, setTab] = useState<Tab>("mine");
  const [status, setStatus] = useState<VerificationStatus | "">("");
  const [level, setLevel] = useState<AchievementLevel | "">("");
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const q = useDebounce(search.trim());

  const stats = useQuery({ queryKey: ["achievements", "stats"], queryFn: async () => (await achievementsApi.stats()).data.statistics });
  const categories = useQuery({ queryKey: qk.achievementCategories, queryFn: async () => (await achievementsApi.categories()).data.results, staleTime: 600_000 });

  const filters: AchievementFilters = { level, category, ...(tab === "mine" ? { status } : {}), ...(q ? { q } : {}) };
  const list = useInfiniteQuery({
    queryKey: qk.achievements(tab, filters),
    queryFn: async ({ pageParam }) => {
      const params = { ...filters, page: pageParam };
      if (tab === "mine") return (await achievementsApi.mine(params)).data;
      if (tab === "featured") return (await achievementsApi.list({ ...params, featured: true })).data;
      return (q ? await achievementsApi.search(params) : await achievementsApi.list(params)).data;
    },
    initialPageParam: 1,
    getNextPageParam: (last) => (last.pagination.next ? last.pagination.page + 1 : undefined),
  });
  const items = list.data?.pages.flatMap((p) => p.results) ?? [];
  const s = stats.data;

  return (
    <div>
      <PageHeader
        icon={<Award className="h-5 w-5" />}
        title="Achievements"
        description="Your verified extra-curricular portfolio: awards, certificates, competitions and roles."
        actions={
          <>
            {isModerator && <Link to="/moderation"><Button variant="outline" icon={<ShieldCheck className="h-4 w-4" />}>Review queue</Button></Link>}
            <Link to="/achievements/new"><Button icon={<Plus className="h-4 w-4" />}>Add achievement</Button></Link>
          </>
        }
      />

      {tab === "mine" && (
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat icon={<Award className="h-5 w-5" />} label="Total" value={s?.total} tone="bg-slate-100 text-slate-700" />
          <Stat icon={<BadgeCheck className="h-5 w-5" />} label="Verified" value={s?.verified} tone="bg-emerald-50 text-emerald-700" />
          <Stat icon={<Clock className="h-5 w-5" />} label="Awaiting review" value={s ? s.pending + s.more_information_required : undefined} tone="bg-amber-50 text-amber-700" />
          <Stat icon={<Star className="h-5 w-5" />} label="Featured" value={s?.featured} tone="bg-violet-50 text-violet-700" />
        </div>
      )}

      <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Tabs<Tab>
          value={tab}
          onChange={(v) => { setTab(v); setStatus(""); }}
          items={[
            { value: "mine", label: <><UserRound className="h-4 w-4" /> My portfolio</> },
            { value: "explore", label: <><Compass className="h-4 w-4" /> Explore</> },
            { value: "featured", label: <><Star className="h-4 w-4" /> Featured</> },
          ]}
        />
        <div className="flex flex-wrap gap-2">
          {tab === "explore" && (
            <div className="relative w-full sm:w-64">
              <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <label htmlFor="ach-search" className="sr-only">Search achievements</label>
              <input id="ach-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search title, skill, organization…" className="input h-10 pl-9" maxLength={100} />
              {search && <button onClick={() => setSearch("")} className="absolute top-1/2 right-2 -translate-y-1/2 p-1 text-slate-400" aria-label="Clear search"><X className="h-4 w-4" /></button>}
            </div>
          )}
          {tab === "mine" && <Select aria-label="Status" wrapperClassName="w-44" className="h-10 py-2" value={status} onChange={(e) => setStatus(e.target.value as VerificationStatus | "")} placeholder="All statuses" options={Object.entries(verificationLabels).map(([v, l]) => ({ value: v, label: l }))} />}
          <Select aria-label="Category" wrapperClassName="w-44" className="h-10 py-2" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="All categories" options={(categories.data ?? []).map((c) => ({ value: c.slug, label: c.name }))} />
          <Select aria-label="Level" wrapperClassName="w-40" className="h-10 py-2" value={level} onChange={(e) => setLevel(e.target.value as AchievementLevel | "")} placeholder="All levels" options={Object.entries(levelLabels).map(([v, l]) => ({ value: v, label: l }))} />
        </div>
      </div>

      {list.isPending ? (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 3 }).map((_, i) => <CardSkeleton key={i} />)}</div>
      ) : list.isError ? (
        <ErrorState error={list.error} onRetry={() => void list.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Award className="h-6 w-6" />}
          title={tab === "mine" ? "Start your portfolio" : "No achievements found"}
          description={tab === "mine" ? "Add an award, certificate or role. A reviewer verifies it before it appears on your public profile." : "Only verified achievements that their owners made visible appear here."}
          action={tab === "mine" ? <Link to="/achievements/new"><Button icon={<Plus className="h-4 w-4" />}>Add your first achievement</Button></Link> : undefined}
        />
      ) : (
        <>
          <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {items.map((a) => <AchievementCard key={a.id} achievement={a} showUser={tab !== "mine"} showStatus={tab === "mine"} />)}
          </div>
          <LoadMore hasMore={!!list.hasNextPage} loading={list.isFetchingNextPage} onLoad={() => void list.fetchNextPage()} />
        </>
      )}
    </div>
  );
}
