import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { Flag, Heart, Pencil, Reply, Send, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Avatar } from "@/components/common/Avatar";
import { Button } from "@/components/common/Button";
import { Spinner } from "@/components/common/Feedback";
import { Menu } from "@/components/common/Menu";
import { useConfirm } from "@/components/common/Modal";
import { useAuth } from "@/contexts/AuthContext";
import { qk } from "@/hooks/queryKeys";
import { usePostCache } from "@/hooks/usePostCache";
import { errorMessage } from "@/services/api/errors";
import { socialApi } from "@/services/api/social";
import type { Comment } from "@/types/api";
import { cn } from "@/utils/cn";
import { timeAgo } from "@/utils/format";
import { socialReportReasons } from "@/utils/labels";
import { ReportDialog } from "./ReportDialog";

const MAX_DEPTH = 2; // social.models.MAX_COMMENT_DEPTH

function CommentInput({ onSubmit, placeholder, initial = "", autoFocus, onCancel }: {
  onSubmit: (text: string) => Promise<unknown>; placeholder: string; initial?: string; autoFocus?: boolean; onCancel?: () => void;
}) {
  const { user, profile } = useAuth();
  const [text, setText] = useState(initial);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim() || busy) return;
    setBusy(true);
    try {
      await onSubmit(text.trim());
      setText("");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="flex items-start gap-2">
      <Avatar src={profile?.profile_picture} name={user?.full_name} size="xs" className="mt-1.5" />
      <div className="flex flex-1 items-center gap-1 rounded-2xl bg-slate-100 pr-1 focus-within:bg-white focus-within:ring-2 focus-within:ring-brand-200">
        <label className="sr-only" htmlFor={`c-${placeholder}`}>{placeholder}</label>
        <input
          id={`c-${placeholder}`}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={placeholder}
          maxLength={2000}
          autoFocus={autoFocus}
          onKeyDown={(e) => e.key === "Escape" && onCancel?.()}
          className="min-w-0 flex-1 border-0 bg-transparent px-3.5 py-2 text-sm focus:ring-0 focus:outline-none"
        />
        <button type="submit" disabled={!text.trim() || busy} className="rounded-full p-1.5 text-brand-700 hover:bg-brand-50 disabled:text-slate-300" aria-label="Send">
          {busy ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />}
        </button>
      </div>
    </form>
  );
}

function CommentItem({ comment, postId }: { comment: Comment; postId: string }) {
  const queryClient = useQueryClient();
  const { update } = usePostCache();
  const confirm = useConfirm();
  const [liked, setLiked] = useState({ is_liked: comment.is_liked, like_count: comment.like_count });
  const [editing, setEditing] = useState(false);
  const [replying, setReplying] = useState(false);
  const [showReplies, setShowReplies] = useState(false);
  const [reporting, setReporting] = useState(false);

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: qk.comments(postId) });
    if (comment.parent_comment_id) void queryClient.invalidateQueries({ queryKey: qk.replies(comment.parent_comment_id) });
    void queryClient.invalidateQueries({ queryKey: qk.replies(comment.id) });
  };

  const toggleLike = async () => {
    const before = liked;
    setLiked({ is_liked: !before.is_liked, like_count: before.like_count + (before.is_liked ? -1 : 1) });
    try {
      const r = before.is_liked ? await socialApi.unlikeComment(comment.id) : await socialApi.likeComment(comment.id);
      setLiked(r.data);
    } catch (error) {
      setLiked(before);
      toast.error(errorMessage(error));
    }
  };

  const remove = async () => {
    if (!(await confirm({ title: "Delete comment?", description: "This comment will be removed for everyone.", confirmLabel: "Delete" }))) return;
    try {
      await socialApi.deleteComment(comment.id);
      toast.success("Comment deleted.");
      update(postId, (p) => ({ ...p, comment_count: Math.max(0, p.comment_count - 1) }));
      invalidate();
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  if (comment.is_deleted) {
    return (
      <li className="text-sm italic text-slate-400">
        This comment was deleted.
        {comment.reply_count > 0 && <Replies parent={comment} postId={postId} open={showReplies} setOpen={setShowReplies} />}
      </li>
    );
  }

  const author = comment.author!;
  return (
    <li>
      <div className="flex gap-2.5">
        <Link to={`/profile/${author.id}`} className="shrink-0"><Avatar src={author.profile_picture} name={author.full_name} size="xs" className="mt-0.5" /></Link>
        <div className="min-w-0 flex-1">
          {editing ? (
            <CommentInput
              initial={comment.content}
              placeholder="Edit comment"
              autoFocus
              onCancel={() => setEditing(false)}
              onSubmit={async (text) => {
                await socialApi.editComment(comment.id, text);
                setEditing(false);
                toast.success("Comment updated.");
                invalidate();
              }}
            />
          ) : (
            <div className="group flex items-start gap-1">
              <div className="min-w-0 rounded-2xl bg-slate-100 px-3.5 py-2">
                <Link to={`/profile/${author.id}`} className="text-[13px] font-semibold text-slate-900 hover:underline">{author.full_name}</Link>
                <p className="prose-plain text-sm text-slate-700">{comment.content}</p>
              </div>
              <div className="opacity-0 transition group-hover:opacity-100 focus-within:opacity-100">
                <Menu
                  label="Comment actions"
                  items={[
                    { label: "Edit", icon: <Pencil className="h-4 w-4" />, onSelect: () => setEditing(true), hidden: !comment.is_owner },
                    { label: "Delete", icon: <Trash2 className="h-4 w-4" />, onSelect: remove, danger: true, hidden: !comment.is_owner },
                    { label: "Report", icon: <Flag className="h-4 w-4" />, onSelect: () => setReporting(true), hidden: comment.is_owner },
                  ]}
                />
              </div>
            </div>
          )}
          <div className="mt-1 flex items-center gap-3 pl-2 text-xs text-slate-500">
            <time dateTime={comment.created_at}>{timeAgo(comment.created_at)}</time>
            {comment.is_edited && <span>Edited</span>}
            <button onClick={toggleLike} className={cn("inline-flex items-center gap-1 font-semibold hover:text-rose-600", liked.is_liked && "text-rose-600")} aria-pressed={liked.is_liked}>
              <Heart className={cn("h-3.5 w-3.5", liked.is_liked && "fill-current")} /> {liked.like_count || ""} Like
            </button>
            {comment.depth < MAX_DEPTH && (
              <button onClick={() => setReplying((r) => !r)} className="inline-flex items-center gap-1 font-semibold hover:text-slate-800"><Reply className="h-3.5 w-3.5" /> Reply</button>
            )}
          </div>
          {replying && (
            <div className="mt-2">
              <CommentInput
                placeholder={`Reply to ${author.full_name}`}
                autoFocus
                onCancel={() => setReplying(false)}
                onSubmit={async (text) => {
                  await socialApi.reply(comment.id, text);
                  setReplying(false);
                  setShowReplies(true);
                  update(postId, (p) => ({ ...p, comment_count: p.comment_count + 1 }));
                  invalidate();
                }}
              />
            </div>
          )}
          {comment.reply_count > 0 && <Replies parent={comment} postId={postId} open={showReplies} setOpen={setShowReplies} />}
        </div>
      </div>
      <ReportDialog open={reporting} onClose={() => setReporting(false)} title="Report comment" reasons={socialReportReasons} onSubmit={(r, d) => socialApi.report("comment", comment.id, r, d)} />
    </li>
  );
}

function Replies({ parent, postId, open, setOpen }: { parent: Comment; postId: string; open: boolean; setOpen: (v: boolean) => void }) {
  const query = useInfiniteQuery({
    queryKey: qk.replies(parent.id),
    queryFn: async ({ pageParam }) => (await socialApi.replies(parent.id, pageParam)).data,
    initialPageParam: 1,
    getNextPageParam: (last) => (last.pagination.next ? last.pagination.page + 1 : undefined),
    enabled: open,
  });
  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="mt-1.5 pl-2 text-xs font-semibold text-brand-700 hover:underline">
        View {parent.reply_count} {parent.reply_count === 1 ? "reply" : "replies"}
      </button>
    );
  }
  const items = query.data?.pages.flatMap((p) => p.results) ?? [];
  return (
    <div className="mt-2 border-l-2 border-slate-100 pl-3">
      {query.isPending ? <Spinner className="py-2" /> : (
        <ul className="space-y-3">{items.map((c) => <CommentItem key={c.id} comment={c} postId={postId} />)}</ul>
      )}
      {query.hasNextPage && (
        <button onClick={() => void query.fetchNextPage()} className="mt-2 text-xs font-semibold text-brand-700 hover:underline">Load more replies</button>
      )}
    </div>
  );
}

/** Top-level comments of a post (paginated, oldest first) + composer. */
export function CommentSection({ postId }: { postId: string }) {
  const queryClient = useQueryClient();
  const { update } = usePostCache();
  const query = useInfiniteQuery({
    queryKey: qk.comments(postId),
    queryFn: async ({ pageParam }) => (await socialApi.comments(postId, pageParam)).data,
    initialPageParam: 1,
    getNextPageParam: (last) => (last.pagination.next ? last.pagination.page + 1 : undefined),
  });
  const items = query.data?.pages.flatMap((p) => p.results) ?? [];
  return (
    <div className="space-y-4 border-t border-slate-100 pt-4">
      <CommentInput
        placeholder="Write a comment"
        onSubmit={async (text) => {
          await socialApi.addComment(postId, text);
          toast.success("Comment added.");
          update(postId, (p) => ({ ...p, comment_count: p.comment_count + 1 }));
          await queryClient.invalidateQueries({ queryKey: qk.comments(postId) });
        }}
      />
      {query.isPending ? (
        <Spinner className="px-2" />
      ) : query.isError ? (
        <p className="text-sm text-rose-600">{errorMessage(query.error)}</p>
      ) : items.length === 0 ? (
        <p className="px-2 text-sm text-slate-500">No comments yet. Start the conversation.</p>
      ) : (
        <ul className="space-y-4">{items.map((c) => <CommentItem key={c.id} comment={c} postId={postId} />)}</ul>
      )}
      {query.hasNextPage && (
        <Button variant="ghost" size="sm" loading={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>Load more comments</Button>
      )}
    </div>
  );
}
