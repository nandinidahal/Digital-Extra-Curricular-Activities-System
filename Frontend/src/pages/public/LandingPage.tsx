import { useInfiniteQuery } from "@tanstack/react-query";
import { ArrowRight, Award, Lock, Megaphone, Search, Users } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { AnnouncementCard, AnnouncementCardSkeleton } from "@/components/announcements/AnnouncementCard";
import { Button } from "@/components/common/Button";
import { EmptyState, ErrorState } from "@/components/common/Feedback";
import { LoadMore } from "@/components/common/LoadMore";
import { announcementsApi } from "@/services/api/announcements";

/**
 * Public landing page: published PUBLIC announcements from GET /api/announcements/public/.
 * Visitors can browse cards only. Search, filters, creation and full details need an account;
 * opening a card goes to the protected detail route, which redirects to login and back.
 */
export default function LandingPage() {
  const navigate = useNavigate();
  const query = useInfiniteQuery({
    queryKey: ["announcements", "public"],
    queryFn: async ({ pageParam }) => (await announcementsApi.publicList({ page: pageParam })).data,
    initialPageParam: 1,
    getNextPageParam: (last) => (last.pagination.next ? last.pagination.page + 1 : undefined),
  });
  const items = query.data?.pages.flatMap((p) => p.results) ?? [];
  const total = query.data?.pages[0]?.pagination.count ?? 0;

  return (
    <>
      <section className="relative overflow-hidden border-b border-slate-200/70 bg-white">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,var(--color-brand-100),transparent_55%)]" aria-hidden />
        <div className="relative mx-auto grid max-w-6xl items-center gap-10 px-4 py-14 sm:px-6 lg:grid-cols-[1.2fr_1fr] lg:py-20">
          <div>
            <span className="chip bg-accent-400/20 text-amber-800">From Screen Time to Life Time</span>
            <h1 className="mt-4 text-4xl leading-[1.1] font-bold sm:text-5xl">
              Find your next activity.<br />
              <span className="text-brand-700">Turn it into an achievement.</span>
            </h1>
            <p className="mt-5 max-w-xl text-lg text-slate-600">
              DEAS brings together workshops, competitions, volunteering and events with a social space to share what you do and a portfolio that proves it.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/register"><Button size="lg" icon={<ArrowRight className="h-4 w-4" />}>Create a free account</Button></Link>
              <a href="#announcements"><Button size="lg" variant="outline">Browse announcements</Button></a>
            </div>
          </div>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
            {[
              { icon: Megaphone, title: "Discover", text: "Events and opportunities shared by the community." },
              { icon: Users, title: "Connect", text: "Friends, posts, comments and messages." },
              { icon: Award, title: "Showcase", text: "A verified achievement portfolio for your future." },
            ].map(({ icon: Icon, title, text }) => (
              <li key={title} className="card flex items-start gap-4 p-4">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700"><Icon className="h-5 w-5" /></span>
                <span><span className="block font-semibold text-slate-900">{title}</span><span className="text-sm text-slate-600">{text}</span></span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section id="announcements" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-12 sm:px-6">
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold">Latest announcements</h2>
            <p className="mt-1 text-sm text-slate-500">{total ? `${total} public opportunit${total === 1 ? "y" : "ies"}` : "Public opportunities from the DEAS community"}</p>
          </div>
          <Link to="/login?next=%2Fannouncements" className="flex items-center gap-2 rounded-xl border border-dashed border-slate-300 bg-white px-3.5 py-2 text-sm text-slate-500 transition hover:border-brand-400 hover:text-brand-700">
            <Search className="h-4 w-4" /> Log in to search and filter by category <Lock className="h-3.5 w-3.5" />
          </Link>
        </div>

        {query.isPending ? (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{Array.from({ length: 6 }).map((_, i) => <AnnouncementCardSkeleton key={i} />)}</div>
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => void query.refetch()} title="Could not load announcements" />
        ) : items.length === 0 ? (
          <EmptyState icon={<Megaphone className="h-6 w-6" />} title="No public announcements yet" description="Be the first to share an opportunity with the community." action={<Link to="/register"><Button>Create an account</Button></Link>} />
        ) : (
          <>
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((a) => (
                <AnnouncementCard key={a.id} announcement={a} onOpen={() => navigate(`/announcements/${a.id}`)} />
              ))}
            </div>
            <LoadMore hasMore={!!query.hasNextPage} loading={query.isFetchingNextPage} onLoad={() => void query.fetchNextPage()} />
          </>
        )}
      </section>
    </>
  );
}
