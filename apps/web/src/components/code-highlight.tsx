import { highlightToReact } from "@/lib/highlight";
import { CodeBlock } from "./code-block";

export async function HighlightedCodeBlock({
	code,
	lang,
	label,
	className,
}: {
	code: string;
	lang: string;
	label?: React.ReactNode;
	className?: string;
}) {
	const highlighted = await highlightToReact(code, lang);

	return (
		<CodeBlock code={code} label={label} className={className}>
			{highlighted}
		</CodeBlock>
	);
}
