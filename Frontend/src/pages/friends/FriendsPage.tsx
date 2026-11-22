import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, Check, Clock, MessageCircle, Search, UserMinus, UserPlus, Users, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Avatar } from "@/components/common/Avatar";
import { Button } from "@/components/common/Button";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/common/Feedback";
import { LoadMore } from "@/components/common/LoadMore";
import { useConfirm } from "@/components/common/Modal";
import { PageHeader } from "@/components/common/PageHeader";
import { LinkTabs } from "@/components/common/Tabs";
import { FriendButton } from "@/components/friends/FriendButton";
import { errorMessage } from "@/services/api/errors";
import { friendsApi } from "@/services/api/friends";
import { messagingApi } from "@/services/api/messaging";
import type { FriendCard, Paginated } from "@/types/api";
import { timeAgo } from "@/utils/format";

function usePaged<T>(key: readonly unknown[], fetcher: (page: number) => Promise<{ data: Paginated<T> }>, enabled = true) {
  return useInfiniteQuery({
    queryKey: key,
    queryFn: async ({ pageParam }) => (await fetcher(pageParam)).data,
    initialPageParam: 1,
    getNextPageParam: (last) => (last.pagination.next ? last.pagination.page + 1 : undefined),
    enabled,
  });
}

function PersonRow({ person, subtitle, actions }: { person: FriendCard; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <li className="card flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
      <Link to={`/profile/${person.user_id}`} className="flex min-w-0 flex-1 items-center gap-3">
        <Avatar src={person.profile_picture} name={person.full_name} size="md" />
        <span className="min-w-0">
          <span className="block truncate font-semibold text-slate-900 hover:underline">{person.full_name}</span>
          <span className="block truncate text-sm text-slate-500">{subtitle ?? (person.headline || `@${person.username}`)}</span>
        </span>
      </Link>
      {actions && <div className="flex flex-wrap gap-2 sm:justify-end">{actions}</div>}
    </li>
  );
}

function ListState({ query, empty, children }: { query: { isPending: boolean; isError: boolean; error: unknown; refetch: () => unknown }; empty: boolean; children: ReactNode; }) {
  if (query.isPending) return <div className="space-y-3"><CardSkeleton lines={1} /><CardSkeleton lines={1} /></div>;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  if (empty) return null;
  return <>{children}</>;
}

function FriendsTab() {
  const navigate = useNavigate();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState("");
  const query = usePaged(["friends", "list"], friendsApi.list);
  const friends = query.data?.pages.flatMap((p) => p.results) ?? [];
  const total = query.data?.pages[0]?.pagination.count ?? 0;
  const needle = filter.trim().toLowerCase();
  const visible = needle ? friends.filter((f) => `${f.full_name} ${f.username}`.toLowerCase().includes(needle)) : friends;

  const message = async (userId: string) => {
    try {
      const r = await messagingApi.start(userId);
      navigate(`/messages/${r.data.id}`);
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };
  const remove = async (f: FriendCard) => {
    if (!(await confirm({ title: `Remove ${f.full_name}?`, description: "You will no longer be friends. You can send a new request later.", confirmLabel: "Remove friend" }))) return;
    try {
      await friendsApi.remove(f.user_id);
      toast.success("Friend removed.");
      void queryClient.invalidateQueries({ queryKey: ["friends"] });
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  return (
    <>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-500">{total} friend{total === 1 ? "" : "s"}</p>
        <div className="relative sm:w-72">
          <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <label htmlFor="friend-filter" className="sr-only">Search friends</label>
          <input id="friend-filter" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Search your friends" className="input h-10 pl-9" />
        </div>
      </div>
      <ListState query={query} empty={false}>
        {friends.length === 0 ? (
          <EmptyState icon={<Users className="h-6 w-6" />} title="No friends yet" description="Find people on DEAS and send them a friend request." action={<Link to="/friends/discover"><Button icon={<UserPlus className="h-4 w-4" />}>Find people</Button></Link>} />
        ) : visible.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-500">No loaded friends match “{filter}”.{query.hasNextPage ? " Load more to search further." : ""}</p>
        ) : (
          <ul className="grid gap-3 md:grid-cols-2">
            {visible.map((f) => (
              <PersonRow key={f.user_id} person={f} subtitle={`Friends since ${timeAgo(f.friendship_created_at)}`} actions={
                <>
                  <Button size="sm" variant="subtle" onClick={() => message(f.user_id)} icon={<MessageCircle className="h-4 w-4" />}>Message</Button>
                  <Button size="sm" variant="ghost" onClick={() => remove(f)} icon={<UserMinus className="h-4 w-4" />} aria-label={`Remove ${f.full_name}`}>Remove</Button>
                </>
              } />
            ))}
          </ul>
        )}
        <LoadMore hasMore={!!query.hasNextPage} loading={query.isFetchingNextPage} onLoad={() => void query.fetchNextPage()} />
      </ListState>
    </>
  );
}

function RequestsTab() {
  const queryClient = useQueryClient();
  const received = usePaged(["friends", "received"], friendsApi.received);
  const sent = usePaged(["friends", "sent"], friendsApi.sent);
  const [busy, setBusy] = useState<string | null>(null);
  const act = async (id: string, action: () => Promise<{ message: string }>) => {
    setBusy(id);
    try {
      const r = await action();
      toast.success(r.message);
      await queryClient.invalidateQueries({ queryKey: ["friends"] });
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(null);
    }
  };
  const receivedItems = received.data?.pages.flatMap((p) => p.results) ?? [];
  const sentItems = sent.data?.pages.flatMap((p) => p.results) ?? [];
  return (
    <div className="grid gap-8 lg:grid-cols-2">
      <section>
        <h2 className="mb-3 font-semibold">Received <span className="text-slate-400">({received.data?.pages[0]?.pagination.count ?? 0})</span></h2>
        <ListState query={received} empty={false}>
          {receivedItems.length === 0 ? <EmptyState title="No pending requests" description="When someone wants to connect, you'll see it here." /> : (
            <ul className="space-y-3">
              {receivedItems.map((r) => r.sender && (
                <PersonRow key={r.id} person={r.sender} subtitle={`Sent ${timeAgo(r.created_at)}`} actions={
                  <>
                    <Button size="sm" loading={busy === r.id} onClick={() => act(r.id, () => friendsApi.accept(r.id))} icon={<Check className="h-4 w-4" />}>Accept</Button>
                    <Button size="sm" variant="outline" disabled={busy === r.id} onClick={() => act(r.id, () => friendsApi.reject(r.id))} icon={<X className="h-4 w-4" />}>Reject</Button>
                  </>
                } />
              ))}
            </ul>
          )}
          <LoadMore hasMore={!!received.hasNextPage} loading={received.isFetchingNextPage} onLoad={() => void received.fetchNextPage()} />
        </ListState>
      </section>
      <section>
        <h2 className="mb-3 font-semibold">Sent <span className="text-slate-400">({sent.data?.pages[0]?.pagination.count ?? 0})</span></h2>
        <ListState query={sent} empty={false}>
          {sentItems.length === 0 ? <EmptyState title="No sent requests" description="Requests you send stay here until they're answered." /> : (
            <ul className="space-y-3">
              {sentItems.map((r) => r.receiver && (
                <PersonRow key={r.id} person={r.receiver} subtitle={<span className="inline-flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> Pending · {timeAgo(r.created_at)}</span>} actions={
                  <Button size="sm" variant="outline" loading={busy === r.id} onClick={() => act(r.id, () => friendsApi.cancel(r.id))}>Cancel request</Button>
                } />
              ))}
            </ul>
          )}
          <LoadMore hasMore={!!sent.hasNextPage} loading={sent.isFetchingNextPage} onLoad={() => void sent.fetchNextPage()} />
        </ListState>
      </section>
    </div>
  );
}

function DiscoverTab() {
  const query = usePaged(["friends", "discover"], friendsApi.discover);
  const people = query.data?.pages.flatMap((p) => p.results) ?? [];
  return (
    <>
      <p className="mb-4 text-sm text-slate-500">Everyone on DEAS, alphabetically. (The backend does not offer people search yet.)</p>
      <ListState query={query} empty={false}>
        {people.length === 0 ? <EmptyState title="Nobody to show" /> : (
          <ul className="grid gap-3 md:grid-cols-2">
            {people.map((p) => (
              <PersonRow key={p.user_id} person={p} actions={<FriendButton userId={p.user_id} name={p.full_name} status={p.friendship_status} size="sm" onChange={() => void query.refetch()} />} />
            ))}
          </ul>
        )}
        <LoadMore hasMore={!!query.hasNextPage} loading={query.isFetchingNextPage} onLoad={() => void query.fetchNextPage()} />
      </ListState>
    </>
  );
}

function BlockedTab() {
  const queryClient = useQueryClient();
  const query = usePaged(["friends", "blocked"], friendsApi.blocked);
  const people = query.data?.pages.flatMap((p) => p.results) ?? [];
  const unblock = async (userId: string) => {
    try {
      const r = await friendsApi.unblock(userId);
      toast.success(r.message);
      void queryClient.invalidateQueries({ queryKey: ["friends"] });
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };
  return (
    <ListState query={query} empty={false}>
      {people.length === 0 ? <EmptyState icon={<Ban className="h-6 w-6" />} title="You haven't blocked anyone" description="Blocked people can't message you, see your posts or send you requests." /> : (
        <ul className="grid gap-3 md:grid-cols-2">
          {people.map((p) => <PersonRow key={p.user_id} person={p} subtitle={`Blocked ${timeAgo(p.blocked_at)}`} actions={<Button size="sm" variant="outline" onClick={() => unblock(p.user_id)}>Unblock</Button>} />)}
        </ul>
      )}
      <LoadMore hasMore={!!query.hasNextPage} loading={query.isFetchingNextPage} onLoad={() => void query.fetchNextPage()} />
    </ListState>
  );
}

export default function FriendsPage() {
  const { tab } = useParams();
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader icon={<Users className="h-5 w-5" />} title="Friends" description="Your connections, requests and people to meet." />
      <LinkTabs
        className="mb-6"
        items={[
          { to: "/friends", label: "Friends", end: true },
          { to: "/friends/requests", label: "Requests" },
          { to: "/friends/discover", label: "Find people" },
          { to: "/friends/blocked", label: "Blocked" },
        ]}
      />
      {tab === "requests" ? <RequestsTab /> : tab === "discover" ? <DiscoverTab /> : tab === "blocked" ? <BlockedTab /> : <FriendsTab />}
    </div>
  );
}
