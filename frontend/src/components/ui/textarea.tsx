import * as React from "react";

import { cn } from "@/lib/utils";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        // DESIGN_SYSTEM.md §13: control surface + hairline border; the global
        // :focus-visible ring is the only focus treatment.
        "border-hairline bg-control placeholder:text-tertiary aria-invalid:border-destructive flex field-sizing-content min-h-16 w-full rounded-lg border px-2.5 py-2 text-base transition-colors outline-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
        className
      )}
      {...props}
    />
  );
}

export { Textarea };
