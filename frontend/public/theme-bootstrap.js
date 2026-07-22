/* Apply the saved theme (default: light) before first paint. */
(function () {
  try {
    var theme = localStorage.getItem("vibecleaner.theme");
    if (theme !== "light" && theme !== "dark") theme = "light";
    document.documentElement.setAttribute("data-theme", theme);
  } catch (_error) {
    document.documentElement.setAttribute("data-theme", "light");
  }
})();
