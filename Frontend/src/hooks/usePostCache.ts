import { useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { useCallback } from "react";
import type { Paginated, Post } from "@/types/api";

/** Patch or remove one post in every cached feed/list/detail, so the UI updates instantly. */
export function usePostCache() {
  const queryClient = useQueryClient();

  const update = useCallback((postId: string, patch: (post: Post) => Post | null) => {
    queryClient.setQueriesData<InfiniteData<Paginated<Post>>>({ queryKey: ["social"] }, (data) => {
      if (!data || !("pages" in data)) return data;
      return {
        ...data,
        pages: data.pages.map((page) => ({
          ...page,
          results: page.results.flatMap((p) => {
            if (p.id !== postId) return [p];
            const next = patch(p);
            return next ? [next] : [];
          }),
        })),
      };
    });
    queryClient.setQueriesData<Post>({ queryKey: ["social", "post", postId] }, (post) => (post ? patch(post) ?? post : post));
  }, [queryClient]);

  const refresh = useCallback(() => queryClient.invalidateQueries({ queryKey: ["social"] }), [queryClient]);

  return { update, refresh };
}
