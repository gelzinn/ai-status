"use client";

import { Check, Copy } from "lucide-react";
import { type ReactNode, useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import { cn } from "@/lib/utils";
import { IconFade } from "./icon-fade";

/** Copy button with cross-faded icon + label so the copied state morphs instead of snapping. */
export function CopyButton({
	copied,
	onCopy,
	subject,
	className,
}: {
	copied: boolean;
	onCopy: () => void;
	/** For the aria-label: "Copy code" / "Copy command". */
	subject: string;
	className?: string;
}) {
	return (
		<button
			type="button"
			onClick={onCopy}
			aria-label={copied ? `Copied ${subject}` : `Copy ${subject}`}
			className={cn(
				"flex items-center gap-2 rounded-md px-2 py-1.5 text-xs text-muted-foreground outline-none transition-all duration-150 hover:bg-muted hover:text-foreground focus-visible:bg-muted focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-[0.97]",
				className,
			)}
		>
			<span className="relative flex items-center justify-center">
				<AnimatePresence mode="popLayout" initial={false}>
					<motion.span
						key={copied ? "copied" : "copy"}
						initial={{ opacity: 0, y: -8, filter: "blur(2px)" }}
						animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
						exit={{ opacity: 0, y: 8, filter: "blur(2px)" }}
						transition={{ type: "spring", bounce: 0, duration: 0.25 }}
					>
						{copied ? "Copied" : "Copy"}
					</motion.span>
				</AnimatePresence>
			</span>
			<span className="relative size-3.5 shrink-0">
				<IconFade show={copied}>
					<Check className="size-full" />
				</IconFade>
				<IconFade show={!copied}>
					<Copy className="size-full" />
				</IconFade>
			</span>
		</button>
	);
}

/** ponytail: hand-tinted spans instead of shiki — four static snippets don't earn a highlighter */
export function CodeBlock({
	label,
	actions,
	code,
	html,
	children,
	className,
}: {
	label?: ReactNode;
	/** Right-side controls rendered before the copy button. */
	actions?: ReactNode;
	code: string;
	html?: string;
	children?: ReactNode;
	className?: string;
}) {
	const [copied, setCopied] = useState(false);
	const preRef = useRef<HTMLPreElement>(null);
	const [scrollState, setScrollState] = useState<"none" | "start" | "middle" | "end">("none");

	useEffect(() => {
		const el = preRef.current;
		if (!el) return;

		const checkScroll = () => {
			if (el.scrollWidth - el.clientWidth <= 2) {
				setScrollState("none");
			} else if (el.scrollLeft <= 2) {
				setScrollState("start");
			} else if (Math.ceil(el.scrollLeft + el.clientWidth) >= el.scrollWidth - 2) {
				setScrollState("end");
			} else {
				setScrollState("middle");
			}
		};

		checkScroll();
		el.addEventListener("scroll", checkScroll, { passive: true });
		
		const observer = new ResizeObserver(() => checkScroll());
		observer.observe(el);
		if (el.firstElementChild) {
			observer.observe(el.firstElementChild);
		}

		return () => {
			el.removeEventListener("scroll", checkScroll);
			observer.disconnect();
		};
	}, []);
	const copy = async () => {
		await navigator.clipboard.writeText(code);
		setCopied(true);
		setTimeout(() => setCopied(false), 1500);
	};

	return (
		<div
			className={`overflow-hidden rounded-2xl border border-border bg-card ${className ?? ""}`}
		>
			<div className="flex items-center justify-between border-b border-border py-2 pr-2 pl-4">
				<div className="font-mono text-xs text-muted-foreground">{label}</div>
				<div className="flex items-center gap-2">
					{actions}
					<CopyButton copied={copied} onCopy={copy} subject="code" />
				</div>
			</div>
			{html ? (
				<div
					ref={preRef as any}
					data-scroll={scrollState}
					className="scroll-fade-x overflow-x-auto font-mono text-[13px] leading-relaxed [&>pre]:bg-transparent! [&>pre]:p-4! [&>pre]:m-0! [&>pre]:font-mono! [&>pre]:overflow-visible! [&>pre]:w-max! [&>pre]:min-w-full! [&_code]:font-mono!"
					dangerouslySetInnerHTML={{ __html: html }}
				/>
			) : (
				<pre
					ref={preRef}
					data-scroll={scrollState}
					className="scroll-fade-x overflow-x-auto p-4 font-mono text-[13px] leading-relaxed"
				>
					<code>{children}</code>
				</pre>
			)}
		</div>
	);
}

export const dim = (text: string) => (
	<span className="text-muted-foreground">{text}</span>
);
