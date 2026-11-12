export function registerPwa(): void {
  if (
    "serviceWorker" in navigator &&
    import.meta.env.PROD
  ) {
    window.addEventListener("load", () => {
      navigator.serviceWorker
        .register("/sw.js")
        .catch(error => {
          console.warn(
            "PWA indisponivel:",
            error instanceof Error
              ? error.message
              : "Falha no registro"
          );
        });
    });
  }
}
