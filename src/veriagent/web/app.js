"use strict";
const id = document.body.dataset.issueId;
const find = name => document.querySelector(`[data-testid="${name}"]`);
const result = find("result");
const choice = find("status-choice");
const save = find("save");
function message(text, code, phase) {
  result.textContent = text;
  result.dataset.code = String(code);
  result.dataset.phase = phase;
}
async function load() {
  try {
    const response = await fetch(`/issues/${id}`, {cache: "no-store"});
    if (!response.ok) { message("Issue could not be loaded", response.status, "ready"); return; }
    const issue = await response.json();
    find("title").textContent = issue.title;
    find("status").textContent = issue.status;
    find("version").textContent = String(issue.version);
    choice.value = issue.status;
    choice.disabled = false;
    save.disabled = false;
    message("Issue loaded", response.status, "ready");
  } catch { message("Connection failed", 0, "ready"); }
}
document.querySelector("form").addEventListener("submit", async event => {
  event.preventDefault();
  save.disabled = true;
  message("Saving…", 0, "saving");
  try {
    const response = await fetch(`/issues/${id}/status`, {
      method: "PATCH", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({status: choice.value})
    });
    if (response.ok) {
      // Deliberately trust the acknowledgment, as an ordinary optimistic UI might.
      // The independent SQLite oracle must detect an injected dropped commit.
      find("status").textContent = choice.value;
      message("Status updated", response.status, "done");
    } else { message("Status update failed", response.status, "done"); }
  } catch { message("Connection failed", 0, "done"); }
  save.disabled = false;
});
load();
