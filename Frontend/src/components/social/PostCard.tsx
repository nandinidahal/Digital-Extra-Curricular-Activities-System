import { Award, CalendarDays, Flag, Heart, Link2Off, MapPin, MessageCircle, Pencil, Repeat2, Trash2, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Avatar } from "@/components/common/Avatar";
import { Button } from "@/components/common/Button";
import { Badge } from "@/components/common/Feedback";
import { FilePicker } from "@/components/common/FilePicker";
import { Select, Textarea } from "@/components/common/Field";
import { Menu } from "@/components/common/Menu";
import { Modal, useConfirm } from "@/components/common/Modal";
import { usePostCache } from "@/hooks/usePostCache";
import { errorMessage } from "@/services/api/errors";
import { socialApi } from "@/services/api/social";
import type { Post, PostType, PostVisibility, SharedResource } from "@/types/api";
import { cn } from "@/utils/cn";
import { checkImage, IMAGE_ACCEPT, LIMITS } from "@/utils/files";
import { formatDate, formatDateTime, timeAgo } from "@/utils/format";
import { achievementTypeLabels, levelLabels, postTypeLabels, socialReportReasons, visibilityLabels } from "@/utils/labels";
import { CommentSection } from "./CommentSection";
import { ReportDialog } from "./ReportDialog";
import { VisibilityIcon } from "./VisibilityIcon";

function MediaGrid({ media }: { media: Post["media"] }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!media.length) return null;
  const count = media.length;
  return (
    <>
      <div className={cn("mt-3 grid gap-1 overflow-hidden rounded-xl", count === 1 ? "grid-cols-1" : "grid-cols-2")}>
        {media.slice(0, 4).map((m, i) => (
          <button
            key={m.id}
            onClick={() => setOpen(m.url)}
            className={cn("relative overflow-hidden bg-slate-100", count === 1 ? "max-h-[32rem]" : "aspect-square", count === 3 && i === 0 && "row-span-2 aspect-auto")}
            aria-label={`Open image ${i + 1}`}
          >
            <img src={m.url} alt="" loading="lazy" className="h-full w-full object-cover transition hover:opacity-95" />
            {i === 3 && count > 4 && <span className="absolute inset-0 flex items-center justify-center bg-slate-900/50 text-2xl font-semibold text-white">+{count - 4}</span>}
          </button>
        ))}
      </div>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/90 p-4" onClick={() => setOpen(null)} role="dialog" aria-modal="true" aria-label="Image preview">
          <button className="absolute top-4 right-4 rounded-full bg-white/10 p-2 text-white hover:bg-white/20" aria-label="Close"><X className="h-6 w-6" /></button>
          <img src={open} alt="" className="max-h-full max-w-full rounded-lg object-contain" />
        </div>
      )}
    </>
  );
}

export function SharedResourceCard({ resource }: { resource: SharedResource }) {
  if (!resource.available || !resource.data) {
    return (
      <div className="mt-3 flex items-center gap-3 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">
        <Link2Off className="h-5 w-5" /> This {resource.type} is no longer available.
      </div>
    );
  }
  if (resource.type === "announcement") {
    const a = resource.data;
    return (
      <Link to={`/announcements/${a.id}`} className="mt-3 block overflow-hidden rounded-xl border border-slate-200 transition hover:border-brand-300 hover:shadow-card">
        {a.cover_image && <img src={a.cover_image} alt="" className="h-40 w-full object-cover" loading="lazy" />}
        <div className="p-4">
          <p className="text-xs font-semibold tracking-wide text-brand-700 uppercase">{a.category ?? "Announcement"}</p>
          <p className="mt-1 font-semibold text-slate-900">{a.title}</p>
          {a.short_description && <p className="mt-1 line-clamp-2 text-sm text-slate-600">{a.short_description}</p>}
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
            {a.start_datetime && <span className="inline-flex items-center gap-1"><CalendarDays className="h-3.5 w-3.5" />{formatDateTime(a.start_datetime)}</span>}
            {a.location && <span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{a.location}</span>}
          </div>
        </div>
      </Link>
    );
  }
  const a = resource.data;
  return (
    <Link to={`/achievements/${a.id}`} className="mt-3 flex items-center gap-4 rounded-xl border border-amber-200 bg-gradient-to-br from-amber-50 to-white p-4 transition hover:shadow-card">
      <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-amber-100 text-amber-700"><Award className="h-6 w-6" /></span>
      <div className="min-w-0">
        <p className="text-xs font-semibold tracking-wide text-amber-700 uppercase">Verified achievement · {levelLabels[a.level]}</p>
        <p className="truncate font-semibold text-slate-900">{a.title}</p>
        <p className="truncate text-xs text-slate-500">
          {a.user.full_name} · {achievementTypeLabels[a.achievement_type]}{a.organization ? ` · ${a.organization}` : ""} · {formatDate(a.achievement_date)}
        </p>
      </div>
    </Link>
  );
}

function EditPostDialog({ post, open, onClose }: { post: Post; open: boolean; onClose: () => void }) {
  const { update } = usePostCache();
  const [content, setContent] = useState(post.content);
  const [visibility, setVisibility] = useState<PostVisibility>(post.visibility);
  const [postType, setPostType] = useState<PostType>(post.post_type);
  const [images, setImages] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      const r = await socialApi.updatePost(post.id, { content: content.trim(), visibility, post_type: postType, images });
      update(post.id, () => r.data.post);
      toast.success("Post updated.");
      setImages([]);
      onClose();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  const removeMedia = async (mediaId: string) => {
    try {
      const r = await socialApi.removeMedia(post.id, mediaId);
      update(post.id, () => r.data.post);
      toast.success("Photo removed.");
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };
  const visibilities = (Object.keys(visibilityLabels) as PostVisibility[]).filter((v) => !(post.shared_type && v === "private"));
  return (
    <Modal open={open} onClose={onClose} title="Edit post" footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button loading={busy} onClick={save}>Save changes</Button></>}>
      <div className="space-y-4">
        <Textarea label={post.shared_type ? "Caption" : "Text"} rows={5} maxLength={post.shared_type ? 500 : 5000} value={content} onChange={(e) => setContent(e.target.value)} />
        <div className="grid gap-3 sm:grid-cols-2">
          <Select label="Who can see this" value={visibility} onChange={(e) => setVisibility(e.target.value as PostVisibility)} options={visibilities.map((v) => ({ value: v, label: visibilityLabels[v] }))} />
          {!post.shared_type && <Select label="Type" value={postType} onChange={(e) => setPostType(e.target.value as PostType)} options={Object.entries(postTypeLabels).map(([v, l]) => ({ value: v, label: l }))} />}
        </div>
        {!post.shared_type && (
          <div>
            <p className="label">Photos</p>
            {post.media.length > 0 && (
              <div className="mb-3 grid grid-cols-4 gap-2">
                {post.media.map((m) => (
                  <div key={m.id} className="relative aspect-square overflow-hidden rounded-lg">
                    <img src={m.url} alt="" className="h-full w-full object-cover" />
                    <button onClick={() => removeMedia(m.id)} className="absolute top-1 right-1 rounded-full bg-slate-900/70 p-1 text-white" aria-label="Remove photo"><X className="h-3.5 w-3.5" /></button>
                  </div>
                ))}
              </div>
            )}
            <FilePicker files={images} onChange={setImages} accept={IMAGE_ACCEPT} max={Math.max(0, LIMITS.postImages - post.media.length)} validate={(f) => checkImage(f, LIMITS.postImage)} label="Add photos" compact />
          </div>
        )}
      </div>
    </Modal>
  );
}

function ShareDialog({ post, open, onClose }: { post: Post; open: boolean; onClose: () => void }) {
  const { update } = usePostCache();
  const [caption, setCaption] = useState("");
  const [busy, setBusy] = useState(false);
  const share = async () => {
    setBusy(true);
    try {
      const r = await socialApi.sharePost(post.id, caption.trim());
      update(post.id, (p) => ({ ...p, share_count: r.data.share.share_count }));
      toast.success("Post shared. It now appears in your shares.");
      setCaption("");
      onClose();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal open={open} onClose={onClose} title="Share post" size="sm" footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button loading={busy} onClick={share} icon={<Repeat2 className="h-4 w-4" />}>Share</Button></>}>
      <Textarea label="Add a caption (optional)" maxLength={500} rows={3} value={caption} onChange={(e) => setCaption(e.target.value)} />
      <p className="mt-3 text-xs text-slate-500">Sharing links to the original post by {post.author.full_name}; its author and privacy settings stay in control.</p>
    </Modal>
  );
}

export function PostCard({ post, defaultShowComments = false }: { post: Post; defaultShowComments?: boolean }) {
  const confirm = useConfirm();
  const { update } = usePostCache();
  const [showComments, setShowComments] = useState(defaultShowComments);
  const [editing, setEditing] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [liking, setLiking] = useState(false);

  const toggleLike = async () => {
    if (liking) return;
    setLiking(true);
    const before = { is_liked: post.is_liked, like_count: post.like_count };
    update(post.id, (p) => ({ ...p, is_liked: !before.is_liked, like_count: before.like_count + (before.is_liked ? -1 : 1) }));
    try {
      const r = before.is_liked ? await socialApi.unlike(post.id) : await socialApi.like(post.id);
      update(post.id, (p) => ({ ...p, ...r.data }));
    } catch (error) {
      update(post.id, (p) => ({ ...p, ...before }));
      toast.error(errorMessage(error));
    } finally {
      setLiking(false);
    }
  };

  const remove = async () => {
    if (!(await confirm({ title: "Delete this post?", description: "The post, its photos and its comments will no longer be visible.", confirmLabel: "Delete post" }))) return;
    try {
      await socialApi.deletePost(post.id);
      update(post.id, () => null);
      toast.success("Post deleted.");
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  const shareable = post.visibility === "public" || post.visibility === "members_only";

  return (
    <article className="card p-4 sm:p-5">
      <header className="flex items-start gap-3">
        <Link to={`/profile/${post.author.id}`} className="shrink-0"><Avatar src={post.author.profile_picture} name={post.author.full_name} /></Link>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2">
            <Link to={`/profile/${post.author.id}`} className="font-semibold text-slate-900 hover:underline">{post.author.full_name}</Link>
            {post.shared_type && <span className="text-sm text-slate-500">shared {post.shared_type === "announcement" ? "an announcement" : "an achievement"}</span>}
          </div>
          <div className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500">
            <Link to={`/social/posts/${post.id}`} className="hover:underline"><time dateTime={post.created_at} title={formatDateTime(post.created_at)}>{timeAgo(post.created_at)}</time></Link>
            {post.is_edited && <span>· Edited</span>}
            <span>·</span>
            <VisibilityIcon visibility={post.visibility} />
            {post.post_type !== "general" && !post.shared_type && <Badge tone="brand" className="ml-1 py-0.5">{postTypeLabels[post.post_type]}</Badge>}
          </div>
        </div>
        <Menu
          label="Post actions"
          items={[
            { label: "Edit post", icon: <Pencil className="h-4 w-4" />, onSelect: () => setEditing(true), hidden: !post.is_owner },
            { label: "Delete post", icon: <Trash2 className="h-4 w-4" />, onSelect: remove, danger: true, hidden: !post.is_owner },
            { label: "Report post", icon: <Flag className="h-4 w-4" />, onSelect: () => setReporting(true), hidden: post.is_owner },
          ]}
        />
      </header>

      {post.content && <p className="prose-plain mt-3 text-[15px] leading-relaxed text-slate-800">{post.content}</p>}
      <MediaGrid media={post.media} />
      {post.shared_resource && <SharedResourceCard resource={post.shared_resource} />}

      {(post.like_count > 0 || post.comment_count > 0 || post.share_count > 0) && (
        <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
          <span>{post.like_count > 0 && <span className="inline-flex items-center gap-1"><span className="flex h-4 w-4 items-center justify-center rounded-full bg-rose-500"><Heart className="h-2.5 w-2.5 fill-white text-white" /></span>{post.like_count}</span>}</span>
          <span className="space-x-3">
            {post.comment_count > 0 && <button onClick={() => setShowComments(true)} className="hover:underline">{post.comment_count} comment{post.comment_count === 1 ? "" : "s"}</button>}
            {post.share_count > 0 && <span>{post.share_count} share{post.share_count === 1 ? "" : "s"}</span>}
          </span>
        </div>
      )}

      <div className="mt-3 grid grid-cols-3 gap-1 border-t border-slate-100 pt-2">
        <button onClick={toggleLike} aria-pressed={post.is_liked} className={cn("inline-flex items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium transition hover:bg-slate-50", post.is_liked ? "text-rose-600" : "text-slate-600")}>
          <Heart className={cn("h-[18px] w-[18px]", post.is_liked && "fill-current")} /> Like
        </button>
        <button onClick={() => setShowComments((s) => !s)} aria-expanded={showComments} className="inline-flex items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-50">
          <MessageCircle className="h-[18px] w-[18px]" /> Comment
        </button>
        <button
          onClick={() => (shareable ? setSharing(true) : toast.info(`${visibilityLabels[post.visibility]} posts cannot be shared.`))}
          disabled={post.is_owner && !shareable}
          className="inline-flex items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-50 disabled:opacity-40"
        >
          <Repeat2 className="h-[18px] w-[18px]" /> Share
        </button>
      </div>

      {showComments && <div className="mt-2"><CommentSection postId={post.id} /></div>}

      {editing && <EditPostDialog post={post} open={editing} onClose={() => setEditing(false)} />}
      <ShareDialog post={post} open={sharing} onClose={() => setSharing(false)} />
      <ReportDialog open={reporting} onClose={() => setReporting(false)} title="Report post" reasons={socialReportReasons} onSubmit={(r, d) => socialApi.report("post", post.id, r, d)} />
    </article>
  );
}
