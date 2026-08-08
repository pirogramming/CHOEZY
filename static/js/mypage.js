function getCookie(name) {
  const match = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
  return match ? decodeURIComponent(match[2]) : null;
}

const csrftoken = getCookie("csrftoken");

async function apiPatch(url, data) {
  const res = await fetch(url, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrftoken,
    },
    credentials: "same-origin",
    body: JSON.stringify(data),
  });

  const body = await res.json().catch(() => ({}));

  if (!res.ok) {
    const message = Object.values(body).flat().join("\n") || "수정에 실패했습니다.";
    throw new Error(message);
  }

  return body;
}

function setupChipGroup(groupEl) {
  const max = parseInt(groupEl.dataset.max, 10);
  const chips = groupEl.querySelectorAll(".chip");

  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      if (groupEl.dataset.editing !== "true") return;

      if (max === 1) {
        chips.forEach((c) => c.classList.remove("chip--active"));
        chip.classList.add("chip--active");
        return;
      }

      const activeCount = groupEl.querySelectorAll(".chip--active").length;
      if (chip.classList.contains("chip--active")) {
        chip.classList.remove("chip--active");
      } else if (activeCount < max) {
        chip.classList.add("chip--active");
      }
    });
  });
}

function getActiveCodes(groupEl) {
  return Array.from(groupEl.querySelectorAll(".chip--active")).map(
    (c) => c.dataset.code
  );
}

function setGroupEditable(groupEl, editable) {
  groupEl.dataset.editing = editable ? "true" : "false";
  groupEl.classList.toggle("chip-grid--editing", editable);
}

document.addEventListener("DOMContentLoaded", () => {
  // ---- 기본 정보 ----
  const basicEditBtn = document.getElementById("basic-edit-btn");
  const basicFieldIds = [
    "field-username",
    "field-name",
    "field-birth-date",
    "field-gender",
  ];
  const basicFields = basicFieldIds.map((id) => document.getElementById(id));

  basicEditBtn.addEventListener("click", async () => {
    const isEditing = basicEditBtn.dataset.mode === "edit";

    if (!isEditing) {
      basicFields.forEach((el) => (el.disabled = false));
      basicEditBtn.textContent = "저장";
      basicEditBtn.dataset.mode = "edit";
      return;
    }

    const payload = {
      username: document.getElementById("field-username").value.trim(),
      name: document.getElementById("field-name").value.trim(),
      birth_date: document.getElementById("field-birth-date").value,
      gender: document.getElementById("field-gender").value,
    };

    try {
      await apiPatch("/api/accounts/me/basic/", payload);
      basicFields.forEach((el) => (el.disabled = true));
      basicEditBtn.textContent = "수정";
      basicEditBtn.dataset.mode = "view";
      alert("기본 정보가 수정되었습니다.");
    } catch (err) {
      alert(err.message);
    }
  });

  // ---- 소비성향 + 월 소비 가능 예상 금액 ----
  const spendingGroup = document.getElementById("spending-type-group");
  const budgetGroup = document.getElementById("monthly-budget-group");
  const spendingEditBtn = document.getElementById("spending-edit-btn");

  setupChipGroup(spendingGroup);
  setupChipGroup(budgetGroup);

  spendingEditBtn.addEventListener("click", async () => {
    const isEditing = spendingEditBtn.dataset.mode === "edit";

    if (!isEditing) {
      setGroupEditable(spendingGroup, true);
      setGroupEditable(budgetGroup, true);
      spendingEditBtn.textContent = "저장";
      spendingEditBtn.dataset.mode = "edit";
      return;
    }

    const payload = {
      spending_type: getActiveCodes(spendingGroup),
      monthly_budget: getActiveCodes(budgetGroup)[0] || null,
    };

    try {
      await apiPatch("/api/accounts/me/profile/", payload);
      setGroupEditable(spendingGroup, false);
      setGroupEditable(budgetGroup, false);
      spendingEditBtn.textContent = "수정";
      spendingEditBtn.dataset.mode = "view";
      alert("소비 프로필이 수정되었습니다.");
    } catch (err) {
      alert(err.message);
    }
  });

  // ---- 중요 가치 기준 ----
  const valueGroup = document.getElementById("value-criteria-group");
  const valueEditBtn = document.getElementById("value-edit-btn");

  setupChipGroup(valueGroup);

  valueEditBtn.addEventListener("click", async () => {
    const isEditing = valueEditBtn.dataset.mode === "edit";

    if (!isEditing) {
      setGroupEditable(valueGroup, true);
      valueEditBtn.textContent = "저장";
      valueEditBtn.dataset.mode = "edit";
      return;
    }

    const payload = {
      value_criteria: getActiveCodes(valueGroup),
    };

    try {
      await apiPatch("/api/accounts/me/profile/", payload);
      setGroupEditable(valueGroup, false);
      valueEditBtn.textContent = "수정";
      valueEditBtn.dataset.mode = "view";
      alert("중요 가치 기준이 수정되었습니다.");
    } catch (err) {
      alert(err.message);
    }
  });
});