import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/common/Button";
import { Select, Textarea } from "@/components/common/Field";
import { Modal } from "@/components/common/Modal";
import { errorMessage } from "@/services/api/errors";

/** Generic report dialog; `reasons` comes from the backend's choice list for that module. */
export function ReportDialog<R extends string>({ open, onClose, title, reasons, onSubmit }: {
  open: boolean; onClose: () => void; title: string; reasons: Record<R, string>;
  onSubmit: (reason: R, description: string) => Promise<unknown>;
}) {
  const keys = Object.keys(reasons) as R[];
  const [reason, setReason] = useState<R>(keys[0]);
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      await onSubmit(reason, description.trim());
      toast.success("Thanks. Your report was submitted and will be reviewed.");
      setDescription("");
      onClose();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      description="Reports are private. Moderators review them and take action when needed."
      size="sm"
      footer={<><Button variant="outline" onClick={onClose}>Cancel</Button><Button variant="danger" loading={busy} onClick={submit}>Submit report</Button></>}
    >
      <div className="space-y-4">
        <Select label="Reason" value={reason} onChange={(e) => setReason(e.target.value as R)} options={keys.map((k) => ({ value: k, label: reasons[k] }))} />
        <Textarea label="Details (optional)" maxLength={1000} rows={3} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Add anything that helps moderators understand the problem." />
      </div>
    </Modal>
  );
}
