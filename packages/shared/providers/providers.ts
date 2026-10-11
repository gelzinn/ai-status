import data from './providers.json';

export type ProviderCategory = 'assistants' | 'apis' | 'cloud';

export interface Provider {
	name: string;
	logo: string;
	tracks: string;
	auth: string;
	authType: string;
	category: ProviderCategory;
	logoVariants?: { web?: string };
	slug: string;
}

function isProviderCategory(category: string): category is ProviderCategory {
	return category === 'assistants' || category === 'apis' || category === 'cloud';
}

export const PROVIDERS: Record<string, Provider> = Object.fromEntries(
	Object.entries(data).map(([key, value]) => {
		if (!isProviderCategory(value.category)) {
			throw new Error(`Invalid category for provider ${key}: ${value.category}`);
		}

		return [key.toUpperCase(), { ...value, category: value.category, slug: key }];
	})
);

export const SUPPORTED_PROVIDERS: Provider[] = Object.values(PROVIDERS);

export const WEB_PROVIDERS: Record<string, Provider> = Object.fromEntries(
	Object.entries(PROVIDERS).map(([key, provider]) => [
		key,
		{ ...provider, logo: provider.logoVariants?.web ?? provider.logo },
	])
);

export const WEB_SUPPORTED_PROVIDERS: Provider[] = Object.values(WEB_PROVIDERS);
