export type UiLanguage = "en" | "ko";

export type TranslationKey =
  | "app.title"
  | "toolbar.addImages"
  | "toolbar.menu"
  | "toolbar.newProject"
  | "toolbar.openProject"
  | "toolbar.saveProject"
  | "toolbar.translate"
  | "toolbar.translating"
  | "toolbar.translateCurrentPage"
  | "toolbar.translatePageCount"
  | "toolbar.export"
  | "toolbar.settings"
  | "toolbar.preferences"
  | "toolbar.about"
  | "toolbar.subtitle"
  | "settings.preferences"
  | "settings.general"
  | "settings.translation"
  | "settings.detection"
  | "settings.inpainting"
  | "settings.generalTitle"
  | "settings.generalDesc"
  | "settings.translationTitle"
  | "settings.translationDesc"
  | "settings.detectionTitle"
  | "settings.detectionDesc"
  | "settings.inpaintingTitle"
  | "settings.inpaintingDesc"
  | "settings.appearance"
  | "settings.theme"
  | "settings.uiLanguage"
  | "settings.connectionDefaults"
  | "settings.requestTimeout"
  | "settings.languages"
  | "settings.sourceLanguage"
  | "settings.targetLanguage"
  | "settings.activeProvider"
  | "settings.translationProvider"
  | "settings.providerConfig"
  | "settings.model"
  | "settings.refresh"
  | "settings.selectModel"
  | "settings.enterApiKeyToLoadModels"
  | "settings.loadingModels"
  | "settings.noModelsFound"
  | "settings.close";

const translations: Record<UiLanguage, Record<TranslationKey, string>> = {
  en: {
    "app.title": "VibeCleaner",
    "toolbar.addImages": "Add Images",
    "toolbar.menu": "Menu",
    "toolbar.newProject": "New Project",
    "toolbar.openProject": "Open Project",
    "toolbar.saveProject": "Save Project",
    "toolbar.translate": "Translate",
    "toolbar.translating": "Translating...",
    "toolbar.translateCurrentPage": "Translate current page",
    "toolbar.translatePageCount": "Translate {count} pages",
    "toolbar.export": "Export",
    "toolbar.settings": "Settings",
    "toolbar.preferences": "Preferences",
    "toolbar.about": "About",
    "toolbar.subtitle": "Image cleanup workspace",
    "settings.preferences": "Preferences",
    "settings.general": "General",
    "settings.translation": "Translation",
    "settings.detection": "Detection",
    "settings.inpainting": "Inpainting",
    "settings.generalTitle": "General Settings",
    "settings.generalDesc": "Manage general preferences, font size boundaries, and timeouts.",
    "settings.translationTitle": "Translation Engine",
    "settings.translationDesc": "Select from offline, local, or cloud API translation engines.",
    "settings.detectionTitle": "Detection & OCR",
    "settings.detectionDesc": "Configure bubble detection models, threshold tolerances, and tiling settings.",
    "settings.inpaintingTitle": "Inpainting & Cleaning",
    "settings.inpaintingDesc": "Tweak background LaMa inpainting mask boundaries and dilation.",
    "settings.appearance": "Appearance",
    "settings.theme": "Theme",
    "settings.uiLanguage": "UI Language",
    "settings.connectionDefaults": "Connection Defaults",
    "settings.requestTimeout": "Request Timeout (sec)",
    "settings.languages": "Languages",
    "settings.sourceLanguage": "Source Language (OCR)",
    "settings.targetLanguage": "Target Language (Translation)",
    "settings.activeProvider": "Active Provider",
    "settings.translationProvider": "Translation Provider",
    "settings.providerConfig": "Provider Credentials & Config",
    "settings.model": "Model",
    "settings.refresh": "Refresh",
    "settings.selectModel": "Select a model...",
    "settings.enterApiKeyToLoadModels": "Enter your API key to load models.",
    "settings.loadingModels": "Loading models...",
    "settings.noModelsFound": "No models found.",
    "settings.close": "Close",
  },
  ko: {
    "app.title": "VibeCleaner",
    "toolbar.addImages": "이미지 추가",
    "toolbar.menu": "메뉴",
    "toolbar.newProject": "새 프로젝트",
    "toolbar.openProject": "프로젝트 열기",
    "toolbar.saveProject": "프로젝트 저장",
    "toolbar.translate": "번역",
    "toolbar.translating": "번역 중...",
    "toolbar.translateCurrentPage": "현재 페이지 번역",
    "toolbar.translatePageCount": "{count}페이지 번역",
    "toolbar.export": "내보내기",
    "toolbar.settings": "설정",
    "toolbar.preferences": "환경설정",
    "toolbar.about": "정보",
    "toolbar.subtitle": "이미지 정리 작업공간",
    "settings.preferences": "환경설정",
    "settings.general": "일반",
    "settings.translation": "번역",
    "settings.detection": "감지",
    "settings.inpainting": "인페인팅",
    "settings.generalTitle": "일반 설정",
    "settings.generalDesc": "기본 표시, 글꼴 크기 범위, 요청 시간 제한을 설정합니다.",
    "settings.translationTitle": "번역 엔진",
    "settings.translationDesc": "오프라인, 로컬, 클라우드 API 번역 엔진을 선택합니다.",
    "settings.detectionTitle": "감지 및 OCR",
    "settings.detectionDesc": "말풍선 감지 모델, 신뢰도 기준, 타일링 설정을 조정합니다.",
    "settings.inpaintingTitle": "인페인팅 및 정리",
    "settings.inpaintingDesc": "LaMa 인페인팅 마스크 경계와 확장 값을 조정합니다.",
    "settings.appearance": "표시",
    "settings.theme": "테마",
    "settings.uiLanguage": "UI 언어",
    "settings.connectionDefaults": "연결 기본값",
    "settings.requestTimeout": "요청 제한 시간(초)",
    "settings.languages": "언어",
    "settings.sourceLanguage": "원본 언어(OCR)",
    "settings.targetLanguage": "대상 언어(번역)",
    "settings.activeProvider": "활성 제공자",
    "settings.translationProvider": "번역 제공자",
    "settings.providerConfig": "제공자 인증 및 설정",
    "settings.model": "모델",
    "settings.refresh": "새로고침",
    "settings.selectModel": "모델 선택...",
    "settings.enterApiKeyToLoadModels": "모델을 불러오려면 API 키를 입력하세요.",
    "settings.loadingModels": "모델 불러오는 중...",
    "settings.noModelsFound": "모델을 찾지 못했습니다.",
    "settings.close": "닫기",
  },
};

export function normalizeUiLanguage(value: unknown): UiLanguage {
  return value === "ko" ? "ko" : "en";
}

export function createTranslator(value: unknown) {
  const language = normalizeUiLanguage(value);
  return (key: string): string => {
    if (isTranslationKey(key)) {
      return translations[language][key] ?? translations.en[key];
    }
    return key;
  };
}

function isTranslationKey(key: string): key is TranslationKey {
  return Object.hasOwn(translations.en, key);
}
