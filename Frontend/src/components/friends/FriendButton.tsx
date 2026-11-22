import { useQueryClient } from "@tanstack/react-query";
import { Check, Clock, UserCheck, UserMinus, UserPlus, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/common/Button";
import { useConfirm } from "@/components/common/Modal";
import { errorMessage } from "@/services/api/errors";
import { friendsApi } from "@/services/api/friends";
import type { FriendshipStatus } from "@/types/api";

/**
 * The right action for the CURRENT relationship (from GET /api/friends/status/<id>/ or the
 * discover list). Every action goes to the backend; the backend decides what is allowed.
 */
export function FriendButton({ userId, name, status, requestId, onChange, size = "md" }: {
  userId: string; name: string; status: FriendshipStatus; requestId?: string | null;
  onChange?: () => void; size?: "sm" | "md";
}) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [busy, setBusy] = useState(false);

  const run = async (action: () => Promise<{ message: string }>) => {
    setBusy(true);
    try {
      const result = await action();
      toast.success(result.message);
      await queryClient.invalidateQueries({ queryKey: ["friends"] });
      onChange?.();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  switch (status) {
    case "self":
      return null;
    case "friends":
      return (
        <div className="flex gap-2">
          <Button size={size} variant="subtle" icon={<UserCheck className="h-4 w-4" />} disabled>Friends</Button>
          <Button
            size={size}
            variant="outline"
            loading={busy}
            icon={<UserMinus className="h-4 w-4" />}
            onClick={async () => {
              if (await confirm({ title: `Remove ${name} from friends?`, description: "You can send a new request later.", confirmLabel: "Remove friend" })) {
                void run(() => friendsApi.remove(userId));
              }
            }}
          >
            Remove
          </Button>
        </div>
      );
    case "request_sent":
      return (
        <Button size={size} variant="outline" loading={busy} icon={<Clock className="h-4 w-4" />} onClick={() => requestId && run(() => friendsApi.cancel(requestId))} title="Cancel request">
          Request sent · Cancel
        </Button>
      );
    case "request_received":
      return (
        <div className="flex gap-2">
          <Button size={size} loading={busy} icon={<Check className="h-4 w-4" />} onClick={() => requestId && run(() => friendsApi.accept(requestId))}>Accept</Button>
          <Button size={size} variant="outline" disabled={busy} icon={<X className="h-4 w-4" />} onClick={() => requestId && run(() => friendsApi.reject(requestId))}>Reject</Button>
        </div>
      );
    case "blocked_by_me":
      return <Button size={size} variant="outline" loading={busy} onClick={() => run(() => friendsApi.unblock(userId))}>Unblock</Button>;
    case "blocked_you":
      return null;
    default:
      return <Button size={size} loading={busy} icon={<UserPlus className="h-4 w-4" />} onClick={() => run(() => friendsApi.send(userId))}>Add friend</Button>;
  }
}
