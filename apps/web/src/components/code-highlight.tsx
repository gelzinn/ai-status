import { codeToHtml } from "shiki";
import { CodeBlock } from "./code-block";

export async function HighlightedCodeBlock({
	code,
	lang,
	label,
	className,
}: {
	code: string;
	lang: any;
	label?: React.ReactNode;
	className?: string;
}) {
	const html = await codeToHtml(code, {
		lang,
		theme: "vesper", // Premium dark theme
	});

	return (
		<CodeBlock code={code} html={html} label={label} className={className}>
			{code}
		</CodeBlock>
	);
}
