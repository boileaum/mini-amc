// Runbook task lists render as disabled checkboxes; enable them in the built
// docs and persist their state per page (localStorage).
document.addEventListener("DOMContentLoaded", () => {
  const key = "mini-amc-checklist-" + location.pathname;
  let saved = {};
  try {
    saved = JSON.parse(localStorage.getItem(key) || "{}");
  } catch {
    saved = {};
  }
  document
    .querySelectorAll("input.task-list-item-checkbox")
    .forEach((cb, i) => {
      cb.disabled = false;
      if (saved[i]) cb.checked = true;
      cb.addEventListener("change", () => {
        saved[i] = cb.checked;
        try {
          localStorage.setItem(key, JSON.stringify(saved));
        } catch {
          // private mode: checkboxes still work for the session
        }
      });
    });
});
