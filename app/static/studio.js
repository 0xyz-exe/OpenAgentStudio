const defaults = { name: "Number transformer", input: 7, factor: 3 };
const $ = (id) => document.getElementById(id);
const runButton = $("run-button");
const validateButton = $("validate-button");
const runTitle = $("run-title");
const runBadge = $("run-badge");
const runOutput = $("run-output");
const saveButton = $("save-button");
let csrfToken = "";
let savedWorkflowId = null;
let workflowDirty = true;
let setupRequired = false;

function makeWorkflow() {
  return {
    nodes: [
      { id: "start", type: "input", config: { value: Number($("input-number").value) } },
      { id: "scale", type: "multiply", config: { factor: Number($("factor-number").value) } },
      { id: "finish", type: "output", config: {} },
    ],
    edges: [
      { source: "start", target: "scale" },
      { source: "scale", target: "finish" },
    ],
  };
}

function markWorkflowDirty() {
  workflowDirty = true;
  $("save-state").textContent = "Unsaved changes";
  $("canvas-title").textContent = $("workflow-name").value.trim() || "Untitled workflow";
}

async function saveWorkflow() {
  const payload = { name: $("workflow-name").value.trim(), definition: makeWorkflow() };
  if (!payload.name) throw new Error("Workflow name cannot be blank.");
  const path = savedWorkflowId ? `/api/workflows/${encodeURIComponent(savedWorkflowId)}` : "/api/workflows";
  const saved = await request(path, payload, savedWorkflowId ? "PUT" : "POST");
  savedWorkflowId = saved.id;
  workflowDirty = false;
  $("save-state").textContent = "Saved locally";
  $("canvas-title").textContent = saved.name;
  await refreshSavedWorkflows(saved.id);
  return saved;
}

async function refreshSavedWorkflows(selectedId = savedWorkflowId) {
  const select = $("saved-workflows");
  const response = await request("/api/workflows");
  const options = [new Option("New workflow", "")];
  for (const workflow of response.workflows) {
    options.push(new Option(workflow.name, workflow.id));
  }
  select.replaceChildren(...options);
  select.value = selectedId || "";
}

async function loadSavedWorkflow(workflowId) {
  if (!workflowId) {
    savedWorkflowId = null;
    markWorkflowDirty();
    return;
  }
  const workflow = await request(`/api/workflows/${encodeURIComponent(workflowId)}`);
  const inputNode = workflow.definition.nodes.find((node) => node.type === "input");
  const multiplyNode = workflow.definition.nodes.find((node) => node.type === "multiply");
  if (!inputNode || !multiplyNode) throw new Error("This saved workflow is not supported by the demo editor.");
  $("workflow-name").value = workflow.name;
  $("input-number").value = inputNode.config.value;
  $("factor-number").value = multiplyNode.config.factor;
  savedWorkflowId = workflow.id;
  workflowDirty = false;
  $("save-state").textContent = "Saved locally";
  $("canvas-title").textContent = workflow.name;
  syncPreview();

  const { runs } = await request(`/api/workflows/${encodeURIComponent(workflow.id)}/runs`);
  if (runs.length) showResults({ ...runs[0].result, run_id: runs[0].id });
}

function activateWorkspace(user, token) {
  csrfToken = token;
  $("user-name").textContent = user.email.split("@")[0];
  $("user-email").textContent = user.email;
  $("auth-screen").hidden = true;
  $("studio-shell").hidden = false;
  refreshSavedWorkflows().then((_) => {
    const select = $("saved-workflows");
    if (select.options.length > 1) {
      select.value = select.options[1].value;
      return loadSavedWorkflow(select.value);
    }
  }).catch((error) => showError(error.message));
}

async function initializeAuthentication() {
  try {
    const statusResponse = await fetch("/api/auth/status", { credentials: "same-origin" });
    const status = await statusResponse.json();
    if (!statusResponse.ok) throw new Error("Unable to check local account status.");
    const meResponse = await fetch("/api/auth/me", { credentials: "same-origin" });
    if (meResponse.ok) {
      const session = await meResponse.json();
      activateWorkspace(session.user, session.csrf_token);
      return;
    }
    setupRequired = status.setup_required;
    $("auth-heading").textContent = setupRequired ? "Create your local workspace" : "Sign in to Open Agent Studio";
    $("auth-description").textContent = setupRequired
      ? "Create the one-time local owner account. Credentials stay on this device."
      : "Sign in to access workflows saved on this device.";
    $("workspace-name-row").hidden = !setupRequired;
    $("auth-password").autocomplete = setupRequired ? "new-password" : "current-password";
    $("auth-submit").textContent = setupRequired ? "Create workspace" : "Sign in";
    $("auth-submit").disabled = false;
  } catch (error) {
    $("auth-heading").textContent = "Local service unavailable";
    $("auth-description").textContent = "Start the local API, then reload this page.";
    $("auth-error").textContent = error.message;
  }
}

$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!event.currentTarget.reportValidity()) return;
  const button = $("auth-submit");
  button.disabled = true;
  $("auth-error").textContent = "";
  const payload = {
    email: $("auth-email").value,
    password: $("auth-password").value,
  };
  if (setupRequired) payload.workspace_name = $("auth-workspace").value;
  try {
    const response = await fetch(setupRequired ? "/api/auth/register" : "/api/auth/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Authentication failed (${response.status})`);
    $("auth-password").value = "";
    activateWorkspace(data.user, data.csrf_token);
  } catch (error) {
    $("auth-error").textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

$("logout-button").addEventListener("click", async () => {
  try {
    await request("/api/auth/logout", {}, "POST");
    window.location.reload();
  } catch (error) {
    showError(error.message);
  }
});

$("saved-workflows").addEventListener("change", async (event) => {
  try {
    await loadSavedWorkflow(event.currentTarget.value);
  } catch (error) {
    showError(error.message);
  }
});

$("workflow-name").addEventListener("input", markWorkflowDirty);

for (const id of ["input-number", "factor-number"]) {
  $(id).addEventListener("input", () => {
    syncPreview();
    markWorkflowDirty();
  });
}

saveButton.addEventListener("click", async () => {
  saveButton.disabled = true;
  try {
    await saveWorkflow();
    runTitle.textContent = "Workflow saved";
    setBadge("SAVED", "success");
  } catch (error) {
    showError(error.message);
  } finally {
    saveButton.disabled = false;
  }
});

function syncPreview() {
  $("input-value").textContent = $("input-number").value || "0";
  $("factor-value").textContent = $("factor-number").value || "0";
}

function setBadge(label, state) {
  runBadge.textContent = label;
  runBadge.className = `run-badge ${state}`;
}

function showError(message) {
  runTitle.textContent = "Execution failed";
  setBadge("FAILED", "error");
  runOutput.replaceChildren();
  const error = document.createElement("p");
  error.className = "error-message";
  error.textContent = message;
  runOutput.append(error);
  $("result-value").textContent = "—";
}

async function request(path, body, method = body === undefined ? "GET" : "POST") {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method) && csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }
  const response = await fetch(path, {
    method,
    headers,
    credentials: "same-origin",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail;
    const message = Array.isArray(detail) ? detail.map((item) => item.msg).join("; ") : detail;
    throw new Error(message || `Request failed (${response.status})`);
  }
  return data;
}

function showResults(result) {
  if (result.status !== "succeeded") {
    const failed = Object.values(result.nodes).find((node) => node.status === "failed");
    showError(failed?.error || "The workflow could not be completed.");
    return;
  }
  runTitle.textContent = result.run_id ? `Run completed · ${result.run_id.slice(0, 8)}` : "Run completed";
  setBadge("SUCCEEDED", "success");
  $("result-value").textContent = String(result.output ?? "null");
  const fragment = document.createDocumentFragment();
  for (const [nodeId, node] of Object.entries(result.nodes)) {
    const row = document.createElement("div");
    row.className = "node-result";
    const check = document.createElement("span");
    check.className = "result-check";
    check.textContent = "✓";
    const name = document.createElement("span");
    name.className = "result-name";
    name.textContent = nodeId;
    const value = document.createElement("code");
    value.className = "result-value";
    value.textContent = String(node.output ?? "null");
    row.append(check, name, value);
    fragment.append(row);
  }
  runOutput.replaceChildren(fragment);
}

for (const id of ["input-number", "factor-number"]) {
  $(id).addEventListener("input", syncPreview);
}

validateButton.addEventListener("click", async () => {
  validateButton.disabled = true;
  validateButton.querySelector("span").textContent = "Validating…";
  try {
    const result = await request("/api/workflows/validate", makeWorkflow());
    runTitle.textContent = `Workflow valid · ${result.order.length} nodes`;
    setBadge("VALID", "success");
    runOutput.replaceChildren();
    const message = document.createElement("p");
    message.className = "empty-run";
    message.textContent = `Execution order: ${result.order.join(" → ")}`;
    runOutput.append(message);
  } catch (error) {
    showError(error.message);
  } finally {
    validateButton.disabled = false;
    validateButton.querySelector("span").textContent = "Validate";
  }
});

runButton.addEventListener("click", async () => {
  runButton.disabled = true;
  runButton.textContent = "Running…";
  runTitle.textContent = "Executing workflow";
  setBadge("RUNNING", "running");
  runOutput.replaceChildren();
  try {
    if (workflowDirty || !savedWorkflowId) await saveWorkflow();
    showResults(await request(`/api/workflows/${encodeURIComponent(savedWorkflowId)}/execute`, undefined, "POST"));
  } catch (error) {
    showError(error.message);
  } finally {
    runButton.disabled = false;
    const icon = document.createElement("span");
    icon.className = "play";
    icon.textContent = "▶";
    runButton.replaceChildren(icon, document.createTextNode(" Run workflow"));
  }
});

$("reset-button").addEventListener("click", () => {
  $("workflow-name").value = defaults.name;
  $("input-number").value = defaults.input;
  $("factor-number").value = defaults.factor;
  savedWorkflowId = null;
  $("saved-workflows").value = "";
  markWorkflowDirty();
  $("result-value").textContent = "—";
  runTitle.textContent = "Ready to run";
  setBadge("IDLE", "idle");
  runOutput.replaceChildren();
  const empty = document.createElement("div");
  empty.className = "empty-run";
  const icon = document.createElement("div");
  icon.className = "empty-icon";
  icon.textContent = "⌁";
  const heading = document.createElement("strong");
  heading.textContent = "No runs yet";
  const hint = document.createElement("span");
  hint.textContent = "Execute the workflow to see node results and timing here.";
  empty.append(icon, heading, hint);
  runOutput.append(empty);
  syncPreview();
});

let currentAgentId = null;
let agentCache = [];

function switchPage(page) {
  const agentsPage = page === "agents";
  $("agents-page").hidden = !agentsPage;
  $("workflow-page").hidden = agentsPage;
  $("agents-nav").classList.toggle("active", agentsPage);
  $("workflow-nav").classList.toggle("active", !agentsPage);
  document.querySelector(".crumb strong").textContent = agentsPage ? "Agents" : "Workflow studio";
  if (agentsPage) refreshAgents().catch((error) => showAgentMessage(error.message, true));
}

function showAgentMessage(message, isError = false) {
  const node = $("agent-message");
  node.textContent = message;
  node.classList.toggle("error", isError);
}

function resetAgentEditor() {
  currentAgentId = null;
  $("agent-form").reset();
  $("agent-form-heading").textContent = "New agent";
  $("agent-version").textContent = "DRAFT";
  $("agent-version").className = "run-badge idle";
  $("agent-save").textContent = "Create agent";
  $("agent-archive").hidden = true;
  $("agent-versions").textContent = "Save an agent to see version history.";
  showAgentMessage("");
  renderAgentList();
}

function renderAgentList() {
  const container = $("agent-list");
  if (!agentCache.length) {
    const empty = document.createElement("p");
    empty.className = "empty-run";
    empty.textContent = "No agents yet. Create a local profile to get started.";
    container.replaceChildren(empty);
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const agent of agentCache) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "agent-item";
    button.setAttribute("aria-current", String(agent.id === currentAgentId));
    const name = document.createElement("span");
    name.textContent = agent.name;
    const version = document.createElement("small");
    version.textContent = `v${agent.version}`;
    button.append(name, version);
    button.addEventListener("click", () => loadAgent(agent.id));
    fragment.append(button);
  }
  container.replaceChildren(fragment);
}

async function refreshAgents() {
  const response = await request("/api/agents");
  agentCache = response.agents;
  renderAgentList();
}

async function loadAgent(agentId) {
  try {
    const agent = await request(`/api/agents/${encodeURIComponent(agentId)}`);
    currentAgentId = agent.id;
    $("agent-name").value = agent.name;
    $("agent-instructions").value = agent.config.instructions;
    $("agent-form-heading").textContent = agent.name;
    $("agent-version").textContent = `V${agent.version}`;
    $("agent-version").className = "run-badge success";
    $("agent-save").textContent = "Save new version";
    $("agent-archive").hidden = false;
    showAgentMessage("Configuration loaded.");
    const { versions } = await request(`/api/agents/${encodeURIComponent(agent.id)}/versions`);
    const list = document.createDocumentFragment();
    for (const item of versions) {
      const row = document.createElement("div");
      row.className = "agent-version-row";
      const label = document.createElement("strong");
      label.textContent = `Version ${item.version}`;
      const date = document.createElement("time");
      date.dateTime = item.created_at;
      date.textContent = new Date(item.created_at).toLocaleString();
      row.append(label, date);
      list.append(row);
    }
    $("agent-versions").replaceChildren(list);
    renderAgentList();
  } catch (error) {
    showAgentMessage(error.message, true);
  }
}

$("workflow-nav").addEventListener("click", (event) => {
  event.preventDefault();
  switchPage("workflow");
});
$("agents-nav").addEventListener("click", (event) => {
  event.preventDefault();
  switchPage("agents");
});
$("new-agent-button").addEventListener("click", resetAgentEditor);
$("agent-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!event.currentTarget.reportValidity()) return;
  const button = $("agent-save");
  button.disabled = true;
  showAgentMessage("");
  const payload = {
    name: $("agent-name").value.trim(),
    instructions: $("agent-instructions").value,
    provider: "demo",
    model: "deterministic",
    tool_allowlist: [],
    memory_policy: "disabled",
  };
  try {
    const saved = await request(
      currentAgentId ? `/api/agents/${encodeURIComponent(currentAgentId)}` : "/api/agents",
      payload,
      currentAgentId ? "PUT" : "POST",
    );
    currentAgentId = saved.id;
    $("agent-form-heading").textContent = saved.name;
    $("agent-version").textContent = `V${saved.version}`;
    $("agent-version").className = "run-badge success";
    $("agent-save").textContent = "Save new version";
    $("agent-archive").hidden = false;
    showAgentMessage(`Saved configuration version ${saved.version}.`);
    await refreshAgents();
    await loadAgent(saved.id);
  } catch (error) {
    showAgentMessage(error.message, true);
  } finally {
    button.disabled = false;
  }
});
$("agent-archive").addEventListener("click", async () => {
  if (!currentAgentId || !window.confirm("Archive this agent? Its version history will be retained.")) return;
  try {
    await request(`/api/agents/${encodeURIComponent(currentAgentId)}`, {}, "DELETE");
    resetAgentEditor();
    await refreshAgents();
    showAgentMessage("Agent archived. Its configuration history is retained.");
  } catch (error) {
    showAgentMessage(error.message, true);
  }
});

syncPreview();
initializeAuthentication();

