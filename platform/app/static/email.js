/* Email lab: native forms work too; polling never replaces an unsent draft. */
(() => {
  const region = document.getElementById("email-content");
  const status = document.getElementById("email-status");
  const error = document.getElementById("email-error");
  const signin = document.getElementById("email-signin");
  let busy = false, timer, epoch = 0, tab = "summary";
  const lab = () => region.querySelector(".email-lab");
  const composer = () => region.querySelector('[data-email-action="send"]');
  const newId = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, "0")).join("");
  const draftKey = () => `anvil-email:${lab().dataset.player}:${lab().dataset.run}`;
  const url = () => `/learn/email-joe?goal=${encodeURIComponent(lab().dataset.goal)}&attempt=${encodeURIComponent(lab().dataset.run)}`;
  function saveDraft() {
    const form = composer();
    if (!form) return;
    try { sessionStorage.setItem(draftKey(), JSON.stringify({subject: form.elements.subject.value,
      body: form.elements.body.value, protected: !!form.elements.protected?.checked,
      request: form.elements.request_id.value})); } catch { /* storage is optional */ }
  }
  function restoreDraft() {
    const form = composer();
    if (!form) return;
    try {
      const draft = JSON.parse(sessionStorage.getItem(draftKey()));
      if (!draft) return;
      form.elements.subject.value = draft.subject;
      form.elements.body.value = draft.body;
      if (form.elements.protected) form.elements.protected.checked = draft.protected;
      const ended = [...region.querySelectorAll("[data-saved-request]")].some(el => el.dataset.savedRequest === draft.request && el.dataset.savedStatus !== "running");
      form.elements.request_id.value = ended ? newId() : draft.request;
    } catch { /* no stored draft */ }
  }
  function showError(message, expired = false) {
    error.textContent = message;
    error.hidden = false;
    signin.hidden = !expired;
  }
  function showTab(name) {
    tab = name;
    region.querySelectorAll("[data-desk-pane]").forEach(el => el.hidden = el.dataset.deskPane !== name);
    region.querySelectorAll("[data-desk-tab]").forEach(el => el.setAttribute("aria-pressed", String(el.dataset.deskTab === name)));
  }
  function setup() {
    showTab(tab);
    restoreDraft();
    if (lab().dataset.running === "true") schedule();
  }
  function replaceDesk(html) {
    const desk = document.getElementById("email-desk");
    const log = desk.querySelector(".email-timeline");
    const nearBottom = !log || log.scrollHeight - log.scrollTop - log.clientHeight < 35;
    const oldScroll = log?.scrollTop || 0;
    const evidenceOpen = desk.querySelector(".email-evidence")?.open;
    desk.innerHTML = html;
    showTab(tab);
    if (evidenceOpen && desk.querySelector(".email-evidence")) desk.querySelector(".email-evidence").open = true;
    const next = desk.querySelector(".email-timeline");
    if (next) next.scrollTop = nearBottom ? next.scrollHeight : oldScroll;
  }
  function schedule() { clearTimeout(timer); timer = setTimeout(poll, 1000); }
  async function poll() {
    const generation = epoch;
    try {
      const response = await fetch(url(), {headers: {Accept: "application/json"}});
      const data = await response.json();
      if (generation !== epoch) return;
      if (!response.ok) { showError(data.error || "Could not check Joe's activity. Reload to resume.", response.status === 401); return; }
      replaceDesk(data.desk);
      if (data.running || busy) schedule();
      else {
        saveDraft();
        region.innerHTML = data.html;
        setup();
        status.textContent = "Run finished. Review Joe's screen and the recorded evidence.";
      }
    } catch {
      if (generation === epoch) showError("Could not refresh activity. Your saved run continues; reload to check its result.");
    }
  }
  region.addEventListener("input", event => {
    if (!event.target.closest('[data-email-action="send"]')) return;
    composer().elements.request_id.value = newId();
    saveDraft();
  });
  region.addEventListener("click", event => {
    const view = event.target.closest("[data-desk-tab]");
    if (view) { showTab(view.dataset.deskTab); return; }
    const fill = event.target.closest("[data-email-fill]");
    const form = composer();
    if (!fill || !form || busy || form.elements.body.disabled) return;
    form.elements.subject.value = fill.dataset.subject;
    form.elements.body.value = fill.dataset.body;
    if (form.elements.protected && fill.dataset.protected !== undefined) form.elements.protected.checked = fill.dataset.protected === "true";
    form.elements.request_id.value = newId();
    saveDraft();
    form.elements.body.focus();
  });
  region.addEventListener("keydown", event => {
    if (event.target.name === "body" && event.key === "Enter" && (event.ctrlKey || event.metaKey) && !event.isComposing) {
      event.preventDefault();
      if (!busy) composer()?.requestSubmit();
    }
  });
  region.addEventListener("submit", async event => {
    const form = event.target.closest("[data-email-action]");
    if (!form) return;
    event.preventDefault();
    if (busy) return;
    const action = form.dataset.emailAction;
    saveDraft();
    const key = draftKey();
    const payload = new FormData(form);
    const controls = [...region.querySelectorAll("form button, form input:not([type=hidden]), form textarea, [data-email-fill]")];
    const disabled = controls.map(el => el.disabled);
    controls.forEach(el => el.disabled = true);
    busy = true;
    epoch++;
    clearTimeout(timer);
    error.hidden = true;
    signin.hidden = true;
    status.textContent = action === "send" ? "Saving your email and starting Joe's assistant. This can take up to three minutes." : "Saving…";
    if (action === "send") schedule();
    try {
      const response = await fetch(form.action, {method: "POST", body: payload, headers: {Accept: "application/json"}});
      const data = await response.json();
      epoch++;
      clearTimeout(timer);
      if (response.ok && action === "reset") {
        try { sessionStorage.removeItem(key); } catch { /* optional */ }
      }
      if (data.html) region.innerHTML = data.html;
      setup();
      if (!response.ok) showError(data.error || "The email could not finish. Your draft is preserved.", response.status === 401);
      if (action === "send") {
        // A terminal result gets a new request ID; retrying a lost connection keeps its ID.
        if (data.html && !data.running && composer()) { composer().elements.request_id.value = newId(); saveDraft(); }
        status.textContent = response.ok ? "Run saved. Review Joe's screen and the recorded evidence." : "Run did not finish. Your email is preserved.";
        if (response.ok) {
          if (window.matchMedia("(max-width: 960px)").matches) {
            showTab("summary");
            const heading = region.querySelector("#joe-summary-heading");
            heading?.focus({preventScroll: true});
            heading?.scrollIntoView({block: "start"});
          } else region.querySelector("#email-verdict-heading")?.focus({preventScroll: true});
        }
      } else if (response.ok && action === "hint") {
        const panel = region.querySelector(".email-hints");
        panel.open = true;
        const newest = [...panel.querySelectorAll(".revealed-hint h3")].pop();
        if (newest) { newest.tabIndex = -1; newest.focus({preventScroll: true}); }
        status.textContent = "Hint revealed. Your draft is preserved.";
      } else if (response.ok) {
        status.textContent = "Fresh workspace ready. Earlier emails and progress are saved.";
        composer()?.elements.body.focus();
      }
    } catch {
      showError("Connection lost. Your draft is preserved. Reload to check whether Joe's assistant finished before sending again.");
      status.textContent = "Connection lost.";
    } finally {
      controls.forEach((el, i) => { if (el.isConnected) el.disabled = disabled[i]; });
      busy = false;
    }
  });
  setup();
})();
