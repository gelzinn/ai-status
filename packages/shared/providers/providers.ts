import data from './providers.json';

export const PROVIDERS = Object.fromEntries(
	Object.entries(data).map(([key, value]) => [
		key.toUpperCase(),
		value,
	])
);

export type Provider = (typeof PROVIDERS)[keyof typeof PROVIDERS];

export const SUPPORTED_PROVIDERS: Provider[] = Object.values(PROVIDERS);
