import * as React from "react"

import { cn } from "@/lib/utils"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        // DESIGN_SYSTEM.md §13: control surface + hairline border; the global
        // :focus-visible ring is the only focus treatment.
        "flex field-sizing-content min-h-16 w-full rounded-lg border border-hairline bg-control px-2.5 py-2 text-base transition-colors outline-none placeholder:text-tertiary disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive md:text-sm",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
