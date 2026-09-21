const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.hash.slice(1));
const token = params.get("token");
const title = value => value[0].toUpperCase() + value.slice(1);
const descriptions = {
  scoped: "Uses scoped command allowances. Commands that need approval are denied without prompting.",
  full: "Uses the selected harness’s full-access tool policy. Edit workers can run shell commands without a scoped allowlist. Host and organization restrictions still apply.",
  inherit: "Checks Codex access at each launch or resume. Confirmed full access enables the selected harness’s full-access tool policy; missing or restricted access uses scoped allowances."
};
let saved, catalog, dirty = false;
$("back-workers").href = "/" + location.hash;
async function api(path, options={}) {
  const response = await fetch(path, {...options, headers: {Authorization: `Bearer ${token}`, ...(options.body ? {"Content-Type":"application/json"} : {})}});
  if (!response.ok) throw new Error(response.status === 401 ? "This dashboard link has expired. Ask Codex to reopen it." : `Settings unavailable (${response.status}). Your changes have not been saved.`);
  return response.json();
}
function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}
function modelSelect(id, label, value, tier) {
  const wrapper = node("label", "filter model-choice", label);
  const select = node("select"); select.id = id;
  if (tier) select.add(new Option("Use tier default", ""));
  for (const model of catalog.models) select.add(new Option(title(model), model));
  select.value = value || "";
  wrapper.append(select);
  return wrapper;
}
function render() {
  $("permission-policy").value = saved.permission_policy;
  $("profile-settings").replaceChildren(...catalog.profiles.map(profile => {
    const card = node("div", "profile-setting");
    card.append(modelSelect("profile-"+profile.id, profile.label+" tier", saved.models.profiles[profile.id]));
    card.append(node("p", "settings-note", profile.effort ? `${title(profile.effort)} effort` : "Model default effort"));
    return card;
  }));
  $("task-settings").replaceChildren(...catalog.tasks.map(task => {
    const row = node("div", "task-setting");
    const copy = node("div", "task-setting-copy");
    copy.append(node("h4", null, task.label), node("p", null, task.description));
    const effective = node("p", "effective-model"); effective.id = "effective-"+task.id; copy.append(effective);
    row.append(copy, modelSelect("task-"+task.id, task.label+" model", saved.models.tasks[task.id], task.profile));
    return row;
  }));
  update();
}
function values() {
  return {version: 2, permission_policy: $("permission-policy").value, models: {
    profiles: Object.fromEntries(catalog.profiles.map(p=>[p.id,$("profile-"+p.id).value])),
    tasks: Object.fromEntries(catalog.tasks.map(t=>[t.id,$("task-"+t.id).value || null]))
  }};
}
function update() {
  const draft = values();
  for (const task of catalog.tasks) {
    const select = $("task-"+task.id), model = draft.models.profiles[task.profile];
    select.options[0].text = `Use ${title(task.profile)} default (${title(model)})`;
    const selected = draft.models.tasks[task.id];
    $("effective-"+task.id).textContent = `${title(selected || model)} · ${selected ? "Task override" : title(task.profile)+" tier"}`;
  }
  $("permission-description").textContent = descriptions[draft.permission_policy];
  dirty = draft.permission_policy !== saved.permission_policy
    || catalog.profiles.some(p => draft.models.profiles[p.id] !== saved.models.profiles[p.id])
    || catalog.tasks.some(t => draft.models.tasks[t.id] !== saved.models.tasks[t.id]);
  $("save-settings").disabled = !dirty;
  $("discard-settings").disabled = !dirty;
  $("settings-status").textContent = dirty ? "Unsaved changes" : "All changes saved";
}
async function load() {
  $("settings-fields").disabled = true;
  $("settings-error").hidden = true; $("retry-settings").hidden = true;
  try {
    [saved, catalog] = await Promise.all([api("/api/settings"), api("/api/settings/catalog")]);
    render(); $("settings-fields").disabled = false;
  } catch (error) {
    $("settings-error").textContent = error.message; $("settings-error").hidden = false;
    $("retry-settings").hidden = false; $("settings-status").textContent = "Settings could not be loaded";
  }
}
$("settings-form").onchange = update;
$("discard-settings").onclick = render;
$("retry-settings").onclick = load;
$("settings-form").onsubmit = async event => {
  event.preventDefault();
  const draft = values();
  $("settings-fields").disabled = true; $("settings-status").textContent = "Saving…";
  $("settings-error").hidden = true;
  try {
    saved = await api("/api/settings", {method:"POST", body:JSON.stringify(draft)});
    render(); $("settings-status").textContent = "Saved. Future workers will use these settings.";
  } catch (error) {
    $("settings-error").textContent = error.message; $("settings-error").hidden = false;
    $("settings-status").textContent = "Not saved. Your changes are still here.";
  } finally { $("settings-fields").disabled = false; }
};
window.addEventListener("beforeunload", event => { if (dirty) { event.preventDefault(); event.returnValue = ""; } });
load();
