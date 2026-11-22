import { useMutation } from "@tanstack/react-query";
import { ImagePlus, Send } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Avatar } from "@/components/common/Avatar";
import { Button } from "@/components/common/Button";
import { FilePicker } from "@/components/common/FilePicker";
import { useAuth } from "@/contexts/AuthContext";
import { usePostCache } from "@/hooks/usePostCache";
import { errorMessage } from "@/services/api/errors";
import { socialApi } from "@/services/api/social";
import type { PostType, PostVisibility } from "@/types/api";
import { checkImage, IMAGE_ACCEPT, LIMITS } from "@/utils/files";
import { postTypeLabels, visibilityLabels } from "@/utils/labels";

const MAX = 5000;

export function PostComposer() {
  const { user, profile } = useAuth();
  const { refresh } = usePostCache();
  const [content, setContent] = useState("");
  const [images, setImages] = useState<File[]>([]);
  const [postType, setPostType] = useState<PostType>("general");
  const [visibility, setVisibility] = useState<PostVisibility>("public");
  const [showImages, setShowImages] = useState(false);

  const create = useMutation({
    mutationFn: () => socialApi.createPost({ content: content.trim(), post_type: postType, visibility, images }),
    onSuccess: (result) => {
      toast.success(result.message || "Post created.");
      setContent("");
      setImages([]);
      setShowImages(false);
      void refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const canPost = (content.trim().length > 0 || images.length > 0) && content.length <= MAX && !create.isPending;

  return (
    <section className="card p-4 sm:p-5" aria-label="Create a post">
      <div className="flex gap-3">
        <Link to="/profile" className="shrink-0"><Avatar src={profile?.profile_picture} name={user?.full_name} /></Link>
        <div className="min-w-0 flex-1">
          <label htmlFor="composer" className="sr-only">What did you do today?</label>
          <textarea
            id="composer"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={content ? 4 : 2}
            maxLength={MAX}
            placeholder={`Share an activity or experience, ${user?.full_name.split(" ")[0] ?? ""}…`}
            className="w-full resize-none rounded-xl border-0 bg-slate-50 px-4 py-3 text-[15px] placeholder:text-slate-400 focus:bg-white focus:ring-2 focus:ring-brand-200 focus:outline-none"
          />
          {(showImages || images.length > 0) && (
            <div className="mt-3">
              <FilePicker files={images} onChange={setImages} accept={IMAGE_ACCEPT} max={LIMITS.postImages} validate={(f) => checkImage(f, LIMITS.postImage)} label="Add photos (JPEG, PNG, WebP · up to 6)" />
            </div>
          )}
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <button type="button" onClick={() => setShowImages((v) => !v)} className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100">
                <ImagePlus className="h-4 w-4 text-emerald-600" /> Photo
              </button>
              <select aria-label="Post type" value={postType} onChange={(e) => setPostType(e.target.value as PostType)} className="rounded-lg border-0 bg-slate-100 py-1.5 pr-8 pl-2.5 text-sm text-slate-700 focus:ring-2 focus:ring-brand-200">
                {Object.entries(postTypeLabels).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <select aria-label="Who can see this post" value={visibility} onChange={(e) => setVisibility(e.target.value as PostVisibility)} className="rounded-lg border-0 bg-slate-100 py-1.5 pr-8 pl-2.5 text-sm text-slate-700 focus:ring-2 focus:ring-brand-200">
                {Object.entries(visibilityLabels).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div className="flex items-center gap-3">
              {content.length > MAX - 300 && <span className="text-xs text-slate-400">{content.length}/{MAX}</span>}
              <Button onClick={() => create.mutate()} disabled={!canPost} loading={create.isPending} icon={<Send className="h-4 w-4" />}>Post</Button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
