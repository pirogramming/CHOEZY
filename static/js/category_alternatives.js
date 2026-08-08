function getCookie(name) {
  const match = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
  return match ? decodeURIComponent(match[2]) : null;
}

const csrftoken = getCookie("csrftoken");

async function apiGet(url) {
  const res = await fetch(url, { credentials: "same-origin" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body.message || body.detail || "요청에 실패했습니다.");
  }
  return body;
}

async function apiPost(url) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "X-CSRFToken": csrftoken },
    credentials: "same-origin",
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body.message || body.detail || "요청에 실패했습니다.");
  }
  return body;
}

function priceLine(alt) {
  if (alt.unit_price_display) return alt.unit_price_display;
  return alt.display_text || "";
}

function renderCategory(category) {
  const items = category.alternatives
    .map(
      (alt) => `
    <div class="alt-item" data-alt-id="${alt.id}" data-slot="${alt.slot}">
      <button type="button" class="regen-btn">재생성</button>
      <div class="alt-item__info">
        <div class="alt-item__name">${alt.item.name}</div>
        <div class="alt-item__price">${priceLine(alt)}</div>
      </div>
    </div>`
    )
    .join("");

  return `
  <div class="alt-card" data-category-id="${category.id}">
    <div class="alt-card__header">
      <div class="alt-card__icon-wrap">
        <span class="icon-category">${category.emoji}</span>
      </div>
      <div class="alt-card__title">${category.name}</div>
    </div>
    ${items}
  </div>`;
}

function renderCards(data) {
  const cardsEl = document.getElementById("alt-cards");
  if (!data.categories || data.categories.length === 0) {
    cardsEl.innerHTML = `<p class="alt-loading">생성된 대안이 없습니다.</p>`;
    return;
  }
  cardsEl.innerHTML = data.categories.map(renderCategory).join("");
  attachRegenerateHandlers();
}

async function loadAlternatives(considerationId) {
  const cardsEl = document.getElementById("alt-cards");
  try {
    let data = await apiGet(
      `/api/alternatives/considerations/${considerationId}/`
    );

    if (!data.categories || data.categories.length === 0) {
      cardsEl.innerHTML = `<p class="alt-loading">AI가 대안을 생성하는 중입니다...</p>`;
      data = await apiPost(
        `/api/alternatives/considerations/${considerationId}/generate/`
      );
    }

    renderCards(data);
  } catch (err) {
    cardsEl.innerHTML = `<p class="alt-loading">${err.message}</p>`;
  }
}

function attachRegenerateHandlers() {
  document.querySelectorAll(".alt-item .regen-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const itemEl = btn.closest(".alt-item");
      const altId = itemEl.dataset.altId;
      btn.disabled = true;
      btn.textContent = "생성 중...";
      try {
        const result = await apiPost(`/api/alternatives/${altId}/regenerate/`);
        itemEl.dataset.altId = result.id;
        itemEl.querySelector(".alt-item__name").textContent = result.item.name;
        itemEl.querySelector(".alt-item__price").textContent = priceLine(result);
      } catch (err) {
        alert(err.message);
      } finally {
        btn.disabled = false;
        btn.textContent = "재생성";
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById("alt-page");
  const considerationId = root.dataset.considerationId;
  loadAlternatives(considerationId);
});