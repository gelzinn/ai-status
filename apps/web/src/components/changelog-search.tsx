import { SearchInput } from "@/components/search-input";

export function ChangelogSearch({ query }: { query: string }) {
	return (
		<form action="/changelog" method="get" role="search" className="changelog-search">
			<SearchInput
				key={query}
				type="search"
				name="q"
				defaultValue={query}
				placeholder="Search releases…"
				aria-label="Search releases"
			/>
		</form>
	);
}
