import { PROVIDERS as sharedProviders, type Provider as SharedProvider } from "@ai-status/shared";

export type ProviderCategory = "assistants" | "apis" | "cloud";
export type Provider = SharedProvider & { category: ProviderCategory };

// Categories describe the service being monitored, independently of how its
// credentials are read (for example, an API key stored by OpenCode).
const categories: Record<string, ProviderCategory> = {
  claude: "assistants",
  codex: "assistants",
  opencode: "assistants",
  antigravity: "assistants",
  copilot: "assistants",
  zai: "assistants",
  kiro: "assistants",
  commandcode: "assistants",
  "anthropic-api": "apis",
  "openai-api": "apis",
  "google-cloud": "cloud",
  openrouter: "apis",
  deepseek: "apis",
  deepinfra: "apis",
  kimi: "assistants",
  minimax: "assistants",
  kilo: "assistants",
  lyceum: "apis",
  novita: "apis",
  moonshot: "apis",
  grok: "apis",
  supergrok: "assistants",
  "grok-bot": "assistants",
  cursor: "assistants",
  nous: "assistants",
  ollama: "cloud",
  orcarouter: "apis",
  modelstudio: "cloud",
  devin: "assistants",
};

// These bundled logos have opaque backgrounds so their black glyphs remain
// visible on both light and dark website surfaces, including app previews.
const localLogos: Record<string, string> = {
  kilo: "/providers/kilo.png",
  lyceum: "/providers/lyceum.png",
};

export const PROVIDERS: Record<string, Provider> = Object.fromEntries(
  Object.entries(sharedProviders).map(([key, provider]) => [
    key,
    {
      ...provider,
      logo: localLogos[provider.slug] ?? provider.logo,
      category: categories[provider.slug],
    },
  ]),
);

export const SUPPORTED_PROVIDERS: Provider[] = Object.values(PROVIDERS);
