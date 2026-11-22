import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import {
  Award, Bell, CheckCheck, Heart, Megaphone, MessageCircle, MoreHorizontal, Settings, ShieldAlert, Trash2, UserPlus, Users,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Avatar } from "@/components/common/Avatar";
import { Button } from "@/components/common/Button";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/common/Feedback";
import { LoadMore } from "@/components/common/LoadMore";
import { Menu } from "@/components/common/Menu";
import { useConfirm } from "@/components/common/Modal";
import { PageHeader } from "@/components/common/PageHeader";
import { Tabs } from "@/components/common/Tabs";
import { qk } from "@/hooks/queryKeys";
import { errorMessage } from "@/services/api/errors";
import { notificationsApi } from "@/services/api/notifications";
import type { AppNotification, NotificationCategory } from "@/types/api";
import { cn } from "@/utils/cn";
import { timeAgo } from "@/utils/format";

const categoryIcon: Record<NotificationCategory, ReactNode> = {
  account: <ShieldAlert className="h-3.5 w-3.5" />,
  friends: <UserPlus className="h-3.5 w-3.5" />,
  messages: <MessageCircle className="h-3.5 w-3.5" />,
  social: <Heart className="h-3.5 w-3.5" />,
  announcements: <Megaphone className="h-3.5 w-3.5" />,
  achievements: <Award className="h-3.5 w-3.5" />,
  system: <Bell className="h-3.5 w-3.5" />,
};
const categoryTone: Record<NotificationCategory, string> = {
  account: "bg-slate-700", friends: "bg-sky-600", messages: "bg-brand-600", social: "bg-rose-500",
  announcements: "bg-amber-500", achievements: "bg-violet-600", system: "bg-slate-500",
};

type Filter = "all" | "unread" | NotificationCategory;

export default function NotificationsPage() {
  const navigate = useNavigate();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<Filter>("all");

  const params = filter === "all" ? {} : filter === "unread" ? { is_read: false } : { category: filter };
  const query = useInfiniteQuery({
    queryKey: qk.notifications(filter),
    queryFn: async ({ pageParam }) => (await notificationsApi.list({ ...params, page: pageParam })).data,
    initialPageParam: 1,
    getNextPageParam: (last) => (last.pagination.next ? last.pagination.page + 1 : undefined),
  });
  const items = query.data?.pages.flatMap((p) => p.results) ?? [];

  const sync = (unread?: number) => {
    if (typeof unread === "number") queryClient.setQueryData(qk.notificationsUnread, unread);
    void queryClient.invalidateQueries({ queryKey: ["notifications", "list"] });
  };

  const open = async (n: AppNotification) => {
    if (!n.is_read) {
      try {
        const r = await notificationsApi.markRead(n.id);
        sync(r.data.unread_count);
      } catch {
        /* navigation still works */
      }
    }
    if (n.action_url) navigate(n.action_url);
  };

  const action = async (fn: () => Promise<{ data: { unread_count: number }; message: string }>) => {
    try {
      const r = await fn();
      toast.success(r.message);
      sync(r.data.unread_count);
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        icon={<Bell className="h-5 w-5" />}
        title="Notifications"
        actions={
          <>
            <Button variant="outline" icon={<CheckCheck className="h-4 w-4" />} onClick={() => action(notificationsApi.markAllRead)}>Mark all read</Button>
            <Menu
              label="More"
              trigger={<MoreHorizontal className="h-5 w-5" />}
              items={[
                { label: "Clear read notifications", icon: <Trash2 className="h-4 w-4" />, onSelect: async () => { if (await confirm({ title: "Clear read notifications?", confirmLabel: "Clear" })) void action(() => notificationsApi.clear(true)); } },
                { label: "Clear all notifications", icon: <Trash2 className="h-4 w-4" />, danger: true, onSelect: async () => { if (await confirm({ title: "Clear all notifications?", description: "Unread ones are removed too.", confirmLabel: "Clear all" })) void action(() => notificationsApi.clear(false)); } },
                { label: "Notification settings", icon: <Settings className="h-4 w-4" />, onSelect: () => navigate("/settings/notifications") },
              ]}
            />
          </>
        }
      />
      <Tabs<Filter>
        className="mb-4"
        value={filter}
        onChange={setFilter}
        items={[
          { value: "all", label: "All" },
          { value: "unread", label: "Unread" },
          { value: "friends", label: <><Users className="h-4 w-4" /> Friends</> },
          { value: "social", label: <><Heart className="h-4 w-4" /> Social</> },
          { value: "messages", label: <><MessageCircle className="h-4 w-4" /> Messages</> },
          { value: "announcements", label: <><Megaphone className="h-4 w-4" /> Events</> },
          { value: "achievements", label: <><Award className="h-4 w-4" /> Achievements</> },
          { value: "account", label: "Account" },
        ]}
      />
      {query.isPending ? <div className="space-y-3"><CardSkeleton lines={1} /><CardSkeleton lines={1} /></div> : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState icon={<Bell className="h-6 w-6" />} title={filter === "unread" ? "You're all caught up" : "No notifications"} description="Likes, comments, friend requests, messages and review decisions show up here." />
      ) : (
        <ul className="card divide-y divide-slate-100 overflow-hidden">
          {items.map((n) => (
            <li key={n.id} className={cn("group flex items-start gap-3 px-4 py-3.5 transition", !n.is_read && "bg-brand-50/50")}>
              <button onClick={() => open(n)} className="flex min-w-0 flex-1 items-start gap-3 text-left">
                <span className="relative shrink-0">
                  <Avatar src={n.actor?.profile_picture} name={n.actor?.full_name ?? "DEAS"} />
                  <span className={cn("absolute -right-1 -bottom-1 flex h-5 w-5 items-center justify-center rounded-full text-white ring-2 ring-white", categoryTone[n.category])}>{categoryIcon[n.category]}</span>
                </span>
                <span className="min-w-0 flex-1">
                  <span className={cn("block text-sm", n.is_read ? "text-slate-700" : "font-semibold text-slate-900")}>{n.title}</span>
                  <span className="mt-0.5 block text-sm text-slate-600">{n.message}{typeof n.metadata.count === "number" && n.metadata.count > 1 ? ` (${n.metadata.count})` : ""}</span>
                  <time dateTime={n.created_at} className="mt-1 block text-xs text-slate-400">{timeAgo(n.created_at)}</time>
                </span>
                {!n.is_read && <span className="mt-2 h-2.5 w-2.5 shrink-0 rounded-full bg-brand-600" aria-label="Unread" />}
              </button>
              <Menu
                label="Notification actions"
                items={[
                  { label: n.is_read ? "Mark as unread" : "Mark as read", icon: <CheckCheck className="h-4 w-4" />, onSelect: () => action(() => (n.is_read ? notificationsApi.markUnread(n.id) : notificationsApi.markRead(n.id))) },
                  { label: "Delete", icon: <Trash2 className="h-4 w-4" />, danger: true, onSelect: () => action(() => notificationsApi.remove(n.id)) },
                ]}
              />
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={!!query.hasNextPage} loading={query.isFetchingNextPage} onLoad={() => void query.fetchNextPage()} />
      <p className="mt-6 text-center text-xs text-slate-400">Choose which notifications you get in <Link to="/settings/notifications" className="font-medium text-brand-700 hover:underline">settings</Link>.</p>
    </div>
  );
}
