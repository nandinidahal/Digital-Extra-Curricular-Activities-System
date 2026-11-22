import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Award, Ban, BookOpen, Briefcase, Code2, ExternalLink, Globe, GraduationCap, Link2, Lock, MapPin,
  MessageCircle, Newspaper, Pencil, Settings, Sparkles, Star, UserRound, Users,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { AchievementCard } from "@/components/achievements/AchievementCard";
import { Avatar } from "@/components/common/Avatar";
import { Button } from "@/components/common/Button";
import { CardSkeleton, EmptyState, ErrorState, PageLoader } from "@/components/common/Feedback";
import { LoadMore } from "@/components/common/LoadMore";
import { Menu } from "@/components/common/Menu";
import { useConfirm } from "@/components/common/Modal";
import { Tabs } from "@/components/common/Tabs";
import { FriendButton } from "@/components/friends/FriendButton";
import { PostCard } from "@/components/social/PostCard";
import { useAuth } from "@/contexts/AuthContext";
import { qk } from "@/hooks/queryKeys";
import { achievementsApi } from "@/services/api/achievements";
import { errorMessage, toApiError } from "@/services/api/errors";
import { friendsApi } from "@/services/api/friends";
import { messagingApi } from "@/services/api/messaging";
import { profilesApi } from "@/services/api/profiles";
import { socialApi } from "@/services/api/social";
import type { FriendCard, Paginated, Profile } from "@/types/api";
import { formatDate } from "@/utils/format";
import { educationLabels } from "@/utils/labels";

type Tab = "posts" | "about" | "friends" | "achievements";

function paged<T>(fetcher: (page: number) => Promise<{ data: Paginated<T> }>) {
  return {
    queryFn: async ({ pageParam }: { pageParam: number }) => (await fetcher(pageParam)).data,
    initialPageParam: 1,
    getNextPageParam: (last: Paginated<T>) => (last.pagination.next ? last.pagination.page + 1 : undefined),
  };
}

function PostsTab({ userId, own }: { userId: string; own: boolean }) {
  const query = useInfiniteQuery({ queryKey: qk.userPosts(own ? "me" : userId), ...paged((page) => (own ? socialApi.myPosts(page) : socialApi.userPosts(userId, page))) });
  const posts = query.data?.pages.flatMap((p) => p.results) ?? [];
  if (query.isPending) return <CardSkeleton media />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  if (!posts.length) return <EmptyState icon={<Newspaper className="h-6 w-6" />} title="No posts to show" description={own ? "Share your first activity from the home feed." : "Nothing here that you can see."} />;
  return (
    <div className="space-y-4">
      {posts.map((p) => <PostCard key={p.id} post={p} />)}
      <LoadMore hasMore={!!query.hasNextPage} loading={query.isFetchingNextPage} onLoad={() => void query.fetchNextPage()} />
    </div>
  );
}

function AchievementsTab({ userId, own }: { userId: string; own: boolean }) {
  const query = useInfiniteQuery({ queryKey: ["achievements", "user", userId], ...paged((page) => achievementsApi.ofUser(userId, page)) });
  const items = query.data?.pages.flatMap((p) => p.results) ?? [];
  if (query.isPending) return <CardSkeleton />;
  if (query.isError) return <ErrorState error={query.error} />;
  return (
    <div className="space-y-4">
      {own && <p className="text-sm text-slate-500">Others see your <strong>verified</strong> achievements here, according to each one's visibility. <Link to="/achievements" className="font-medium text-brand-700 hover:underline">Manage your portfolio</Link></p>}
      {!items.length ? <EmptyState icon={<Award className="h-6 w-6" />} title="No verified achievements yet" /> : (
        <div className="grid gap-4 sm:grid-cols-2">{items.map((a) => <AchievementCard key={a.id} achievement={a} />)}</div>
      )}
      <LoadMore hasMore={!!query.hasNextPage} loading={query.isFetchingNextPage} onLoad={() => void query.fetchNextPage()} />
    </div>
  );
}

function FriendsTab({ userId, own }: { userId: string; own: boolean }) {
  const query = useInfiniteQuery({
    queryKey: own ? ["friends", "list"] : ["friends", "mutual", userId],
    ...paged<FriendCard>((page) => (own ? friendsApi.list(page) : friendsApi.mutual(userId, page))),
  });
  const people = query.data?.pages.flatMap((p) => p.results) ?? [];
  if (query.isPending) return <CardSkeleton lines={1} />;
  if (query.isError) return <ErrorState error={query.error} title={toApiError(query.error).status === 403 ? "Friends are hidden on private profiles" : "Could not load friends"} />;
  return (
    <div className="card p-5">
      <h3 className="mb-4 font-semibold">{own ? "Your friends" : "Mutual friends"} <span className="text-slate-400">({query.data?.pages[0]?.pagination.count ?? 0})</span></h3>
      {!own && <p className="-mt-3 mb-4 text-xs text-slate-500">DEAS only shows friends you have in common.</p>}
      {!people.length ? <p className="text-sm text-slate-500">{own ? "No friends yet." : "No mutual friends."}</p> : (
        <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {people.map((f) => (
            <li key={f.user_id}>
              <Link to={`/profile/${f.user_id}`} className="flex flex-col items-center rounded-xl p-3 text-center hover:bg-slate-50">
                <Avatar src={f.profile_picture} name={f.full_name} size="lg" />
                <span className="mt-2 line-clamp-1 text-sm font-medium text-slate-800">{f.full_name}</span>
                <span className="line-clamp-1 text-xs text-slate-500">@{f.username}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={!!query.hasNextPage} loading={query.isFetchingNextPage} onLoad={() => void query.fetchNextPage()} />
    </div>
  );
}

function AboutRow({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="flex gap-3 py-2.5">
      <span className="mt-0.5 text-slate-400">{icon}</span>
      <div className="min-w-0"><p className="text-xs text-slate-500">{label}</p><div className="text-sm break-words text-slate-800">{children}</div></div>
    </div>
  );
}

function AboutTab({ profile, own }: { profile: Profile; own: boolean }) {
  const links = [
    { url: profile.website, icon: <Globe className="h-4 w-4" />, label: "Website" },
    { url: profile.portfolio_url, icon: <Briefcase className="h-4 w-4" />, label: "Portfolio" },
    { url: profile.linkedin_url, icon: <Link2 className="h-4 w-4" />, label: "LinkedIn" },
    { url: profile.github_url, icon: <Code2 className="h-4 w-4" />, label: "GitHub" },
  ].filter((l) => l.url);
  const empty = !profile.bio && !profile.institution && !profile.education_level && !profile.location && !profile.interests?.length && !profile.skills?.length && !links.length;
  if (empty) return <EmptyState icon={<UserRound className="h-6 w-6" />} title="Nothing here yet" description={own ? "Add a bio, education and skills from Edit profile." : "This person hasn't shared details, or keeps them private."} action={own ? <Link to="/profile/edit"><Button size="sm">Edit profile</Button></Link> : undefined} />;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="card p-5">
        <h3 className="mb-2 font-semibold">About</h3>
        {profile.bio && <p className="prose-plain mb-2 text-sm leading-relaxed text-slate-700">{profile.bio}</p>}
        <div className="divide-y divide-slate-100">
          {profile.institution && <AboutRow icon={<BookOpen className="h-4 w-4" />} label="Institution">{profile.institution}</AboutRow>}
          {profile.education_level && <AboutRow icon={<GraduationCap className="h-4 w-4" />} label="Education">{educationLabels[profile.education_level]}{profile.field_of_study ? ` · ${profile.field_of_study}` : ""}</AboutRow>}
          {profile.location && <AboutRow icon={<MapPin className="h-4 w-4" />} label="Location">{profile.location}</AboutRow>}
          <AboutRow icon={<Users className="h-4 w-4" />} label="Member since">{formatDate(profile.date_created)}</AboutRow>
        </div>
      </div>
      <div className="space-y-4">
        {!!profile.skills?.length && (
          <div className="card p-5"><h3 className="mb-3 flex items-center gap-2 font-semibold"><Code2 className="h-4 w-4" /> Skills</h3><div className="flex flex-wrap gap-1.5">{profile.skills.map((s) => <span key={s} className="chip bg-brand-50 text-brand-800">{s}</span>)}</div></div>
        )}
        {!!profile.interests?.length && (
          <div className="card p-5"><h3 className="mb-3 flex items-center gap-2 font-semibold"><Sparkles className="h-4 w-4" /> Interests</h3><div className="flex flex-wrap gap-1.5">{profile.interests.map((s) => <span key={s} className="chip bg-amber-50 text-amber-800">{s}</span>)}</div></div>
        )}
        {links.length > 0 && (
          <div className="card p-5">
            <h3 className="mb-2 font-semibold">Links</h3>
            {links.map((l) => (
              <a key={l.label} href={l.url} target="_blank" rel="noopener noreferrer nofollow" className="flex items-center gap-3 rounded-lg py-2 text-sm text-brand-700 hover:underline">{l.icon}{l.label}<ExternalLink className="h-3.5 w-3.5" /></a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ProfilePage() {
  const params = useParams();
  const { user, profile: ownProfile } = useAuth();
  const navigate = useNavigate();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("posts");
  const userId = params.userId ?? user!.id;
  const own = userId === user!.id;

  const profileQuery = useQuery({
    queryKey: qk.profile(userId),
    queryFn: async () => (own ? (await profilesApi.me()).data.profile : (await profilesApi.get(userId)).data.profile),
  });
  const relationship = useQuery({ queryKey: qk.relationship(userId), queryFn: async () => (await friendsApi.status(userId)).data, enabled: !own });
  const friendCount = useQuery({ queryKey: qk.friendCount, queryFn: async () => (await friendsApi.count()).data.friend_count, enabled: own });
  const featured = useQuery({ queryKey: ["achievements", "featured", userId], queryFn: async () => (await achievementsApi.featured(userId)).data.results });

  if (params.userId && params.userId === user!.id) return <Navigate to="/profile" replace />;
  if (profileQuery.isPending) return <PageLoader />;

  const error = profileQuery.isError ? toApiError(profileQuery.error) : null;
  if (error && error.status !== 403) {
    return <div className="mx-auto max-w-xl py-10"><ErrorState error={profileQuery.error} title={error.status === 404 ? "Profile not found" : "Could not load this profile"} /></div>;
  }
  const isPrivate = error?.status === 403;
  const profile = (own ? ownProfile ?? profileQuery.data : profileQuery.data) as Profile | undefined;
  const rel = relationship.data;
  const name = profile?.full_name ?? "This user";

  const message = async () => {
    try {
      const r = await messagingApi.start(userId);
      navigate(`/messages/${r.data.id}`);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  const block = async () => {
    if (!(await confirm({ title: `Block ${name}?`, description: "You'll be removed from each other's friends, pending requests are cancelled, and neither of you can message or see the other's content.", confirmLabel: "Block" }))) return;
    try {
      const r = await friendsApi.block(userId);
      toast.success(r.message);
      void queryClient.invalidateQueries({ queryKey: ["friends"] });
      void relationship.refetch();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  return (
    <div className="mx-auto max-w-4xl">
      <div className="card overflow-hidden">
        <div className="relative h-40 bg-gradient-to-r from-brand-800 via-brand-700 to-brand-500 sm:h-56">
          {profile?.cover_photo && <img src={profile.cover_photo} alt="" className="h-full w-full object-cover" />}
        </div>
        <div className="px-5 pb-5 sm:px-8">
          <div className="-mt-14 flex flex-col gap-4 sm:-mt-16 sm:flex-row sm:items-end sm:justify-between">
            <Avatar src={profile?.profile_picture} name={name} size="xl" className="rounded-full ring-4 ring-white" />
            <div className="flex flex-wrap gap-2 sm:pb-2">
              {own ? (
                <>
                  <Link to="/profile/edit"><Button icon={<Pencil className="h-4 w-4" />}>Edit profile</Button></Link>
                  <Link to="/settings/privacy"><Button variant="outline" icon={<Settings className="h-4 w-4" />}>Privacy</Button></Link>
                </>
              ) : rel && (
                <>
                  <FriendButton userId={userId} name={name} status={rel.friendship_status} requestId={rel.request_id} onChange={() => void relationship.refetch()} />
                  {!rel.blocked && <Button variant="outline" onClick={message} icon={<MessageCircle className="h-4 w-4" />}>Message</Button>}
                  {rel.friendship_status !== "blocked_by_me" && rel.friendship_status !== "blocked_you" && (
                    <Menu label="More profile actions" items={[{ label: "Block", icon: <Ban className="h-4 w-4" />, onSelect: block, danger: true }]} />
                  )}
                </>
              )}
            </div>
          </div>
          <div className="mt-4">
            <h1 className="text-2xl font-bold">{isPrivate ? "Private profile" : name}</h1>
            {profile && <p className="text-sm text-slate-500">@{profile.username}</p>}
            {profile?.headline && <p className="mt-2 text-[15px] text-slate-700">{profile.headline}</p>}
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-500">
              {profile?.location && <span className="inline-flex items-center gap-1.5"><MapPin className="h-4 w-4" />{profile.location}</span>}
              {profile?.institution && <span className="inline-flex items-center gap-1.5"><BookOpen className="h-4 w-4" />{profile.institution}</span>}
              {own && <Link to="/friends" className="inline-flex items-center gap-1.5 hover:text-brand-700"><Users className="h-4 w-4" /><strong className="text-slate-800">{friendCount.data ?? "–"}</strong> friends</Link>}
              {rel?.is_friend && <span className="inline-flex items-center gap-1.5 text-brand-700"><Users className="h-4 w-4" /> You are friends</span>}
            </div>
            {own && "privacy" in (profile ?? {}) && (profile as { privacy: { profile_visibility: string } }).privacy.profile_visibility !== "public" && (
              <p className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600"><Lock className="h-3.5 w-3.5" />Your profile is {(profile as { privacy: { profile_visibility: string } }).privacy.profile_visibility === "private" ? "private" : "visible to members only"}</p>
            )}
          </div>
        </div>
      </div>

      {isPrivate ? (
        <div className="mt-6 space-y-6">
          <EmptyState icon={<Lock className="h-6 w-6" />} title="This profile is private" description="Its owner only shares profile details with themselves. Posts and achievements they made visible to you still appear below." />
          <PostsTab userId={userId} own={false} />
        </div>
      ) : profile && (
        <>
          {featured.data && featured.data.length > 0 && (
            <section className="mt-6">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700"><Star className="h-4 w-4 text-amber-500" /> Featured achievements</h2>
              <div className="scroll-thin flex snap-x gap-4 overflow-x-auto pb-2">
                {featured.data.map((a) => <div key={a.id} className="w-72 shrink-0 snap-start"><AchievementCard achievement={a} /></div>)}
              </div>
            </section>
          )}
          <Tabs<Tab>
            className="mt-6 mb-5"
            value={tab}
            onChange={setTab}
            items={[
              { value: "posts", label: <><Newspaper className="h-4 w-4" /> Posts</> },
              { value: "about", label: <><UserRound className="h-4 w-4" /> About</> },
              { value: "friends", label: <><Users className="h-4 w-4" /> Friends</> },
              { value: "achievements", label: <><Award className="h-4 w-4" /> Achievements</> },
            ]}
          />
          {tab === "posts" && <PostsTab userId={userId} own={own} />}
          {tab === "about" && <AboutTab profile={profile} own={own} />}
          {tab === "friends" && <FriendsTab userId={userId} own={own} />}
          {tab === "achievements" && <AchievementsTab userId={userId} own={own} />}
        </>
      )}
    </div>
  );
}
