export type UiLanguage = "en" | "ko";

export const UI_LANGUAGE_STORAGE_KEY = "vibecleaner_ui_language";

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
  | "dialog.cancel"
  | "dialog.confirm"
  | "dialog.ok"
  | "dialog.save"
  | "dialog.dontSave"
  | "project.unsavedChanges"
  | "project.unsavedChangesMessage"
  | "project.success"
  | "project.projectSaved"
  | "project.loadingSelectedImages"
  | "project.selectMangaImagesTitle"
  | "project.mangaImagesFilter"
  | "project.allFilesFilter"
  | "project.failedToOpenFiles"
  | "project.creatingNewProject"
  | "project.failedToCreateNewProject"
  | "project.loadingProject"
  | "project.openProjectTitle"
  | "project.projectFilter"
  | "project.legacyJsonProjectFilter"
  | "project.failedToLoadProject"
  | "project.savingProject"
  | "project.saveProjectTitle"
  | "project.failedToSaveProject"
  | "project.renamingPage"
  | "project.renameFailed"
  | "pages.loadFailedTitle"
  | "pages.loadFailedMessage"
  | "pages.switchFailedTitle"
  | "pages.switchFailedMessage"
  | "pages.duplicatingPage"
  | "pages.duplicatingPages"
  | "pages.failedToDuplicatePage"
  | "pages.deletePageTitle"
  | "pages.deletePagesTitle"
  | "pages.deletePageMessage"
  | "pages.deletePagesMessage"
  | "pages.deletingPage"
  | "pages.deletingPages"
  | "pages.failedToDeletePage"
  | "pages.reorderingPages"
  | "pages.failedToReorderPages"
  | "bubbles.loadFailedTitle"
  | "bubbles.loadFailedMessage"
  | "bubbles.saveFailedTitle"
  | "bubbles.saveFailedMessage"
  | "bubbles.reRunningOcr"
  | "bubbles.ocrFailed"
  | "bubbles.translatingSpeechBubble"
  | "bubbles.translationFailed"
  | "bubbles.deleteFailedTitle"
  | "bubbles.deleteFailedMessage"
  | "task.translationFailed"
  | "task.multiPageTranslationFailed"
  | "task.translatingPage"
  | "task.translatingPages"
  | "task.failed"
  | "export.cleaningBeforeExport"
  | "export.pageImageTitle"
  | "export.pngImageFilter"
  | "export.jpegImageFilter"
  | "export.webpImageFilter"
  | "export.exportingPage"
  | "export.exportingPages"
  | "export.successTitle"
  | "export.successSingleMessage"
  | "export.successMultiMessage"
  | "export.failedTitle"
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
    "dialog.cancel": "Cancel",
    "dialog.confirm": "Confirm",
    "dialog.ok": "OK",
    "dialog.save": "Save",
    "dialog.dontSave": "Don't Save",
    "project.unsavedChanges": "Unsaved Changes",
    "project.unsavedChangesMessage": "You have unsaved changes. Do you want to save them before continuing?",
    "project.success": "Success",
    "project.projectSaved": "Project saved successfully!",
    "project.loadingSelectedImages": "Loading selected images...",
    "project.selectMangaImagesTitle": "Select Manga Images to Load",
    "project.mangaImagesFilter": "Manga Images",
    "project.allFilesFilter": "All Files",
    "project.failedToOpenFiles": "Failed to Open Files",
    "project.creatingNewProject": "Creating new project...",
    "project.failedToCreateNewProject": "Failed to Create New Project",
    "project.loadingProject": "Loading project...",
    "project.openProjectTitle": "Open {appName} Project",
    "project.projectFilter": "{appName} Project",
    "project.legacyJsonProjectFilter": "Legacy JSON Project",
    "project.failedToLoadProject": "Failed to Load Project",
    "project.savingProject": "Saving project...",
    "project.saveProjectTitle": "Save {appName} Project",
    "project.failedToSaveProject": "Failed to Save Project",
    "project.renamingPage": "Renaming page...",
    "project.renameFailed": "Rename Failed",
    "pages.loadFailedTitle": "Page Load Failed",
    "pages.loadFailedMessage": "Failed to load the page list.",
    "pages.switchFailedTitle": "Page Switch Failed",
    "pages.switchFailedMessage": "Could not switch to the selected page.",
    "pages.duplicatingPage": "Duplicating page...",
    "pages.duplicatingPages": "Duplicating {count} pages...",
    "pages.failedToDuplicatePage": "Failed to Duplicate Page",
    "pages.deletePageTitle": "Delete Page",
    "pages.deletePagesTitle": "Delete Pages",
    "pages.deletePageMessage": "Are you sure you want to delete this page? This action cannot be undone.",
    "pages.deletePagesMessage": "Are you sure you want to delete {count} pages? This action cannot be undone.",
    "pages.deletingPage": "Deleting page...",
    "pages.deletingPages": "Deleting {count} pages...",
    "pages.failedToDeletePage": "Failed to Delete Page",
    "pages.reorderingPages": "Reordering pages...",
    "pages.failedToReorderPages": "Failed to Reorder Pages",
    "bubbles.loadFailedTitle": "Bubble Load Failed",
    "bubbles.loadFailedMessage": "Failed to load speech bubbles for the current page.",
    "bubbles.saveFailedTitle": "Save Failed",
    "bubbles.saveFailedMessage": "Failed to save speech bubble changes.",
    "bubbles.reRunningOcr": "Re-running OCR...",
    "bubbles.ocrFailed": "OCR Failed",
    "bubbles.translatingSpeechBubble": "Translating speech bubble...",
    "bubbles.translationFailed": "Translation Failed",
    "bubbles.deleteFailedTitle": "Delete Failed",
    "bubbles.deleteFailedMessage": "Failed to delete the speech bubble.",
    "task.translationFailed": "Translation Failed",
    "task.multiPageTranslationFailed": "Multi-Page Translation Failed",
    "task.translatingPage": "Translating page...",
    "task.translatingPages": "Translating {count} pages...",
    "task.failed": "Task Failed",
    "export.cleaningBeforeExport": "Cleaning page before export...",
    "export.pageImageTitle": "Export Page Image",
    "export.pngImageFilter": "PNG Image",
    "export.jpegImageFilter": "JPEG Image",
    "export.webpImageFilter": "WebP Image",
    "export.exportingPage": "Exporting page...",
    "export.exportingPages": "Exporting {count} pages...",
    "export.successTitle": "Export Successful",
    "export.successSingleMessage": "Successfully saved to:\n{path}",
    "export.successMultiMessage": "Saved {count} images to:\n{path}",
    "export.failedTitle": "Export Failed",
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
    "dialog.cancel": "취소",
    "dialog.confirm": "확인",
    "dialog.ok": "확인",
    "dialog.save": "저장",
    "dialog.dontSave": "저장 안 함",
    "project.unsavedChanges": "저장되지 않은 변경사항",
    "project.unsavedChangesMessage": "저장되지 않은 변경사항이 있습니다. 계속하기 전에 저장할까요?",
    "project.success": "완료",
    "project.projectSaved": "프로젝트가 저장되었습니다.",
    "project.loadingSelectedImages": "선택한 이미지 불러오는 중...",
    "project.selectMangaImagesTitle": "불러올 만화 이미지 선택",
    "project.mangaImagesFilter": "만화 이미지",
    "project.allFilesFilter": "모든 파일",
    "project.failedToOpenFiles": "파일 열기 실패",
    "project.creatingNewProject": "새 프로젝트 만드는 중...",
    "project.failedToCreateNewProject": "새 프로젝트 생성 실패",
    "project.loadingProject": "프로젝트 불러오는 중...",
    "project.openProjectTitle": "{appName} 프로젝트 열기",
    "project.projectFilter": "{appName} 프로젝트",
    "project.legacyJsonProjectFilter": "레거시 JSON 프로젝트",
    "project.failedToLoadProject": "프로젝트 불러오기 실패",
    "project.savingProject": "프로젝트 저장 중...",
    "project.saveProjectTitle": "{appName} 프로젝트 저장",
    "project.failedToSaveProject": "프로젝트 저장 실패",
    "project.renamingPage": "페이지 이름 변경 중...",
    "project.renameFailed": "이름 변경 실패",
    "pages.loadFailedTitle": "페이지 로드 실패",
    "pages.loadFailedMessage": "페이지 목록을 불러오지 못했습니다.",
    "pages.switchFailedTitle": "페이지 전환 실패",
    "pages.switchFailedMessage": "선택한 페이지로 전환하지 못했습니다.",
    "pages.duplicatingPage": "페이지 복제 중...",
    "pages.duplicatingPages": "{count}개 페이지 복제 중...",
    "pages.failedToDuplicatePage": "페이지 복제 실패",
    "pages.deletePageTitle": "페이지 삭제",
    "pages.deletePagesTitle": "페이지들 삭제",
    "pages.deletePageMessage": "이 페이지를 삭제할까요? 이 작업은 되돌릴 수 없습니다.",
    "pages.deletePagesMessage": "{count}개 페이지를 삭제할까요? 이 작업은 되돌릴 수 없습니다.",
    "pages.deletingPage": "페이지 삭제 중...",
    "pages.deletingPages": "{count}개 페이지 삭제 중...",
    "pages.failedToDeletePage": "페이지 삭제 실패",
    "pages.reorderingPages": "페이지 순서 변경 중...",
    "pages.failedToReorderPages": "페이지 순서 변경 실패",
    "bubbles.loadFailedTitle": "말풍선 로드 실패",
    "bubbles.loadFailedMessage": "현재 페이지의 말풍선 정보를 불러오지 못했습니다.",
    "bubbles.saveFailedTitle": "저장 실패",
    "bubbles.saveFailedMessage": "말풍선 변경 사항을 저장하지 못했습니다.",
    "bubbles.reRunningOcr": "OCR 다시 실행 중...",
    "bubbles.ocrFailed": "OCR 실패",
    "bubbles.translatingSpeechBubble": "말풍선 번역 중...",
    "bubbles.translationFailed": "번역 실패",
    "bubbles.deleteFailedTitle": "삭제 실패",
    "bubbles.deleteFailedMessage": "말풍선을 삭제하지 못했습니다.",
    "task.translationFailed": "번역 실패",
    "task.multiPageTranslationFailed": "여러 페이지 번역 실패",
    "task.translatingPage": "페이지 번역 중...",
    "task.translatingPages": "{count}개 페이지 번역 중...",
    "task.failed": "작업 실패",
    "export.cleaningBeforeExport": "내보내기 전 페이지 정리 중...",
    "export.pageImageTitle": "페이지 이미지 내보내기",
    "export.pngImageFilter": "PNG 이미지",
    "export.jpegImageFilter": "JPEG 이미지",
    "export.webpImageFilter": "WebP 이미지",
    "export.exportingPage": "페이지 내보내는 중...",
    "export.exportingPages": "{count}개 페이지 내보내는 중...",
    "export.successTitle": "내보내기 완료",
    "export.successSingleMessage": "저장 위치:\n{path}",
    "export.successMultiMessage": "{count}개 이미지를 저장했습니다:\n{path}",
    "export.failedTitle": "내보내기 실패",
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

const translatorCache = new Map<UiLanguage, (key: string) => string>();

export function normalizeUiLanguage(value: unknown): UiLanguage {
  return value === "ko" ? "ko" : "en";
}

export function getStoredUiLanguage(storage: Storage | null = getUiLanguageStorage()): UiLanguage {
  try {
    return normalizeUiLanguage(storage?.getItem(UI_LANGUAGE_STORAGE_KEY));
  } catch {
    return "en";
  }
}

export function rememberUiLanguage(value: unknown, storage: Storage | null = getUiLanguageStorage()): void {
  try {
    storage?.setItem(UI_LANGUAGE_STORAGE_KEY, normalizeUiLanguage(value));
  } catch {
    // Ignore unavailable storage; backend settings remain the source of truth.
  }
}

export function createTranslator(value: unknown) {
  const language = normalizeUiLanguage(value);
  const cached = translatorCache.get(language);
  if (cached) return cached;

  const translator = (key: string): string => {
    if (isTranslationKey(key)) {
      return translations[language][key] ?? translations.en[key];
    }
    return key;
  };
  translatorCache.set(language, translator);
  return translator;
}

function isTranslationKey(key: string): key is TranslationKey {
  return Object.hasOwn(translations.en, key);
}

function getUiLanguageStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  return window.localStorage ?? null;
}
