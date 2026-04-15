const state = {
  preset: "today",
  members: [],
  rankings: { daily: [], weekly: [], monthly: [] },
  selectedEmail: null,
  search: "",
};

const elements = {
  errorBanner: document.getElementById("errorBanner"),
  presetGroup: document.getElementById("presetGroup"),
  currentRangeLabel: document.getElementById("currentRangeLabel"),
  memberCountPill: document.getElementById("memberCountPill"),
  memberTableBody: document.getElementById("memberTableBody"),
  memberSearch: document.getElementById("memberSearch"),
  dailyRanking: document.getElementById("dailyRanking"),
  weeklyRanking: document.getElementById("weeklyRanking"),
  monthlyRanking: document.getElementById("monthlyRanking"),
  customStart: document.getElementById("customStart"),
  customEnd: document.getElementById("customEnd"),
  applyCustomRange: document.getElementById("applyCustomRange"),
  statMembers: document.getElementById("statMembers"),
  statRequests: document.getElementById("statRequests"),
  statTokens: document.getElementById("statTokens"),
};

function formatNumber(value) {
  return new Intl.NumberFormat("zh-CN").format(value || 0);
}

function showError(message) {
  elements.errorBanner.textContent = message;
  elements.errorBanner.classList.remove("hidden");
}

function clearError() {
  elements.errorBanner.textContent = "";
  elements.errorBanner.classList.add("hidden");
}

function updatePresetButtons() {
  for (const button of elements.presetGroup.querySelectorAll(".preset-button")) {
    button.classList.toggle("active", button.dataset.preset === state.preset);
  }
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(payload.detail || response.statusText);
  }
  return response.json();
}

function renderSummary(summary, meta) {
  elements.statMembers.textContent = formatNumber(summary.total_members);
  elements.statRequests.textContent = formatNumber(summary.total_request_count);
  elements.statTokens.textContent = formatNumber(summary.total_used_tokens);
  elements.currentRangeLabel.textContent = `当前范围 · ${meta.label}`;
}

function filteredMembers() {
  const keyword = state.search.trim().toLowerCase();
  if (!keyword) {
    return state.members;
  }
  return state.members.filter((member) =>
    [member.display_name, member.username, member.email].some((value) =>
      String(value || "").toLowerCase().includes(keyword)
    )
  );
}

async function saveAlias(email, alias) {
  const payload = await fetchJson("/api/aliases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, alias }),
  });
  state.members = state.members.map((member) =>
    member.email === email
      ? { ...member, alias: payload.alias, display_name: payload.alias || member.raw_display_name || member.username || member.email }
      : member
  );
  await loadRankings();
  renderMembers();
}

function createAliasEditor(member) {
  const wrapper = document.createElement("div");
  wrapper.className = "alias-editor";

  const input = document.createElement("input");
  input.className = "alias-input";
  input.value = member.alias || "";
  input.placeholder = member.display_name;
  input.disabled = !member.email;

  const button = document.createElement("button");
  button.className = "save-button";
  button.type = "button";
  button.textContent = "保存";
  button.disabled = !member.email;
  button.addEventListener("click", async () => {
    try {
      clearError();
      await saveAlias(member.email, input.value);
    } catch (error) {
      showError(error.message);
    }
  });

  wrapper.appendChild(input);
  wrapper.appendChild(button);
  return wrapper;
}

function renderMembers() {
  const members = filteredMembers();
  elements.memberCountPill.textContent = `${members.length} 人`;
  elements.memberTableBody.innerHTML = "";

  if (members.length === 0) {
    const row = document.createElement("tr");
    row.innerHTML = `<td colspan="8"><div class="empty-state">当前条件下没有成员数据</div></td>`;
    elements.memberTableBody.appendChild(row);
    return;
  }

  for (const member of members) {
    const row = document.createElement("tr");
    row.dataset.email = member.email;
    row.classList.toggle("row-selected", member.email === state.selectedEmail);

    const aliasCell = document.createElement("td");
    aliasCell.appendChild(createAliasEditor(member));
    row.appendChild(aliasCell);

    row.insertAdjacentHTML(
      "beforeend",
      `
        <td>${member.username || "-"}</td>
        <td>${member.email || "-"}</td>
        <td>${member.role || "-"}</td>
        <td>${member.user_group || "-"}</td>
        <td>${formatNumber(member.request_count)}</td>
        <td>${formatNumber(member.used_tokens)}</td>
        <td>${formatNumber(member.used_quota)}</td>
      `
    );
    elements.memberTableBody.appendChild(row);
  }
}

function renderRankingList(target, items) {
  target.innerHTML = "";
  if (!items.length) {
    target.innerHTML = `<li class="empty-state">暂无排行数据</li>`;
    return;
  }

  items.forEach((item, index) => {
    const element = document.createElement("li");
    element.className = "ranking-item";
    element.innerHTML = `
      <strong>${index + 1}</strong>
      <div class="ranking-name">
        <span>${item.display_name}</span>
        <small>${item.email || item.username}</small>
      </div>
      <span class="token-value">${formatNumber(item.used_tokens)}</span>
    `;
    element.addEventListener("click", () => {
      state.selectedEmail = item.email;
      renderMembers();
      const row = elements.memberTableBody.querySelector(`tr[data-email="${CSS.escape(item.email)}"]`);
      if (row) {
        row.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
    target.appendChild(element);
  });
}

function renderRankings() {
  renderRankingList(elements.dailyRanking, state.rankings.daily);
  renderRankingList(elements.weeklyRanking, state.rankings.weekly);
  renderRankingList(elements.monthlyRanking, state.rankings.monthly);
}

async function loadDashboard(params = new URLSearchParams({ preset: state.preset })) {
  const payload = await fetchJson(`/api/dashboard?${params.toString()}`);
  state.members = payload.members;
  renderSummary(payload.summary, payload.meta);
  renderMembers();
}

async function loadRankings() {
  state.rankings = await fetchJson("/api/rankings");
  renderRankings();
}

async function loadAll(params) {
  try {
    clearError();
    await Promise.all([loadDashboard(params), loadRankings()]);
  } catch (error) {
    showError(error.message);
  }
}

function dateToTimestamps() {
  const startDate = elements.customStart.value;
  const endDate = elements.customEnd.value;
  if (!startDate || !endDate) {
    throw new Error("请先选择开始和结束日期");
  }
  const start = new Date(`${startDate}T00:00:00`);
  const end = new Date(`${endDate}T23:59:59`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start >= end) {
    throw new Error("自定义日期范围无效");
  }
  return {
    start_timestamp: Math.floor(start.getTime() / 1000),
    end_timestamp: Math.floor(end.getTime() / 1000),
  };
}

elements.presetGroup.addEventListener("click", (event) => {
  const button = event.target.closest(".preset-button");
  if (!button) {
    return;
  }
  state.preset = button.dataset.preset;
  updatePresetButtons();
  loadAll(new URLSearchParams({ preset: state.preset }));
});

elements.applyCustomRange.addEventListener("click", () => {
  try {
    const range = dateToTimestamps();
    state.preset = "custom";
    updatePresetButtons();
    loadAll(new URLSearchParams(range));
  } catch (error) {
    showError(error.message);
  }
});

elements.memberSearch.addEventListener("input", (event) => {
  state.search = event.target.value;
  renderMembers();
});

updatePresetButtons();
loadAll(new URLSearchParams({ preset: state.preset }));
