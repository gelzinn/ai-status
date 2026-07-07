export const PROVIDERS = {
	OPENCODE: { name: "OpenCode", logo: "https://svgl.app/library/opencode-dark.svg" },
	COPILOT: { name: "Copilot", logo: "https://svgl.app/library/copilot_dark.svg" },
	CLAUDE: { name: "Claude", logo: "https://svgl.app/library/claude-ai-icon.svg" },
	CODEX: { name: "Codex", logo: "https://svgl.app/library/codex_dark.svg" },
	ANTIGRAVITY: { name: "Antigravity", logo: "https://svgl.app/library/antigravity.svg" },
	Z_AI: { name: "Z.AI", logo: "https://z-cdn.chatglm.cn/z-ai/static/logo.svg" },
	KIRO: { name: "Kiro", logo: "https://www.google.com/s2/favicons?sz=64&domain=kiro.dev" },
};

export type Provider = (typeof PROVIDERS)[keyof typeof PROVIDERS];

export const SUPPORTED_PROVIDERS: Provider[] = Object.values(PROVIDERS);
