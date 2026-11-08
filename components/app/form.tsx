import { cn } from "cn";
import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";

/**
 * Form and content primitives shared by every screen.
 *
 * The native controls are deliberate. The desktop regression specs drive these
 * fields by label and by `selectOption()`, so labels stay real <label> elements
 * wrapped around the control and selects stay real <select> elements. Nothing
 * here renames a control: the label text is the accessible name.
 */
export function Field({
  label,
  children,
  className,
}: {
  label: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("m-0 flex min-w-0 flex-col gap-1.5", className)}>
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      {children}
    </label>
  );
}

export function CheckField({
  checked,
  onChange,
  disabled,
  children,
  className,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("m-0 flex items-start gap-2 text-sm leading-relaxed", className)}>
      <input
        type="checkbox"
        className="mt-0.5 size-4 shrink-0 accent-primary"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="min-w-0">{children}</span>
    </label>
  );
}

/** A responsive row of fields; wraps instead of overflowing at narrow widths. */
export function Toolbar({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-end gap-x-4 gap-y-3", className)}>{children}</div>
  );
}

/** A horizontal group of related actions that wraps on narrow screens. */
export function Actions({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cn("flex flex-wrap items-center gap-2", className)}>{children}</div>;
}

/**
 * Tables carry dense evidence and must stay readable: one frame supplies the
 * border, scroll container and cell rhythm so no screen re-invents them.
 */
export function DataTable({
  children,
  className,
  label,
}: {
  children: ReactNode;
  className?: string;
  label?: string;
}) {
  return (
    <div className={cn("data-table overflow-x-auto rounded-xl border border-border", className)} aria-label={label}>
      <table>{children}</table>
    </div>
  );
}

/**
 * A native disclosure. Specs expand these by pressing Enter on the summary
 * text, so the summary stays the real interactive element.
 */
export function Disclosure({
  title,
  children,
  className,
  summaryClassName,
  ...rest
}: {
  title: ReactNode;
  children: ReactNode;
  className?: string;
  summaryClassName?: string;
} & React.ComponentProps<"details">) {
  return (
    <details
      className={cn("group rounded-xl border border-border bg-muted/40 px-4 py-3", className)}
      {...rest}
    >
      <summary
        className={cn(
          "flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-foreground marker:hidden",
          summaryClassName,
        )}
      >
        {title}
        <ChevronDown
          aria-hidden
          className="ml-auto size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
        />
      </summary>
      <div className="mt-3 flex min-w-0 flex-col gap-2 text-sm leading-relaxed">{children}</div>
    </details>
  );
}

/** Small descriptive paragraph used under headings and around controls. */
export function Hint({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={cn("text-xs leading-relaxed text-muted-foreground", className)}>{children}</p>
  );
}

/** A sub-section heading inside a panel. */
export function SubHeading({
  children,
  className,
  as: Tag = "h4",
  ...rest
}: {
  children: ReactNode;
  className?: string;
  as?: "h3" | "h4" | "h5" | "h6";
} & React.ComponentProps<"h4">) {
  return (
    <Tag className={cn("text-sm font-semibold tracking-tight text-foreground", className)} {...rest}>
      {children}
    </Tag>
  );
}
