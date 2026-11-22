import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Award, CalendarDays, Megaphone, Newspaper, Sparkles, UserRound, Users } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Avatar } from "@/components/common/Avatar";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/common/Feedback";
import { LoadMore } from "@/components/common/LoadMore";
import { Tabs } from "@/components/common/Tabs";
import { FriendButton } from "@/components/friends/FriendButton";
import { PostCard } from "@/components/social/PostCard";
import { PostComposer } from "@/components/social/PostComposer";
import { useAuth } from "@/contexts/AuthContext";
import { qk } from "@/hooks/queryKeys";
import { announcementsApi } from "@/services/api/announcements";
import { friendsApi } from "@/services/api/friends";
import { socialApi } from "@/services/api/social";
import { formatDay, formatMonth } from "@/utils/format";

type Scope = "all" | "friends" | "shares";

function ProfileSidebar() {
  const { user, profile } = useAuth();
  const friendCount = useQuery({ queryKey: qk.friendCount, queryFn: async () => (await friendsApi.count()).data.friend_count });
  const completion = profile?.profile_completion.percentage ?? 0;
  const links = [
    { to: "/announcements", icon: Megaphone, label: "Announcements" },
    { to: "/achievements", icon: Award, label: "My achievements" },
    { to: "/friends", icon: Users, label: "Friends" },
    { to: "/profile", icon: UserRound, label: "My profile" },
  ];
  return (
    <aside className="hidden space-y-4 lg:block">
      <div className="card overflow-hidden">
        <div className="h-16 bg-gradient-to-r from-brand-700 to-brand-500">
          {profile?.cover_photo && <img src={profile.cover_photo} alt="" className="h-full w-full object-cover" />}
        </div>
        <div className="-mt-8 px-4 pb-4 text-center">
          <Link to="/profile"><Avatar src={profile?.profile_picture} name={user?.full_name} size="lg" className="mx-auto" /></Link>
          <p className="mt-2 font-semibold text-slate-900">{user?.full_name}</p>
          <p className="text-xs text-slate-500">{profile?.headline || `@${user?.username}`}</p>
          <div className="mt-3 flex justify-center gap-6 border-t border-slate-100 pt-3 text-sm">
            <Link to="/friends" className="hover:text-brand-700"><span className="block font-semibold text-slate-900">{friendCount.data ?? "–"}</span><span className="text-xs text-slate-500">Friends</span></Link>
          </div>
          {completion < 100 && (
            <Link to="/profile/edit" className="mt-3 block rounded-xl bg-brand-50 p-3 text-left text-xs text-brand-900 hover:bg-brand-100">
              <span className="flex justify-between font-semibold"><span>Complete your profile</span><span>{completion}%</span></span>
              <span className="mt-2 block h-1.5 overflow-hidden rounded-full bg-white"><span className="block h-full rounded-full bg-brand-600" style={{ width: `${completion}%` }} /></span>
            </Link>
          )}
        </div>
      </div>
      <nav className="card p-2" aria-label="Shortcuts">
        {links.map(({ to, icon: Icon, label }) => (
          <Link key={to} to={to} className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50">
            <Icon className="h-[18px] w-[18px] text-brand-700" /> {label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}

function RightSidebar() {
  const upcoming = useQuery({
    queryKey: ["announcements", "upcoming-widget"],
    queryFn: async () => (await announcementsApi.list({ when: "upcoming", ordering: "start" })).data.results.slice(0, 4),
  });
  const discover = useQuery({
    queryKey: ["friends", "discover", "widget"],
    queryFn: async () => (await friendsApi.discover(1)).data.results.filter((u) => u.friendship_status === "not_friends").slice(0, 4),
  });
  return (
    <aside className="hidden space-y-4 xl:block">
      <section className="card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Upcoming events</h2>
          <Link to="/announcements" className="text-xs font-medium text-brand-700 hover:underline">See all</Link>
        </div>
        {upcoming.data?.length ? (
          <ul className="space-y-3">
            {upcoming.data.map((a) => (
              <li key={a.id}>
                <Link to={`/announcements/${a.id}`} className="flex gap-3 rounded-lg hover:bg-slate-50">
                  <span className="flex w-11 shrink-0 flex-col items-center rounded-lg bg-brand-50 py-1">
                    <span className="text-[10px] font-semibold text-brand-700 uppercase">{formatMonth(a.start_datetime)}</span>
                    <span className="text-base leading-none font-bold text-brand-900">{formatDay(a.start_datetime)}</span>
                  </span>
                  <span className="min-w-0">
                    <span className="line-clamp-2 text-sm font-medium text-slate-800">{a.title}</span>
                    <span className="text-xs text-slate-500">{a.category?.name}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="flex items-center gap-2 text-sm text-slate-500"><CalendarDays className="h-4 w-4" /> No upcoming events yet.</p>
        )}
      </section>
      <section className="card p-4">
        <h2 className="mb-3 text-sm font-semibold">People on DEAS</h2>
        {discover.data?.length ? (
          <ul className="space-y-3">
            {discover.data.map((u) => (
              <li key={u.user_id} className="flex items-center gap-3">
                <Link to={`/profile/${u.user_id}`}><Avatar src={u.profile_picture} name={u.full_name} size="sm" /></Link>
                <Link to={`/profile/${u.user_id}`} className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-slate-800">{u.full_name}</span>
                  <span className="block truncate text-xs text-slate-500">{u.headline || `@${u.username}`}</span>
                </Link>
                <FriendButton userId={u.user_id} name={u.full_name} status={u.friendship_status} size="sm" onChange={() => void discover.refetch()} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">You are connected with everyone we know of. Nice!</p>
        )}
        <Link to="/friends/discover" className="mt-3 block text-xs font-medium text-brand-700 hover:underline">Find more people</Link>
      </section>
    </aside>
  );
}

export default function HomePage() {
  const [scope, setScope] = useState<Scope>("all");
  const feed = useInfiniteQuery({
    queryKey: qk.feed(scope, ""),
    queryFn: async ({ pageParam }) => (await socialApi.feed({ page: pageParam, scope: scope === "friends" ? "friends" : "all" })).data,
    initialPageParam: 1,
    getNextPageParam: (last) => (last.pagination.next ? last.pagination.page + 1 : undefined),
    enabled: scope !== "shares",
  });
  const shares = useInfiniteQuery({
    queryKey: ["social", "my-shares"],
    queryFn: async ({ pageParam }) => (await socialApi.myShares(pageParam)).data,
    initialPageParam: 1,
    getNextPageParam: (last) => (last.pagination.next ? last.pagination.page + 1 : undefined),
    enabled: scope === "shares",
  });
  const posts = feed.data?.pages.flatMap((p) => p.results) ?? [];
  const shareItems = shares.data?.pages.flatMap((p) => p.results) ?? [];

  return (
    <div className="grid gap-6 lg:grid-cols-[17rem_minmax(0,1fr)] xl:grid-cols-[17rem_minmax(0,1fr)_19rem]">
      <ProfileSidebar />
      <div className="mx-auto w-full max-w-2xl space-y-4">
        <PostComposer />
        <Tabs<Scope>
          value={scope}
          onChange={setScope}
          items={[
            { value: "all", label: <><Sparkles className="h-4 w-4" /> For you</> },
            { value: "friends", label: <><Users className="h-4 w-4" /> Friends</> },
            { value: "shares", label: <><Newspaper className="h-4 w-4" /> My shares</> },
          ]}
        />
        {scope === "shares" ? (
          shares.isPending ? <CardSkeleton /> : shares.isError ? <ErrorState error={shares.error} onRetry={() => void shares.refetch()} /> : shareItems.length === 0 ? (
            <EmptyState title="You haven't shared any posts" description="Use Share on a post to keep it in your shares." />
          ) : (
            <>
              {shareItems.map((s) => (
                <div key={s.id} className="space-y-2">
                  {s.caption && <p className="px-1 text-sm text-slate-600">“{s.caption}”</p>}
                  {s.original_post ? <PostCard post={s.original_post} /> : <div className="card p-5 text-sm text-slate-500">The original post is no longer available.</div>}
                </div>
              ))}
              <LoadMore hasMore={!!shares.hasNextPage} loading={shares.isFetchingNextPage} onLoad={() => void shares.fetchNextPage()} />
            </>
          )
        ) : feed.isPending ? (
          <><CardSkeleton media /><CardSkeleton /></>
        ) : feed.isError ? (
          <ErrorState error={feed.error} onRetry={() => void feed.refetch()} title="Could not load your feed" />
        ) : posts.length === 0 ? (
          <EmptyState
            icon={<Newspaper className="h-6 w-6" />}
            title={scope === "friends" ? "Nothing from your friends yet" : "Your feed is empty"}
            description={scope === "friends" ? "Add friends to see their activities here." : "Share your first activity or explore announcements to get started."}
            action={<Link to={scope === "friends" ? "/friends/discover" : "/announcements"} className="text-sm font-semibold text-brand-700 hover:underline">{scope === "friends" ? "Find people" : "Explore announcements"}</Link>}
          />
        ) : (
          <>
            {posts.map((post) => <PostCard key={post.id} post={post} />)}
            <LoadMore hasMore={!!feed.hasNextPage} loading={feed.isFetchingNextPage} onLoad={() => void feed.fetchNextPage()} />
          </>
        )}
      </div>
      <RightSidebar />
    </div>
  );
}
