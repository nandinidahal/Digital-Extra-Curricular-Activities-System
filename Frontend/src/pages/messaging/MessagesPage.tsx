import { useInfiniteQuery } from "@tanstack/react-query";
import { Archive, BellOff, Inbox, MessageCircle, PenSquare, Search } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Avatar } from "@/components/common/Avatar";
import { Button } from "@/components/common/Button";
import { CountBadge, EmptyState, ErrorState, Spinner } from "@/components/common/Feedback";
import { LoadMore } from "@/components/common/LoadMore";
import { Menu } from "@/components/common/Menu";
import { Modal } from "@/components/common/Modal";
import { ConversationView } from "@/components/messaging/ConversationView";
import { qk } from "@/hooks/queryKeys";
import { errorMessage } from "@/services/api/errors";
import { friendsApi } from "@/services/api/friends";
import { messagingApi } from "@/services/api/messaging";
import type { Conversation } from "@/types/api";
import { cn } from "@/utils/cn";
import { timeAgo } from "@/utils/format";

function preview(c: Conversation) {
  const m = c.last_message;
  if (!m) return "No messages yet";
  if (m.is_deleted) return "Message deleted";
  const body = m.content || (m.message_type === "image" ? "📷 Photo" : m.message_type === "file" ? "📎 File" : "");
  return `${m.is_own ? "You: " : ""}${body}`;
}

function NewMessageDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const friends = useInfiniteQuery({
    queryKey: ["friends", "list"],
    queryFn: async ({ pageParam }) => (await friendsApi.list(pageParam)).data,
    initialPageParam: 1,
    getNextPageParam: (last) => (last.pagination.next ? last.pagination.page + 1 : undefined),
    enabled: open,
  });
  const people = (friends.data?.pages.flatMap((p) => p.results) ?? []).filter((f) => `${f.full_name} ${f.username}`.toLowerCase().includes(filter.trim().toLowerCase()));
  const start = async (userId: string) => {
    setBusy(userId);
    try {
      const r = await messagingApi.start(userId);
      onClose();
      navigate(`/messages/${r.data.id}`);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(null);
    }
  };
  return (
    <Modal open={open} onClose={onClose} title="New message" description="Choose a friend. To message someone else, open their profile and use Message (up to 4 messages before you're friends).">
      <div className="relative mb-3">
        <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Search friends" aria-label="Search friends" className="input pl-9" />
      </div>
      {friends.isPending ? <Spinner /> : people.length === 0 ? <p className="py-6 text-center text-sm text-slate-500">No friends found.</p> : (
        <ul className="divide-y divide-slate-100">
          {people.map((f) => (
            <li key={f.user_id}>
              <button onClick={() => start(f.user_id)} disabled={!!busy} className="flex w-full items-center gap-3 rounded-lg px-2 py-2.5 text-left hover:bg-slate-50">
                <Avatar src={f.profile_picture} name={f.full_name} size="sm" />
                <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{f.full_name}</span><span className="block truncate text-xs text-slate-500">@{f.username}</span></span>
                {busy === f.user_id && <Spinner />}
              </button>
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={!!friends.hasNextPage} loading={friends.isFetchingNextPage} onLoad={() => void friends.fetchNextPage()} />
    </Modal>
  );
}

export default function MessagesPage() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const [archived, setArchived] = useState(false);
  const [filter, setFilter] = useState("");
  const [composing, setComposing] = useState(false);

  const list = useInfiniteQuery({
    queryKey: qk.conversations(archived),
    queryFn: async ({ pageParam }) => (await messagingApi.conversations(pageParam, archived)).data,
    initialPageParam: 1,
    getNextPageParam: (last) => (last.pagination.next ? last.pagination.page + 1 : undefined),
  });
  const conversations = (list.data?.pages.flatMap((p) => p.results) ?? []).filter((c) =>
    !filter.trim() || `${c.participant?.full_name ?? ""} ${c.participant?.username ?? ""}`.toLowerCase().includes(filter.trim().toLowerCase()),
  );

  const toggle = async (c: Conversation, action: "mute" | "archive") => {
    try {
      const r = action === "mute" ? await messagingApi.mute(c.id, !c.is_muted) : await messagingApi.archive(c.id, !c.is_archived);
      toast.success(r.message);
      void list.refetch();
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  return (
    <div className="card -mx-3 flex h-[calc(100dvh-9.5rem)] min-h-[28rem] overflow-hidden rounded-none sm:mx-0 sm:rounded-2xl lg:h-[calc(100dvh-7rem)]">
      <aside className={cn("flex w-full min-w-0 flex-col border-r border-slate-200 md:w-80 lg:w-96", conversationId && "hidden md:flex")}>
        <div className="space-y-3 border-b border-slate-200 p-4">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-semibold">{archived ? "Archived" : "Messages"}</h1>
            <div className="flex gap-1">
              <button onClick={() => setArchived((a) => !a)} className={cn("rounded-full p-2 hover:bg-slate-100", archived ? "text-brand-700" : "text-slate-500")} aria-pressed={archived} aria-label={archived ? "Show inbox" : "Show archived"}>
                {archived ? <Inbox className="h-5 w-5" /> : <Archive className="h-5 w-5" />}
              </button>
              <button onClick={() => setComposing(true)} className="rounded-full p-2 text-brand-700 hover:bg-brand-50" aria-label="New message"><PenSquare className="h-5 w-5" /></button>
            </div>
          </div>
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Search conversations" aria-label="Search conversations" className="input h-10 bg-slate-50 pl-9" />
          </div>
        </div>
        <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
          {list.isPending ? <div className="p-6"><Spinner /></div> : list.isError ? <div className="p-4"><ErrorState error={list.error} onRetry={() => void list.refetch()} /></div> : conversations.length === 0 ? (
            <div className="p-4">
              <EmptyState icon={<MessageCircle className="h-6 w-6" />} title={archived ? "No archived chats" : "No conversations yet"} description="Start one from a friend's card or profile." action={!archived ? <Button size="sm" onClick={() => setComposing(true)}>New message</Button> : undefined} />
            </div>
          ) : (
            <ul>
              {conversations.map((c) => (
                <li key={c.id} className={cn("group relative flex items-center border-b border-slate-100", c.id === conversationId ? "bg-brand-50" : "hover:bg-slate-50")}>
                  <button onClick={() => navigate(`/messages/${c.id}`)} className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 text-left">
                    <Avatar src={c.participant?.profile_picture} name={c.participant?.full_name ?? "Deleted account"} online={c.participant?.is_online} />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center justify-between gap-2">
                        <span className={cn("truncate text-sm", c.unread_count ? "font-bold text-slate-900" : "font-medium text-slate-800")}>{c.participant?.full_name ?? "Deleted account"}</span>
                        <span className="shrink-0 text-[11px] text-slate-400">{c.last_message ? timeAgo(c.last_message.created_at) : ""}</span>
                      </span>
                      <span className="mt-0.5 flex items-center gap-2">
                        <span className={cn("truncate text-[13px]", c.unread_count ? "font-medium text-slate-800" : "text-slate-500")}>{preview(c)}</span>
                        {c.is_muted && <BellOff className="h-3.5 w-3.5 shrink-0 text-slate-400" aria-label="Muted" />}
                        <CountBadge count={c.unread_count} className="ml-auto shrink-0" />
                      </span>
                    </span>
                  </button>
                  <div className="pr-2 opacity-100 md:opacity-0 md:group-hover:opacity-100 md:focus-within:opacity-100">
                    <Menu label="Conversation actions" items={[
                      { label: c.is_muted ? "Unmute" : "Mute", icon: <BellOff className="h-4 w-4" />, onSelect: () => toggle(c, "mute") },
                      { label: c.is_archived ? "Move to inbox" : "Archive", icon: <Archive className="h-4 w-4" />, onSelect: () => toggle(c, "archive") },
                    ]} />
                  </div>
                </li>
              ))}
            </ul>
          )}
          <LoadMore hasMore={!!list.hasNextPage} loading={list.isFetchingNextPage} onLoad={() => void list.fetchNextPage()} />
        </div>
      </aside>
      <section className={cn("min-w-0 flex-1", !conversationId && "hidden md:flex")}>
        {conversationId ? (
          <ConversationView key={conversationId} conversationId={conversationId} onBack={() => navigate("/messages")} />
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center p-8 text-center">
            <span className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-50 text-brand-700"><MessageCircle className="h-8 w-8" /></span>
            <h2 className="mt-4 text-lg font-semibold">Your messages</h2>
            <p className="mt-1 max-w-xs text-sm text-slate-500">Pick a conversation or start a new one. Friends can message freely; others share a 4-message allowance.</p>
            <Button className="mt-5" onClick={() => setComposing(true)} icon={<PenSquare className="h-4 w-4" />}>New message</Button>
          </div>
        )}
      </section>
      <NewMessageDialog open={composing} onClose={() => setComposing(false)} />
    </div>
  );
}
