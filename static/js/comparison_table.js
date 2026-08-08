function formatPrice(value) {
  return Number.isFinite(Number(value))
    ? `${Number(value).toLocaleString("ko-KR")}원`
    : "—";
}

async function getComparisonData(considerationId) {
  const response = await fetch(
    `/api/alternatives/considerations/${considerationId}/comparison/`,
    { credentials: "same-origin" }
  );
  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      body.error?.message || body.detail || "비교 데이터를 불러오지 못했습니다."
    );
  }
  return body;
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value || "—";
}

function renderProduct(product) {
  setText("productName", product?.name);
  setText("productPrice", formatPrice(product?.price));
  setText("productDuration", product?.duration_display);
  setText("productEffect", product?.expected_effect);
}

function renderTable(tab) {
  const rows = Array.isArray(tab?.rows) ? tab.rows : [];

  for (let index = 0; index < 3; index += 1) {
    const row = rows[index];
    const number = index + 1;
    setText(`name${number}`, row?.name);
    setText(`price${number}`, row?.price_display);
    setText(`duration${number}`, row?.duration_display);
    setText(`effect${number}`, row?.expected_effect);
  }
}

function renderCategoryTabs(tabs) {
  const container = document.querySelector(".comparison-category-wrapper");
  if (!container) return;

  container.replaceChildren();
  tabs.forEach((tab, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "comparison-category-btn";
    if (index === 0) button.classList.add("active");
    button.textContent = `${tab.category.emoji || ""} ${tab.category.name}`.trim();

    button.addEventListener("click", () => {
      container
        .querySelectorAll(".comparison-category-btn")
        .forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      renderTable(tab);
    });
    container.appendChild(button);
  });
}

function renderError(message) {
  const container = document.querySelector(".comparison-category-wrapper");
  if (!container) return;
  container.replaceChildren();
  const error = document.createElement("span");
  error.className = "comparison-error";
  error.textContent = message;
  container.appendChild(error);
}

document.addEventListener("DOMContentLoaded", async () => {
  const page = document.querySelector(".comparison-page");
  const idElement = document.getElementById("consideration-id");
  if (!page || !idElement) return;

  const considerationId = JSON.parse(idElement.textContent);
  const previousButton = document.querySelector(".comparison-prev-btn");
  const nextButton = document.querySelector(".comparison-next-btn");

  previousButton?.addEventListener("click", () => {
    window.location.href = page.dataset.previousUrl;
  });
  nextButton?.addEventListener("click", () => {
    window.location.href = page.dataset.nextUrl;
  });

  try {
    const data = await getComparisonData(considerationId);
    const tabs = Array.isArray(data.tabs) ? data.tabs : [];
    if (tabs.length === 0) {
      throw new Error("비교할 대안이 없습니다.");
    }

    renderProduct(data.product);
    renderCategoryTabs(tabs);
    renderTable(tabs[0]);
  } catch (error) {
    renderError(error.message);
  }
});
