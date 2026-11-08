import { cn } from "cn";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

/**
 * The application shell: a floating navigation rail on a pale canvas, with the
 * screen content in the remaining column. Navigation is a real <nav> with
 * aria-current on the active item; the rail itself is not a landmark wrapper,
 * so screen readers reach the content with one jump.
 */
export function AppShell({
  brand,
  navigation,
  status,
  skipLink,
  children,
}: {
  brand: ReactNode;
  navigation: ReactNode;
  status?: ReactNode;
  skipLink?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-canvas">
      {/* The skip link is first in the DOM so it is the very first tab stop. */}
      {skipLink}
      <div className="mx-auto flex w-full max-w-[104rem] gap-6 px-4 py-4 lg:px-8 lg:py-8">
        <aside className="sticky top-4 hidden h-[calc(100vh-2rem)] w-64 shrink-0 flex-col rounded-card bg-card p-3 shadow-[var(--shadow-card)] lg:top-8 lg:flex lg:h-[calc(100vh-4rem)]">
          {brand}
          <nav aria-label="Workspaces" className="mt-4 flex-1 overflow-y-auto pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">{navigation}</nav>
          {status ? <div className="mt-3 border-t border-border pt-3">{status}</div> : null}
        </aside>
        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </div>
  );
}

export function Brand({
  title,
  subtitle,
  icon: Icon,
}: {
  title: string;
  subtitle: string;
  icon: LucideIcon;
}) {
  return (
    <div className="flex items-center gap-3 px-2 py-2">
      <span className="flex size-9 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-sm">
        <Icon aria-hidden className="size-4" />
      </span>
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold tracking-tight">{title}</span>
        <span className="block truncate text-xs text-muted-foreground">{subtitle}</span>
      </span>
    </div>
  );
}

export function NavGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="mb-3 last:mb-0">
      <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </p>
      <ul className="flex flex-col gap-0.5">{children}</ul>
    </div>
  );
}

export function NavItem({
  label,
  accessibleName,
  icon: Icon,
  active,
  disabled,
  badge,
  onSelect,
}: {
  label: string;
  accessibleName?: string;
  icon: LucideIcon;
  active?: boolean;
  disabled?: boolean;
  badge?: ReactNode;
  onSelect: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        aria-label={accessibleName}
        aria-current={active ? "page" : undefined}
        disabled={disabled}
        onClick={onSelect}
        className={cn(
          "group flex w-full items-center gap-2.5 rounded-full px-3 py-1.5 text-left text-sm transition-colors",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
          active
            ? "bg-primary font-medium text-primary-foreground shadow-sm"
            : "text-foreground/85 hover:bg-accent hover:text-foreground",
          disabled && "cursor-wait opacity-60",
        )}
      >
        <Icon aria-hidden className="size-4 shrink-0" />
        <span className="min-w-0 flex-1 truncate">{label}</span>
        {badge}
      </button>
    </li>
  );
}

export function StatusChip({
  tone,
  label,
  detail,
}: {
  tone: "ready" | "pending" | "error";
  label: string;
  detail?: string;
}) {
  const dot =
    tone === "ready"
      ? "bg-success"
      : tone === "pending"
        ? "bg-warning"
        : "bg-destructive";
  return (
    <div className="flex items-start gap-2 rounded-full bg-muted px-3 py-2">
      <span aria-hidden className={cn("mt-1.5 size-2 shrink-0 rounded-full", dot)} />
      <span className="min-w-0">
        <span className="block text-xs font-medium leading-tight">{label}</span>
        {detail ? (
          <span className="block truncate text-[11px] leading-tight text-muted-foreground">
            {detail}
          </span>
        ) : null}
      </span>
    </div>
  );
}
