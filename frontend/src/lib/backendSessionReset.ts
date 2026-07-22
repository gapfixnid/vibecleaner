interface BackendSessionResetActions {
  hasInMemoryWork: boolean;
  resetProcessing: () => void;
  resetWorkspace: () => void;
  resetProject: () => void;
  markClean: () => void;
  warnAboutSessionLoss: () => void;
}

export function resetBackendSessionState({
  hasInMemoryWork,
  resetProcessing,
  resetWorkspace,
  resetProject,
  markClean,
  warnAboutSessionLoss,
}: BackendSessionResetActions): void {
  resetProcessing();
  resetWorkspace();
  resetProject();
  markClean();
  if (hasInMemoryWork) warnAboutSessionLoss();
}
