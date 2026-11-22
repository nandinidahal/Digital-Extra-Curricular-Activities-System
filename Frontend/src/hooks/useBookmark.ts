import { useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { announcementsApi } from "@/services/api/announcements";
import { errorMessage } from "@/services/api/errors";
import type { AnnouncementCard, AnnouncementDetail, Paginated } from "@/types/api";

/** Toggle a bookmark and patch every cached announcement list/detail. */
export function useBookmark() {
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<string | null>(null);

  const patch = (id: string, value: boolean) => {
    queryClient.setQueriesData<InfiniteData<Paginated<AnnouncementCard>>>({ queryKey: ["announcements", "list"] }, (data) =>
      data && "pages" in data
        ? { ...data, pages: data.pages.map((p) => ({ ...p, results: p.results.map((a) => (a.id === id ? { ...a, is_bookmarked: value } : a)) })) }
        : data,
    );
    queryClient.setQueryData<AnnouncementDetail>(["announcements", "detail", id], (a) => (a ? { ...a, is_bookmarked: value } : a));
  };

  const toggle = async (announcement: Pick<AnnouncementCard, "id" | "is_bookmarked">) => {
    const next = !announcement.is_bookmarked;
    setPending(announcement.id);
    patch(announcement.id, next);
    try {
      if (next) await announcementsApi.bookmark(announcement.id);
      else await announcementsApi.unbookmark(announcement.id);
      toast.success(next ? "Saved to your bookmarks." : "Removed from bookmarks.");
      void queryClient.invalidateQueries({ queryKey: ["announcements", "bookmarks"] });
    } catch (error) {
      patch(announcement.id, !next);
      toast.error(errorMessage(error));
    } finally {
      setPending(null);
    }
  };

  return { toggle, pending };
}
