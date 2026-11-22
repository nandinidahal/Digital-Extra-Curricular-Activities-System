import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { CardSkeleton, ErrorState } from "@/components/common/Feedback";
import { PostCard } from "@/components/social/PostCard";
import { qk } from "@/hooks/queryKeys";
import { socialApi } from "@/services/api/social";

/** Single post (target of post.liked / post.commented / comment.replied notifications). */
export default function PostPage() {
  const { postId = "" } = useParams();
  const query = useQuery({ queryKey: qk.post(postId), queryFn: async () => (await socialApi.post(postId)).data.post });
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link to="/home" className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"><ArrowLeft className="h-4 w-4" /> Back to feed</Link>
      {query.isPending ? <CardSkeleton media /> : query.isError ? (
        <ErrorState error={query.error} title="This post is not available" />
      ) : (
        <PostCard post={query.data} defaultShowComments />
      )}
    </div>
  );
}
