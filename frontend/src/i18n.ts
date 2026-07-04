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
  | "sidebar.pages"
  | "sidebar.addedCount"
  | "sidebar.saveImages"
  | "sidebar.saveSelectedImages"
  | "sidebar.filterPages"
  | "sidebar.noMatchingPages"
  | "sidebar.differentFilter"
  | "sidebar.noImagesLoaded"
  | "sidebar.rename"
  | "sidebar.duplicate"
  | "sidebar.delete"
  | "sidebar.translatePage"
  | "sidebar.translatePages"
  | "sidebar.saveImageEllipsis"
  | "sidebar.saveImagesEllipsis"
  | "sidebar.selectAll"
  | "inspector.header"
  | "inspector.text"
  | "inspector.style"
  | "inspector.noSelection"
  | "inspector.noSelectionDesc"
  | "inspector.multiSelect"
  | "inspector.multiSelectDesc"
  | "inspector.original"
  | "inspector.translation"
  | "inspector.reOcr"
  | "inspector.noOriginalText"
  | "inspector.translationPlaceholder"
  | "inspector.typographyDesign"
  | "inspector.fontFamily"
  | "inspector.fontSize"
  | "inspector.fontStyle"
  | "inspector.bold"
  | "inspector.italic"
  | "inspector.alignment"
  | "inspector.alignLeft"
  | "inspector.alignCenter"
  | "inspector.alignRight"
  | "inspector.textColor"
  | "inspector.category"
  | "inspector.reviewStatus"
  | "inspector.unknown"
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
  | "settings.close"
  | "settings.googleProviderInfo"
  | "settings.deeplApiKey"
  | "settings.deeplApiKeyPlaceholder"
  | "settings.deeplApiKeyHelp"
  | "settings.openaiApiKey"
  | "settings.claudeApiKey"
  | "settings.papagoClientId"
  | "settings.papagoClientIdPlaceholder"
  | "settings.papagoClientSecret"
  | "settings.papagoClientSecretPlaceholder"
  | "settings.baiduAppId"
  | "settings.baiduAppIdPlaceholder"
  | "settings.baiduSecretKey"
  | "settings.baiduSecretKeyPlaceholder"
  | "settings.ollamaProviderInfo"
  | "settings.apiBaseUrl"
  | "settings.apiKeyOptional"
  | "settings.optionalApiKeyPlaceholder"
  | "settings.visionContext"
  | "settings.systemPromptOverride"
  | "settings.systemPromptPlaceholder"
  | "settings.recognitionRules"
  | "settings.tilingEnabled"
  | "settings.bubblesOnly"
  | "settings.confidenceTolerances"
  | "settings.confidenceThreshold"
  | "settings.inpaintingOptions"
  | "settings.cleanTextboxOnly"
  | "settings.clipInpaintingMask"
  | "settings.maskTolerances"
  | "settings.maskDilation";

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
    "sidebar.pages": "Pages",
    "sidebar.addedCount": "{count} added",
    "sidebar.saveImages": "Save Images",
    "sidebar.saveSelectedImages": "Save Selected Images",
    "sidebar.filterPages": "Filter pages...",
    "sidebar.noMatchingPages": "No matching pages",
    "sidebar.differentFilter": "Try a different filename filter.",
    "sidebar.noImagesLoaded": "No images loaded",
    "sidebar.rename": "Rename",
    "sidebar.duplicate": "Duplicate",
    "sidebar.delete": "Delete",
    "sidebar.translatePage": "Translate Page",
    "sidebar.translatePages": "Translate Pages",
    "sidebar.saveImageEllipsis": "Save Image...",
    "sidebar.saveImagesEllipsis": "Save Images...",
    "sidebar.selectAll": "Select All",
    "inspector.header": "Inspector - Bubble #{id}",
    "inspector.text": "Text",
    "inspector.style": "Style",
    "inspector.noSelection": "No Selection",
    "inspector.noSelectionDesc": "Select a speech bubble on the canvas to inspect and edit its properties.",
    "inspector.multiSelect": "Multiple Pages Selected",
    "inspector.multiSelectDesc": "Select a single page to edit bubbles.",
    "inspector.original": "Original ({language})",
    "inspector.translation": "Translation ({language})",
    "inspector.reOcr": "Re-OCR",
    "inspector.noOriginalText": "No original text detected.",
    "inspector.translationPlaceholder": "Translation result will show here...",
    "inspector.typographyDesign": "Typography & Design",
    "inspector.fontFamily": "Font Family",
    "inspector.fontSize": "Font Size",
    "inspector.fontStyle": "Font Style",
    "inspector.bold": "Bold",
    "inspector.italic": "Italic",
    "inspector.alignment": "Alignment",
    "inspector.alignLeft": "Align Left",
    "inspector.alignCenter": "Align Center",
    "inspector.alignRight": "Align Right",
    "inspector.textColor": "Text Color",
    "inspector.category": "Category",
    "inspector.reviewStatus": "Review Status",
    "inspector.unknown": "unknown",
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
    "settings.googleProviderInfo": "Google Translate uses a public web-scraping translator API. No credential setup is required. Requires an active internet connection.",
    "settings.deeplApiKey": "DeepL API Authentication Key",
    "settings.deeplApiKeyPlaceholder": "Paste your DeepL API key here...",
    "settings.deeplApiKeyHelp": "Free API Keys typically end with :fx.",
    "settings.openaiApiKey": "OpenAI API Key",
    "settings.claudeApiKey": "Anthropic Claude API Key",
    "settings.papagoClientId": "Papago Client ID",
    "settings.papagoClientIdPlaceholder": "Naver Cloud Platform Client ID...",
    "settings.papagoClientSecret": "Papago Client Secret",
    "settings.papagoClientSecretPlaceholder": "Naver Cloud Platform Client Secret...",
    "settings.baiduAppId": "Baidu APP ID",
    "settings.baiduAppIdPlaceholder": "Baidu Translation Portal APP ID...",
    "settings.baiduSecretKey": "Baidu Secret Key",
    "settings.baiduSecretKeyPlaceholder": "Baidu Translation Portal Secret Key...",
    "settings.ollamaProviderInfo": "Connects to your local Ollama daemon at http://127.0.0.1:11434. Make sure Ollama is running, then pick a model below.",
    "settings.apiBaseUrl": "API Base URL",
    "settings.apiKeyOptional": "API Key (Optional)",
    "settings.optionalApiKeyPlaceholder": "Optional custom LLM API key...",
    "settings.visionContext": "Send page image for visual context (turn off for text-only models, e.g. llama.cpp without mmproj)",
    "settings.systemPromptOverride": "System Prompt Override",
    "settings.systemPromptPlaceholder": "Enter custom context guidelines for the LLM translation engine...",
    "settings.recognitionRules": "Recognition Rules",
    "settings.tilingEnabled": "Tiling Enabled (Increases detection quality for small bubbles)",
    "settings.bubblesOnly": "Speech Bubbles Only (Ignore free-floating sfx text)",
    "settings.confidenceTolerances": "Confidence Tolerances",
    "settings.confidenceThreshold": "Confidence Threshold",
    "settings.inpaintingOptions": "Inpainting Options",
    "settings.cleanTextboxOnly": "Clean Text Box Areas Only (Recommended)",
    "settings.clipInpaintingMask": "Clip Inpainting Mask to speech bubble stroke edges",
    "settings.maskTolerances": "Mask tolerances",
    "settings.maskDilation": "Mask Dilation (Expansion)",
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
    "sidebar.pages": "페이지",
    "sidebar.addedCount": "{count}개 추가됨",
    "sidebar.saveImages": "이미지 저장",
    "sidebar.saveSelectedImages": "선택 이미지 저장",
    "sidebar.filterPages": "페이지 필터...",
    "sidebar.noMatchingPages": "일치하는 페이지 없음",
    "sidebar.differentFilter": "다른 파일명 필터를 입력해보세요.",
    "sidebar.noImagesLoaded": "불러온 이미지 없음",
    "sidebar.rename": "이름 변경",
    "sidebar.duplicate": "복제",
    "sidebar.delete": "삭제",
    "sidebar.translatePage": "페이지 번역",
    "sidebar.translatePages": "페이지들 번역",
    "sidebar.saveImageEllipsis": "이미지 저장...",
    "sidebar.saveImagesEllipsis": "이미지들 저장...",
    "sidebar.selectAll": "전체 선택",
    "inspector.header": "인스펙터 - 말풍선 #{id}",
    "inspector.text": "텍스트",
    "inspector.style": "스타일",
    "inspector.noSelection": "선택 없음",
    "inspector.noSelectionDesc": "캔버스에서 말풍선을 선택하면 속성을 확인하고 편집할 수 있습니다.",
    "inspector.multiSelect": "여러 페이지 선택됨",
    "inspector.multiSelectDesc": "말풍선을 편집하려면 단일 페이지를 선택하세요.",
    "inspector.original": "원문({language})",
    "inspector.translation": "번역문({language})",
    "inspector.reOcr": "OCR 다시 실행",
    "inspector.noOriginalText": "감지된 원문이 없습니다.",
    "inspector.translationPlaceholder": "번역 결과가 여기에 표시됩니다...",
    "inspector.typographyDesign": "타이포그래피 및 디자인",
    "inspector.fontFamily": "글꼴",
    "inspector.fontSize": "글꼴 크기",
    "inspector.fontStyle": "글꼴 스타일",
    "inspector.bold": "굵게",
    "inspector.italic": "기울임",
    "inspector.alignment": "정렬",
    "inspector.alignLeft": "왼쪽 정렬",
    "inspector.alignCenter": "가운데 정렬",
    "inspector.alignRight": "오른쪽 정렬",
    "inspector.textColor": "텍스트 색상",
    "inspector.category": "분류",
    "inspector.reviewStatus": "검토 상태",
    "inspector.unknown": "알 수 없음",
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
    "settings.googleProviderInfo": "Google Translate는 공개 웹 번역 API를 사용합니다. 별도 인증 설정은 필요 없으며 인터넷 연결이 필요합니다.",
    "settings.deeplApiKey": "DeepL API 인증 키",
    "settings.deeplApiKeyPlaceholder": "DeepL API 키를 붙여넣으세요...",
    "settings.deeplApiKeyHelp": "무료 API 키는 보통 :fx로 끝납니다.",
    "settings.openaiApiKey": "OpenAI API 키",
    "settings.claudeApiKey": "Anthropic Claude API 키",
    "settings.papagoClientId": "Papago 클라이언트 ID",
    "settings.papagoClientIdPlaceholder": "Naver Cloud Platform 클라이언트 ID...",
    "settings.papagoClientSecret": "Papago 클라이언트 시크릿",
    "settings.papagoClientSecretPlaceholder": "Naver Cloud Platform 클라이언트 시크릿...",
    "settings.baiduAppId": "Baidu APP ID",
    "settings.baiduAppIdPlaceholder": "Baidu 번역 포털 APP ID...",
    "settings.baiduSecretKey": "Baidu 시크릿 키",
    "settings.baiduSecretKeyPlaceholder": "Baidu 번역 포털 시크릿 키...",
    "settings.ollamaProviderInfo": "로컬 Ollama 데몬(http://127.0.0.1:11434)에 연결합니다. Ollama가 실행 중인지 확인한 뒤 모델을 선택하세요.",
    "settings.apiBaseUrl": "API Base URL",
    "settings.apiKeyOptional": "API 키(선택)",
    "settings.optionalApiKeyPlaceholder": "선택 사항인 커스텀 LLM API 키...",
    "settings.visionContext": "시각적 문맥을 위해 페이지 이미지를 함께 전송합니다(text-only 모델, 예: mmproj 없는 llama.cpp는 끄세요).",
    "settings.systemPromptOverride": "시스템 프롬프트 재정의",
    "settings.systemPromptPlaceholder": "LLM 번역 엔진에 전달할 커스텀 문맥 지침을 입력하세요...",
    "settings.recognitionRules": "인식 규칙",
    "settings.tilingEnabled": "타일링 활성화(작은 말풍선 감지 품질 향상)",
    "settings.bubblesOnly": "말풍선만 처리(떠 있는 효과음 텍스트 무시)",
    "settings.confidenceTolerances": "신뢰도 허용값",
    "settings.confidenceThreshold": "신뢰도 기준",
    "settings.inpaintingOptions": "인페인팅 옵션",
    "settings.cleanTextboxOnly": "텍스트 박스 영역만 지우기(권장)",
    "settings.clipInpaintingMask": "인페인팅 마스크를 말풍선 테두리 안쪽으로 제한",
    "settings.maskTolerances": "마스크 허용값",
    "settings.maskDilation": "마스크 확장",
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
