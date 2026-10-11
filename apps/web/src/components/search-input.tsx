import type { ComponentProps } from "react";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";

/** Shared height and shape for search, filter and subscription controls. */
export const PILL_CONTROL = "h-10 rounded-full border text-sm transition-colors";

type SearchInputProps = ComponentProps<"input"> & {
	wrapperClassName?: string;
};

export function SearchInput({ className, wrapperClassName, type = "text", ...props }: SearchInputProps) {
	return (
		<div className={cn("relative w-full", wrapperClassName)}>
			<Search aria-hidden="true" className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
			<input
				type={type}
				{...props}
				className={cn(
					PILL_CONTROL,
					"w-full border-border bg-card pl-10 pr-4 text-foreground outline-none placeholder:text-muted-foreground/70 focus:border-foreground/30 focus:bg-card",
					className,
				)}
			/>
		</div>
	);
}
