export const LLM_TRANSLATION_PROVIDERS = ["openai", "claude", "ollama", "openai_compatible"] as const;

export const DEFAULT_TRANSLATION_OPTIONS = {
  timeoutSeconds: 90,
  cacheEnabled: true,
  cacheMode: "text_with_context",
  maxRetries: 2,
  retryBackoffSeconds: 2,
  temperature: 0.1,
  topP: 0.95,
  maxTokens: 4096,
} as const;

export interface TranslationProviderCapabilities {
  llmOptions: boolean;
  modelPicker: boolean;
  visionContext: boolean;
  systemPrompt: boolean;
}

export function isLlmTranslationProvider(provider: string): boolean {
  return LLM_TRANSLATION_PROVIDERS.includes(provider as (typeof LLM_TRANSLATION_PROVIDERS)[number]);
}

export function getTranslationProviderCapabilities(provider: string): TranslationProviderCapabilities {
  const llm = isLlmTranslationProvider(provider);
  return {
    llmOptions: llm,
    modelPicker: llm,
    visionContext: llm,
    systemPrompt: llm,
  };
}
