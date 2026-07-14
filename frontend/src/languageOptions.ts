export const SUPPORTED_TRANSLATION_LANGUAGES = [
  { value: "Japanese", label: "Japanese" },
  { value: "English", label: "English" },
  { value: "Korean", label: "Korean" },
] as const;

export function getTargetLanguageOptions(sourceLanguage: string) {
  return SUPPORTED_TRANSLATION_LANGUAGES.filter((language) => language.value !== sourceLanguage);
}

export function getSafeTargetLanguage(sourceLanguage: string, targetLanguage: string) {
  const options = getTargetLanguageOptions(sourceLanguage);
  return options.some((language) => language.value === targetLanguage)
    ? targetLanguage
    : options[0].value;
}
