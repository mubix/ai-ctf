/* Progressive enhancement. Native forms still work without JavaScript. */
(() => {
  const region = document.getElementById("lesson-content");
  const status = document.getElementById("request-status");
  const error = document.getElementById("connection-error");
  const signin = document.getElementById("sign-in-again");
  let busy = false;
  let timer;
  // randomUUID is unavailable on some browsers over a workshop's plain HTTP LAN.
  const requestId = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, "0")).join("");
  const layout = () => region.querySelector(".lesson-layout");
  const composer = () => region.querySelector('[data-lesson-action="send"]');
  const draftKey = () => `anvil-lesson:${layout().dataset.player}:${layout().dataset.run}`;
  const readDraft = () => {
    try { return JSON.parse(sessionStorage.getItem(draftKey())); } catch { return null; }
  };
  const saveDraft = () => {
    const form = composer();
    if (!form) return;
    try { sessionStorage.setItem(draftKey(), JSON.stringify({message: form.elements.message.value, request: form.elements.request_id.value})); } catch { /* Storage can be disabled. */ }
  };
  const clearDraft = (key) => { try { sessionStorage.removeItem(key); } catch { /* optional */ } };
  function setup() {
    if (window.matchMedia("(max-width: 820px)").matches) {
      region.querySelectorAll(".mission-explainer, .hint-panel").forEach(el => el.open = false);
    }
    const form = composer();
    let draft = readDraft();
    if (draft && [...region.querySelectorAll('[data-turn-status="completed"]')].some(el => el.dataset.request === draft.request)) {
      clearDraft(draftKey());
      draft = null;
    }
    if (form && draft) {
      form.elements.message.value = draft.message;
      form.elements.request_id.value = draft.request;
    }
    if (layout().dataset.running === "true") {
      timer = setTimeout(refresh, 3000);
    }
  }
  function showError(message, expired = false) {
    error.textContent = message;
    error.hidden = false;
    signin.hidden = !expired;
  }
  async function refresh() {
    if (busy) return;
    try {
      const response = await fetch(window.location.href, {headers: {Accept: "application/json"}});
      const data = await response.json();
      if (!response.ok) { showError(data.error || "Could not refresh this attempt. Reload to try again.", response.status === 401); return; }
      region.innerHTML = data.html;
      setup();
    } catch { showError("Could not refresh this attempt. Your work is saved on the server. Reload to check its status."); }
  }
  region.addEventListener("input", (event) => {
    if (event.target.name === "message") {
      // Editing a failed/retried payload is a new request, not a replay.
      composer().elements.request_id.value = requestId();
      saveDraft();
    }
  });
  region.addEventListener("click", (event) => {
    const button = event.target.closest("[data-fill]");
    const form = composer();
    if (!button || !form || busy || form.elements.message.disabled) return;
    form.elements.message.value = button.dataset.fill;
    form.elements.request_id.value = button.dataset.retry || requestId();
    saveDraft();
    if (window.matchMedia("(max-width: 820px)").matches) region.querySelector(".hint-panel").open = false;
    form.elements.message.focus();
  });
  region.addEventListener("keydown", (event) => {
    if (event.target.name === "message" && event.key === "Enter" && (event.ctrlKey || event.metaKey) && !event.isComposing) {
      event.preventDefault();
      if (!busy) composer().requestSubmit();
    }
  });
  region.addEventListener("submit", async (event) => {
    const form = event.target.closest("[data-lesson-action]");
    if (!form) return;
    event.preventDefault();
    if (busy) return;
    const action = form.dataset.lessonAction;
    if (action === "send" && !form.elements.message.value.trim()) {
      showError("Enter a message before sending.");
      form.elements.message.focus();
      return;
    }
    saveDraft();
    const key = draftKey();
    const payload = new FormData(form);
    const focusAction = action;
    busy = true;
    clearTimeout(timer);
    error.hidden = true;
    signin.hidden = true;
    const controls = [...region.querySelectorAll("button, textarea")];
    const disabledBefore = controls.map(el => el.disabled);
    controls.forEach(el => el.disabled = true);
    status.textContent = action === "send" ? "Waiting for the AI service. Your request may be queued or running; it can take up to three minutes." : "Saving…";
    try {
      const response = await fetch(form.action, {method: "POST", body: payload, headers: {Accept: "application/json"}});
      const data = await response.json();
      if (response.ok && (action === "send" || action === "reset")) clearDraft(key);
      if (data.html) region.innerHTML = data.html;
      if (!response.ok) showError(data.error || "The request could not finish. Your draft is preserved.", response.status === 401);
      setup();
      if (response.ok && focusAction === "send") {
        const log = region.querySelector(".lesson-messages");
        const latestExperiment = log.querySelector(".experiment:last-child h3");
        if (latestExperiment) {
          latestExperiment.tabIndex = -1;
          latestExperiment.focus();
          latestExperiment.scrollIntoView({block: "start"});
        } else {
          log.scrollTop = log.scrollHeight;
          composer()?.elements.message.focus({preventScroll: true});
        }
        status.textContent = "Result saved. Review the feedback and evidence in the workspace.";
      } else {
        status.textContent = response.ok ? "Saved." : "Request failed. Your message is preserved.";
        if (response.ok && action === "hint") {
          region.querySelector(".hint-panel").open = true;
          const hints = region.querySelectorAll(".revealed-hint h3");
          const newest = hints[hints.length - 1];
          if (newest) { newest.tabIndex = -1; newest.focus(); }
        }
        if (response.ok && action === "reset") composer()?.elements.message.focus();
        if (response.ok && action === "compare") {
          const result = region.querySelector(`[data-comparison="${payload.get("request_id")}"]`);
          const heading = result?.querySelector("h4");
          if (heading) { heading.tabIndex = -1; heading.focus(); heading.scrollIntoView({block: "start"}); }
          status.textContent = "Comparison saved. Review the replay and legitimate-use check.";
        }
      }
    } catch {
      showError("Connection lost. Your draft is preserved. Retry the same message or reload to check whether its response arrived.");
      status.textContent = "Connection lost.";
    } finally {
      controls.forEach((el, i) => { if (el.isConnected) el.disabled = disabledBefore[i]; });
      busy = false;
    }
  });
  setup();
})();
