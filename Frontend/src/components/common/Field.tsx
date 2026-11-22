import { Eye, EyeOff, X } from "lucide-react";
import { forwardRef, useId, useState, type InputHTMLAttributes, type KeyboardEvent, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn } from "@/utils/cn";

interface FieldProps {
  label?: ReactNode;
  error?: string;
  hint?: ReactNode;
  required?: boolean;
  className?: string;
  children: (id: string, describedBy: string | undefined) => ReactNode;
}

export function Field({ label, error, hint, required, className, children }: FieldProps) {
  const id = useId();
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className={className}>
      {label && (
        <label htmlFor={id} className="label">
          {label}
          {required && <span className="ml-0.5 text-rose-500" aria-hidden>*</span>}
        </label>
      )}
      {children(id, describedBy)}
      {error ? (
        <p id={`${id}-error`} role="alert" className="mt-1.5 text-xs font-medium text-rose-600">{error}</p>
      ) : hint ? (
        <p id={`${id}-hint`} className="mt-1.5 text-xs text-slate-500">{hint}</p>
      ) : null}
    </div>
  );
}

type InputProps = InputHTMLAttributes<HTMLInputElement> & { label?: ReactNode; error?: string; hint?: ReactNode; wrapperClassName?: string };

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, hint, required, wrapperClassName, className, ...rest },
  ref,
) {
  return (
    <Field label={label} error={error} hint={hint} required={required} className={wrapperClassName}>
      {(id, describedBy) => (
        <input
          ref={ref}
          id={id}
          aria-invalid={!!error || undefined}
          aria-describedby={describedBy}
          required={required}
          className={cn("input", error && "input-invalid", className)}
          {...rest}
        />
      )}
    </Field>
  );
});

export const PasswordInput = forwardRef<HTMLInputElement, InputProps>(function PasswordInput(
  { label, error, hint, required, wrapperClassName, className, ...rest },
  ref,
) {
  const [visible, setVisible] = useState(false);
  return (
    <Field label={label} error={error} hint={hint} required={required} className={wrapperClassName}>
      {(id, describedBy) => (
        <div className="relative">
          <input
            ref={ref}
            id={id}
            type={visible ? "text" : "password"}
            aria-invalid={!!error || undefined}
            aria-describedby={describedBy}
            className={cn("input pr-11", error && "input-invalid", className)}
            {...rest}
          />
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-slate-400 hover:text-slate-700"
            aria-label={visible ? "Hide password" : "Show password"}
          >
            {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
      )}
    </Field>
  );
});

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: ReactNode; error?: string; hint?: ReactNode; wrapperClassName?: string };

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, error, hint, required, wrapperClassName, className, rows = 4, ...rest },
  ref,
) {
  return (
    <Field label={label} error={error} hint={hint} required={required} className={wrapperClassName}>
      {(id, describedBy) => (
        <textarea
          ref={ref}
          id={id}
          rows={rows}
          aria-invalid={!!error || undefined}
          aria-describedby={describedBy}
          className={cn("input resize-y leading-relaxed", error && "input-invalid", className)}
          {...rest}
        />
      )}
    </Field>
  );
});

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label?: ReactNode; error?: string; hint?: ReactNode; wrapperClassName?: string;
  options: { value: string; label: string }[];
  placeholder?: string;
};

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, error, hint, required, wrapperClassName, className, options, placeholder, ...rest },
  ref,
) {
  return (
    <Field label={label} error={error} hint={hint} required={required} className={wrapperClassName}>
      {(id, describedBy) => (
        <select
          ref={ref}
          id={id}
          aria-invalid={!!error || undefined}
          aria-describedby={describedBy}
          className={cn("input pr-9", error && "input-invalid", className)}
          {...rest}
        >
          {placeholder !== undefined && <option value="">{placeholder}</option>}
          {options.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      )}
    </Field>
  );
});

export function Toggle({ checked, onChange, label, description, disabled }: {
  checked: boolean; onChange: (value: boolean) => void; label: ReactNode; description?: ReactNode; disabled?: boolean;
}) {
  const id = useId();
  return (
    <div className="flex items-start justify-between gap-4 py-3">
      <div className="min-w-0">
        <label htmlFor={id} className="text-sm font-medium text-slate-800">{label}</label>
        {description && <p className="mt-0.5 text-xs text-slate-500">{description}</p>}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-50",
          checked ? "bg-brand-600" : "bg-slate-300",
        )}
      >
        <span className={cn("inline-block h-5 w-5 rounded-full bg-white shadow transition-transform", checked ? "translate-x-5" : "translate-x-0.5")} />
      </button>
    </div>
  );
}

/** Small chip editor for lists of short strings (skills, interests). */
export function TagInput({ value, onChange, label, hint, max = 20, maxLength = 40, placeholder = "Type and press Enter", error }: {
  value: string[]; onChange: (tags: string[]) => void; label?: ReactNode; hint?: ReactNode; max?: number; maxLength?: number; placeholder?: string; error?: string;
}) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const tag = draft.trim().slice(0, maxLength);
    if (!tag || value.length >= max || value.some((t) => t.toLowerCase() === tag.toLowerCase())) {
      setDraft("");
      return;
    }
    onChange([...value, tag]);
    setDraft("");
  };
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add();
    } else if (e.key === "Backspace" && !draft && value.length) {
      onChange(value.slice(0, -1));
    }
  };
  return (
    <Field label={label} hint={hint ?? `${value.length}/${max}`} error={error}>
      {(id, describedBy) => (
        <div className={cn("input flex min-h-11 flex-wrap items-center gap-1.5 py-1.5", error && "input-invalid")}>
          {value.map((tag) => (
            <span key={tag} className="chip bg-brand-50 text-brand-800">
              {tag}
              <button type="button" onClick={() => onChange(value.filter((t) => t !== tag))} aria-label={`Remove ${tag}`} className="rounded-full hover:text-brand-950">
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
          <input
            id={id}
            aria-describedby={describedBy}
            value={draft}
            maxLength={maxLength}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKey}
            onBlur={add}
            placeholder={value.length >= max ? "" : placeholder}
            disabled={value.length >= max}
            className="min-w-[8rem] flex-1 border-0 bg-transparent p-1 text-sm outline-none focus:ring-0"
          />
        </div>
      )}
    </Field>
  );
}
