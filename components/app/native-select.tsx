import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";

/**
 * A native <select> wearing the design system.
 *
 * The richer registry select is a listbox of buttons; this stays a real form
 * control on purpose. It keeps the platform picker, type-ahead, screen-reader
 * semantics and keyboard model, and it keeps the DOM contract that the desktop
 * regression specs drive with selectOption().
 */
export function NativeSelect({
  className = "",
  children,
  bare = false,
  ...props
}: React.ComponentProps<"select"> & { children: ReactNode; bare?: boolean }) {
  return (
    <div className={`relative flex min-w-0 items-center ${className}`}>
      <select
        {...props}
        className={`h-8 w-full min-w-0 appearance-none truncate rounded-[min(var(--radius-md),12px)] border border-input bg-card py-1 pl-2.5 text-sm text-foreground shadow-xs outline-none transition-colors focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40 disabled:cursor-not-allowed disabled:opacity-50 ${bare ? "pr-2.5" : "pr-8"}`}
      >
        {children}
      </select>
      {bare ? null : <ChevronDown aria-hidden className="pointer-events-none absolute right-2.5 size-3.5 text-muted-foreground" />}
    </div>
  );
}
