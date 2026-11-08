import { cn } from "cn";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/reui/alert";
import { Badge } from "@/components/reui/badge";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * One container family for the whole app: floating white cards on the canvas.
 * The soft shadow and 22px radius live here once, so no screen re-invents them.
 */
export function Panel({
  title,
  description,
  action,
  children,
  footer,
  className,
  contentClassName,
  label,
  ...rest
}: {
  title?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  contentClassName?: string;
  /** Landmark name. Set it only when the desktop specs address this region. */
  label?: string;
} & Omit<React.ComponentProps<"section">, "title">) {
  const panel = (
    <Card
      className={cn(
        "gap-0 overflow-hidden rounded-card border-0 bg-card py-0 shadow-[var(--shadow-card)]",
        className,
      )}
      {...(rest as object)}
      data-slot="panel"
    >
      {title || description || action ? (
        <CardHeader className="flex flex-row items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <CardTitle className="text-sm font-semibold tracking-tight">{title}</CardTitle>
            {description ? (
              <CardDescription className="mt-0.5 text-xs leading-relaxed">{description}</CardDescription>
            ) : null}
          </div>
          {action ? <CardAction className="shrink-0">{action}</CardAction> : null}
        </CardHeader>
      ) : null}
      <CardContent className={cn("px-5 py-4", contentClassName)}>{children}</CardContent>
      {footer ? (
        <div className="border-t border-border bg-muted/60 px-5 py-3 text-xs text-muted-foreground">
          {footer}
        </div>
      ) : null}
    </Card>
  );
  return label ? <section aria-label={label}>{panel}</section> : panel;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  headingRef,
  id,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  headingRef?: React.Ref<HTMLHeadingElement>;
  id?: string;
}) {
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">
            {eyebrow}
          </p>
        ) : null}
        <h1
          id={id}
          ref={headingRef}
          tabIndex={-1}
          className="text-balance text-2xl font-semibold tracking-tight text-foreground"
        >
          {title}
        </h1>
        {description ? (
          <p className="mt-1 max-w-3xl text-sm leading-relaxed text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}

export function Stat({
  label,
  value,
  hint,
  icon: Icon,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: LucideIcon;
  tone?: "neutral" | "success" | "warning" | "destructive" | "primary";
}) {
  const toneClass = {
    neutral: "text-muted-foreground",
    success: "text-success",
    warning: "text-warning",
    destructive: "text-destructive",
    primary: "text-primary",
  }[tone];
  return (
    <div className="rounded-card bg-card p-4 shadow-[var(--shadow-card)]">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        {Icon ? (
          <Icon aria-hidden className={cn("size-4 shrink-0", toneClass)} />
        ) : null}
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
      {hint ? <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

/**
 * Status is never carried by color alone: every badge states its meaning in
 * words, in addition to the tint.
 */
export function StateBadge({
  tone,
  children,
}: {
  tone: "success" | "warning" | "destructive" | "info" | "neutral";
  children: ReactNode;
}) {
  const variant = {
    success: "success-light",
    warning: "warning-light",
    destructive: "destructive-light",
    info: "info-light",
    neutral: "secondary",
  } as const;
  return (
    <Badge variant={variant[tone]} size="sm">
      {children}
    </Badge>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  description: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl bg-muted/60 px-6 py-10 text-center">
      {Icon ? (
        <span className="mb-1 flex size-10 items-center justify-center rounded-full bg-primary-wash text-primary">
          <Icon aria-hidden className="size-5" />
        </span>
      ) : null}
      <p className="text-sm font-medium">{title}</p>
      <p className="max-w-md text-xs leading-relaxed text-muted-foreground">{description}</p>
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

export function ErrorNote({
  title = "This did not complete",
  children,
}: {
  title?: string;
  children: ReactNode;
}) {
  return (
    <Alert variant="destructive" className="rounded-xl">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{children}</AlertDescription>
    </Alert>
  );
}

export function LoadingRows({ rows = 3, label = "Loading" }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-2">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-4 w-full max-w-xl" />
      ))}
    </div>
  );
}

export function KeyValue({ items }: { items: { label: string; value: ReactNode }[] }) {
  return (
    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2 xl:grid-cols-3">
      {items.map((item) => (
        <div key={item.label} className="min-w-0">
          <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            {item.label}
          </dt>
          <dd className="mt-0.5 break-words text-sm">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
