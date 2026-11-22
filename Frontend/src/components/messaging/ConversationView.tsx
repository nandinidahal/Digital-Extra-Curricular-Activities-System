import { useInfiniteQuery, useQuery, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { ArrowLeft, Ban, Check, CheckCheck, FileText, Heart, Info, Paperclip, Pencil, RotateCw, Send, Trash2, UserPlus, X } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Avatar } from "@/components/common/Avatar";
import { Button } from "@/components/common/Button";
import { ErrorState, Spinner } from "@/components/common/Feedback";
import { FilePicker } from "@/components/common/FilePicker";
import { Menu } from "@/components/common/Menu";
import { useConfirm } from "@/components/common/Modal";
import { useRealtime } from "@/contexts/RealtimeContext";
import { qk } from "@/hooks/queryKeys";
import { errorMessage, toApiError } from "@/services/api/errors";
import { messagingApi } from "@/services/api/messaging";
import type { CursorPaginated, Message, MessagingState } from "@/types/api";
import { cn } from "@/utils/cn";
import { checkImageOrPdf, EVIDENCE_ACCEPT, LIMITS, newClientId } from "@/utils/files";
import { formatDate, formatTime, timeAgo } from "@/utils/format";

type Pages = InfiniteData<CursorPaginated<Message>>;
type Pending = { client_id: string; content: string; files: File[]; failed: boolean; created_at: string };

function StateBanner({ state, name }: { state: MessagingState; name: string }) {
  if (!state.can_message) {
    const text = {
      blocked: "You can't message this person.",
      user_unavailable: "This account is not available.",
      conversation_inactive: "This conversation is closed.",
      message_limit_reached: `You've used all ${state.messages_allowed} messages allowed before becoming friends. Send ${name} a friend request to keep talking.`,
    }[state.reason ?? "blocked"];
    return (
      <div role="status" className="flex items-start gap-2 border-t border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <Ban className="mt-0.5 h-4 w-4 shrink-0" />
        <span>{text}</span>
      </div>
    );
  }
  if (!state.is_friend && state.messages_remaining !== null) {
    return (
      <div role="status" className="flex items-center gap-2 border-t border-sky-100 bg-sky-50 px-4 py-2 text-xs text-sky-900">
        <Info className="h-3.5 w-3.5 shrink-0" />
        You're not friends yet: {state.messages_remaining} of {state.messages_allowed} messages left in this conversation (both of you share the limit).
      </div>
    );
  }
  return null;
}

function StatusTicks({ status }: { status: Message["status"] }) {
  if (status === "read") return <CheckCheck className="h-3.5 w-3.5 text-sky-300" aria-label="Read" />;
  if (status === "delivered") return <CheckCheck className="h-3.5 w-3.5" aria-label="Delivered" />;
  return <Check className="h-3.5 w-3.5" aria-label="Sent" />;
}

function Bubble({ message, showAvatar, onChanged }: { message: Message; showAvatar: boolean; onChanged: (m: Message | null) => void }) {
  const confirm = useConfirm();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content ?? "");
  const own = message.is_own;

  const react = async () => {
    try {
      const r = message.my_reaction ? await messagingApi.unreact(message.id) : await messagingApi.react(message.id, "love");
      onChanged(r.data);
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };
  const saveEdit = async () => {
    try {
      const r = await messagingApi.edit(message.id, draft.trim());
      onChanged(r.data);
      setEditing(false);
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };
  const del = async (scope: "me" | "everyone") => {
    if (!(await confirm({ title: scope === "me" ? "Delete for you?" : "Delete for everyone?", description: scope === "me" ? "The message disappears only from your view." : "The message is removed for both of you.", confirmLabel: "Delete" }))) return;
    try {
      if (scope === "me") {
        await messagingApi.deleteForMe(message.id);
        onChanged(null);
      } else {
        const r = await messagingApi.deleteForEveryone(message.id);
        onChanged(r.data);
      }
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  const reactions = Object.entries(message.reactions);
  return (
    <div className={cn("group flex items-end gap-2", own ? "justify-end" : "justify-start")}>
      {!own && <div className="w-7">{showAvatar && <Avatar src={message.sender?.profile_picture} name={message.sender?.full_name} size="xs" />}</div>}
      {own && !message.is_deleted && (
        <div className="opacity-0 transition group-hover:opacity-100 focus-within:opacity-100">
          <Menu label="Message actions" items={[
            { label: "Edit", icon: <Pencil className="h-4 w-4" />, onSelect: () => setEditing(true), hidden: !message.content || message.is_forwarded },
            { label: "Delete for everyone", icon: <Trash2 className="h-4 w-4" />, onSelect: () => del("everyone"), danger: true },
            { label: "Delete for me", icon: <Trash2 className="h-4 w-4" />, onSelect: () => del("me") },
          ]} />
        </div>
      )}
      <div className={cn("max-w-[80%] sm:max-w-[65%]", own && "items-end")}>
        <div className={cn(
          "relative rounded-2xl px-3.5 py-2 text-[15px] shadow-sm",
          message.is_deleted ? "border border-dashed border-slate-300 bg-transparent text-slate-400 italic" : own ? "rounded-br-md bg-brand-700 text-white" : "rounded-bl-md bg-white text-slate-800 ring-1 ring-slate-200",
        )}>
          {message.is_deleted ? "This message was deleted" : (
            <>
              {message.reply_to && (
                <div className={cn("mb-1.5 rounded-lg border-l-2 px-2 py-1 text-xs", own ? "border-white/60 bg-white/10" : "border-brand-400 bg-slate-50")}>
                  <span className="font-semibold">{message.reply_to.sender_username}</span>: {message.reply_to.is_available ? message.reply_to.content_preview : "Unavailable"}
                </div>
              )}
              {message.attachments.length > 0 && (
                <div className="mb-1 space-y-1.5">
                  {message.attachments.map((att) => att.kind === "image" ? (
                    <a key={att.id} href={att.url} target="_blank" rel="noopener noreferrer"><img src={att.url} alt={att.name} className="max-h-64 rounded-lg object-cover" loading="lazy" /></a>
                  ) : (
                    <a key={att.id} href={att.url} className={cn("flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm", own ? "bg-white/15" : "bg-slate-100")}><FileText className="h-4 w-4" />{att.name}</a>
                  ))}
                </div>
              )}
              {editing ? (
                <div className="flex items-center gap-1">
                  <input value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void saveEdit(); if (e.key === "Escape") setEditing(false); }} autoFocus aria-label="Edit message" className="min-w-0 flex-1 rounded-md bg-white/90 px-2 py-1 text-sm text-slate-900 focus:outline-none" />
                  <button onClick={saveEdit} aria-label="Save"><Check className="h-4 w-4" /></button>
                  <button onClick={() => setEditing(false)} aria-label="Cancel"><X className="h-4 w-4" /></button>
                </div>
              ) : message.content && <p className="prose-plain">{message.content}</p>}
            </>
          )}
          {reactions.length > 0 && (
            <span className="absolute -bottom-2.5 right-2 rounded-full bg-white px-1.5 py-0.5 text-[11px] text-rose-500 shadow ring-1 ring-slate-200">♥ {reactions.reduce((n, [, c]) => n + c, 0)}</span>
          )}
        </div>
        <div className={cn("mt-1 flex items-center gap-1.5 px-1 text-[11px] text-slate-400", own ? "justify-end" : "justify-start")}>
          <time dateTime={message.created_at}>{formatTime(message.created_at)}</time>
          {message.is_edited && !message.is_deleted && <span>· edited</span>}
          {own && !message.is_deleted && <span className="text-slate-400"><StatusTicks status={message.status} /></span>}
        </div>
      </div>
      {!own && !message.is_deleted && (
        <button onClick={react} aria-label={message.my_reaction ? "Remove reaction" : "React with a heart"} className={cn("mb-5 rounded-full p-1.5 opacity-0 transition group-hover:opacity-100 focus:opacity-100", message.my_reaction ? "text-rose-500 opacity-100" : "text-slate-400 hover:text-rose-500")}>
          <Heart className={cn("h-4 w-4", message.my_reaction && "fill-current")} />
        </button>
      )}
    </div>
  );
}

export function ConversationView({ conversationId, onBack }: { conversationId: string; onBack: () => void }) {
  const queryClient = useQueryClient();
  const { subscribeMessaging, sendMessaging } = useRealtime();
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [showAttach, setShowAttach] = useState(false);
  const [pending, setPending] = useState<Pending[]>([]);
  const [typing, setTyping] = useState(false);
  const [stateOverride, setStateOverride] = useState<MessagingState | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const atBottom = useRef(true);
  const lastTypingSent = useRef(0);
  const typingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const conversation = useQuery({ queryKey: qk.conversation(conversationId), queryFn: async () => (await messagingApi.conversation(conversationId)).data });
  const messages = useInfiniteQuery({
    queryKey: qk.messages(conversationId),
    queryFn: async ({ pageParam }) => (await messagingApi.messages(conversationId, pageParam)).data,
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.pagination.next,
  });

  const state = stateOverride ?? conversation.data?.messaging ?? null;
  const other = conversation.data?.participant;

  const patchCache = useCallback((fn: (list: Message[]) => Message[]) => {
    queryClient.setQueryData<Pages>(qk.messages(conversationId), (data) => {
      if (!data) return data;
      const [first, ...rest] = data.pages;
      return { ...data, pages: [{ ...first, results: fn(first.results) }, ...rest] };
    });
  }, [queryClient, conversationId]);

  const upsert = useCallback((message: Message) => {
    let found = false;
    queryClient.setQueryData<Pages>(qk.messages(conversationId), (data) => {
      if (!data) return data;
      const pages = data.pages.map((p) => ({ ...p, results: p.results.map((m) => (m.id === message.id ? ((found = true), message) : m)) }));
      if (!found) pages[0] = { ...pages[0], results: [message, ...pages[0].results] };
      return { ...data, pages };
    });
    if (message.client_id) setPending((list) => list.filter((p) => p.client_id !== message.client_id));
  }, [queryClient, conversationId]);

  const markRead = useCallback(() => {
    messagingApi.markRead(conversationId).then(() => {
      void queryClient.invalidateQueries({ queryKey: qk.messagingUnread });
      void queryClient.invalidateQueries({ queryKey: ["messaging", "conversations"] });
    }).catch(() => undefined);
  }, [conversationId, queryClient]);

  useEffect(() => {
    setStateOverride(null);
    setPending([]);
    setTyping(false);
    markRead();
  }, [conversationId, markRead]);

  // Real-time events of THIS conversation from the inbox socket.
  useEffect(() => subscribeMessaging((event) => {
    if (event.conversation_id !== conversationId) return;
    const data = event.data as Record<string, unknown>;
    switch (event.type) {
      case "message.new":
      case "message.updated":
      case "message.reaction_updated":
        if (event.type === "message.reaction_updated") {
          patchCache((list) => list.map((m) => (m.id === data.message_id ? { ...m, reactions: data.reactions as Message["reactions"], my_reaction: data.my_reaction as string | null } : m)));
        } else {
          upsert(data as unknown as Message);
          if (event.type === "message.new" && !(data as unknown as Message).is_own) {
            setTyping(false);
            markRead();
          }
        }
        break;
      case "message.deleted":
        if (data.scope === "me") patchCache((list) => list.filter((m) => m.id !== data.message_id));
        else patchCache((list) => list.map((m) => (m.id === data.message_id ? { ...m, is_deleted: true, content: null, attachments: [], reactions: {} } : m)));
        break;
      case "message.read":
      case "message.delivered": {
        const ids = new Set(data.message_ids as string[]);
        const status = event.type === "message.read" ? "read" : "delivered";
        patchCache((list) => list.map((m) => (ids.has(m.id) && m.is_own && m.status !== "read" ? { ...m, status } : m)));
        break;
      }
      case "user.typing":
        setTyping(!!data.is_typing);
        if (typingTimer.current) clearTimeout(typingTimer.current);
        if (data.is_typing) typingTimer.current = setTimeout(() => setTyping(false), Number(data.expires_in ?? 6) * 1000);
        break;
      case "conversation.permissions":
        setStateOverride(data as unknown as MessagingState);
        break;
    }
  }), [subscribeMessaging, conversationId, upsert, patchCache, markRead]);

  const items = [...(messages.data?.pages.flatMap((p) => p.results) ?? [])].reverse();

  // Keep the view pinned to the newest message unless the user scrolled up.
  useLayoutEffect(() => {
    const el = scroller.current;
    if (el && atBottom.current) el.scrollTop = el.scrollHeight;
  }, [items.length, pending.length, typing]);

  const notifyTyping = (isTyping: boolean) => {
    const now = Date.now();
    if (isTyping && now - lastTypingSent.current < 3000) return;
    lastTypingSent.current = isTyping ? now : 0;
    sendMessaging({ type: "message.typing", conversation_id: conversationId, data: { is_typing: isTyping } });
  };

  const send = async (item: Pending) => {
    setPending((list) => list.map((p) => (p.client_id === item.client_id ? { ...p, failed: false } : p)));
    try {
      const r = await messagingApi.send(conversationId, { content: item.content, client_id: item.client_id, attachments: item.files });
      upsert(r.data.message);
      setStateOverride(r.data.messaging);
      void queryClient.invalidateQueries({ queryKey: ["messaging", "conversations"] });
    } catch (error) {
      const e = toApiError(error);
      if (e.code === "message_limit_reached" || e.code === "messaging_not_allowed") {
        setPending((list) => list.filter((p) => p.client_id !== item.client_id));
        void conversation.refetch().then((r) => r.data?.messaging && setStateOverride(r.data.messaging));
        toast.error(e.message);
        return;
      }
      setPending((list) => list.map((p) => (p.client_id === item.client_id ? { ...p, failed: true } : p)));
      toast.error(errorMessage(error));
    }
  };

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if ((!text.trim() && !files.length) || (state && !state.can_message)) return;
    // The client_id is reused on retry, so the server never creates the message twice.
    const item: Pending = { client_id: newClientId(), content: text.trim(), files, failed: false, created_at: new Date().toISOString() };
    setPending((list) => [...list, item]);
    setText("");
    setFiles([]);
    setShowAttach(false);
    notifyTyping(false);
    atBottom.current = true;
    void send(item);
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  if (conversation.isError) return <div className="p-6"><ErrorState error={conversation.error} title="Conversation not available" /></div>;
  const canSend = !state || state.can_message;
  const name = other?.full_name ?? "this person";

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3">
        <button onClick={onBack} className="rounded-full p-1.5 text-slate-500 hover:bg-slate-100 md:hidden" aria-label="Back to conversations"><ArrowLeft className="h-5 w-5" /></button>
        {other ? (
          <Link to={`/profile/${other.id}`} className="flex min-w-0 items-center gap-3">
            <Avatar src={other.profile_picture} name={other.full_name} size="sm" online={other.is_online} />
            <span className="min-w-0">
              <span className="block truncate font-semibold text-slate-900">{other.full_name}</span>
              <span className="block truncate text-xs text-slate-500">
                {typing ? <span className="text-brand-700">typing…</span> : other.is_online ? "Online" : other.last_seen_at ? `Last seen ${timeAgo(other.last_seen_at)}` : `@${other.username}`}
              </span>
            </span>
          </Link>
        ) : <Spinner />}
        {state && !state.is_friend && other && (
          <Link to={`/profile/${other.id}`} className="ml-auto"><Button size="sm" variant="subtle" icon={<UserPlus className="h-4 w-4" />}>Add friend</Button></Link>
        )}
      </header>

      <div
        ref={scroller}
        onScroll={(e) => {
          const el = e.currentTarget;
          atBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
        className="scroll-thin min-h-0 flex-1 space-y-3 overflow-y-auto bg-slate-50 px-3 py-4 sm:px-5"
        aria-live="polite"
      >
        {messages.hasNextPage && (
          <div className="flex justify-center">
            <Button size="sm" variant="outline" loading={messages.isFetchingNextPage} onClick={() => { atBottom.current = false; void messages.fetchNextPage(); }}>Load older messages</Button>
          </div>
        )}
        {messages.isPending ? <div className="flex justify-center py-10"><Spinner /></div> : items.length === 0 && pending.length === 0 ? (
          <div className="py-16 text-center text-sm text-slate-500">
            <p className="font-medium text-slate-700">Say hello to {name} 👋</p>
            {state && !state.is_friend && state.messages_allowed !== null && <p className="mt-1">You can exchange {state.messages_allowed} messages before becoming friends.</p>}
          </div>
        ) : null}
        {items.map((m, i) => {
          const prev = items[i - 1];
          const newDay = !prev || formatDate(prev.created_at) !== formatDate(m.created_at);
          const next = items[i + 1];
          return (
            <div key={m.id}>
              {newDay && <p className="my-3 text-center text-xs font-medium text-slate-400">{formatDate(m.created_at)}</p>}
              <Bubble message={m} showAvatar={!next || next.sender?.id !== m.sender?.id} onChanged={(updated) => updated ? upsert(updated) : patchCache((list) => list.filter((x) => x.id !== m.id))} />
            </div>
          );
        })}
        {pending.map((p) => (
          <div key={p.client_id} className="flex justify-end">
            <div className="max-w-[80%] sm:max-w-[65%]">
              <div className={cn("rounded-2xl rounded-br-md px-3.5 py-2 text-[15px] text-white", p.failed ? "bg-rose-500" : "bg-brand-700/70")}>
                {p.files.length > 0 && <p className="mb-1 text-xs opacity-90"><Paperclip className="mr-1 inline h-3 w-3" />{p.files.length} attachment{p.files.length === 1 ? "" : "s"}</p>}
                <p className="prose-plain">{p.content}</p>
              </div>
              <p className="mt-1 flex items-center justify-end gap-2 px-1 text-[11px] text-slate-400">
                {p.failed ? (
                  <>
                    <span className="text-rose-600">Not sent</span>
                    <button onClick={() => send(p)} className="inline-flex items-center gap-1 font-semibold text-brand-700"><RotateCw className="h-3 w-3" /> Retry</button>
                    <button onClick={() => setPending((l) => l.filter((x) => x.client_id !== p.client_id))} className="font-semibold">Discard</button>
                  </>
                ) : "Sending…"}
              </p>
            </div>
          </div>
        ))}
        {typing && <p className="pl-9 text-xs text-slate-500">{name.split(" ")[0]} is typing…</p>}
      </div>

      {state && <StateBanner state={state} name={name} />}
      <form onSubmit={submit} className="border-t border-slate-200 bg-white p-3">
        {showAttach && (
          <div className="mb-2">
            <FilePicker files={files} onChange={setFiles} accept={EVIDENCE_ACCEPT} max={LIMITS.messageAttachments} compact validate={(f) => checkImageOrPdf(f, LIMITS.messageImage, LIMITS.messageFile)} label="Add image or PDF" />
          </div>
        )}
        <div className="flex items-end gap-2">
          <button type="button" onClick={() => setShowAttach((s) => !s)} disabled={!canSend} className="rounded-full p-2.5 text-slate-500 hover:bg-slate-100 disabled:opacity-40" aria-label="Attach files" aria-expanded={showAttach}>
            <Paperclip className="h-5 w-5" />
          </button>
          <label htmlFor="message-input" className="sr-only">Message</label>
          <textarea
            id="message-input"
            value={text}
            onChange={(e) => { setText(e.target.value); if (e.target.value) notifyTyping(true); }}
            onBlur={() => notifyTyping(false)}
            onKeyDown={onKey}
            rows={1}
            maxLength={5000}
            disabled={!canSend}
            placeholder={canSend ? "Write a message…" : "Messaging is not available"}
            className="scroll-thin max-h-36 min-h-11 flex-1 resize-none rounded-2xl border-0 bg-slate-100 px-4 py-2.5 text-[15px] focus:bg-white focus:ring-2 focus:ring-brand-200 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
          />
          <Button type="submit" size="icon" className="h-11 w-11" disabled={!canSend || (!text.trim() && !files.length)} aria-label="Send message"><Send className="h-5 w-5" /></Button>
        </div>
      </form>
    </div>
  );
}
