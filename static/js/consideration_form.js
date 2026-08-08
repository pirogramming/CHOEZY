document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("consideration-form");
  if (!form) return;

  const productUrl = form.querySelector('[name="product_url"]');
  const productName = form.querySelector('[name="product_name"]');
  const productPrice = form.querySelector('[name="product_price"]');
  const purposeDetail = form.querySelector('[name="purpose_detail"]');
  const categoryDetail = form.querySelector('[name="category_detail"]');
  const purposeInputs = Array.from(
    form.querySelectorAll('.choice-list:not(.category) input[type="radio"]')
  );
  const categoryInputs = Array.from(
    form.querySelectorAll('.category input[type="checkbox"]')
  );
  let productConfirmed = false;
  let purposeDetailConfirmed = false;
  let categoryDetailConfirmed = false;

  function syncChoice(input) {
    const item = input.closest(".choice-item");
    if (item) item.classList.toggle("selected", input.checked);
  }

  function syncChoices(inputs) {
    inputs.forEach(syncChoice);
  }

  purposeInputs.forEach((input) => {
    input.addEventListener("change", () => {
      if (input.checked) purposeDetail.value = "";
      syncChoices(purposeInputs);
      resetConfirmButton("purpose");
    });
  });

  categoryInputs.forEach((input) => {
    input.addEventListener("change", () => {
      const selected = categoryInputs.filter((item) => item.checked);
      if (selected.length > 3) {
        input.checked = false;
        alert("비교 분야는 최대 3개까지 선택할 수 있어요.");
      }
      syncChoices(categoryInputs);
      resetConfirmButton("category");
    });
  });

  syncChoices(purposeInputs);
  syncChoices(categoryInputs);

  const previewButton = form.querySelector(".url-row button");
  if (previewButton) {
    previewButton.addEventListener("click", async () => {
      if (!productUrl.value.trim()) {
        alert("상품 URL을 입력해주세요.");
        productUrl.focus();
        return;
      }

      const csrfToken = form.querySelector('[name="csrfmiddlewaretoken"]').value;
      previewButton.disabled = true;

      try {
        const response = await fetch(previewButton.dataset.productPreviewUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          credentials: "same-origin",
          body: JSON.stringify({ url: productUrl.value.trim() }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(
            data.error?.message || "상품 정보를 불러오지 못했습니다."
          );
        }

        productName.value = data.product_name || "";
        productPrice.value = data.product_price || "";
        productUrl.value = data.product_url || productUrl.value.trim();
        productConfirmed = false;
      } catch (error) {
        alert(`${error.message} 상품명과 가격을 직접 입력해주세요.`);
        productName.focus();
      } finally {
        previewButton.disabled = false;
      }
    });
  }

  const productConfirmButton = document.getElementById("product-confirm-btn");

  function validProduct(showAlert = true) {
    const name = productName.value.trim();
    const numericPrice = productPrice.value.replaceAll(",", "").trim();
    const validPrice = /^\d+$/.test(numericPrice) && Number(numericPrice) > 0;

    if (!name) {
      if (showAlert) alert("상품명을 입력해주세요.");
      productName.focus();
      return false;
    }
    if (!validPrice) {
      if (showAlert) alert("상품 가격을 1원 이상의 숫자로 입력해주세요.");
      productPrice.focus();
      return false;
    }
    return true;
  }

  productConfirmButton?.addEventListener("click", () => {
    if (validProduct()) productConfirmed = true;
  });
  [productName, productPrice].forEach((input) => {
    input.addEventListener("input", () => {
      productConfirmed = false;
    });
  });

  function resetConfirmButton(target) {
    if (target === "purpose") purposeDetailConfirmed = false;
    if (target === "category") categoryDetailConfirmed = false;
  }

  function normalizeCategory(value) {
    return value.toLowerCase().replaceAll("·", "").replaceAll("/", "").replaceAll(" ", "");
  }

  const categoryAliases = {
    여행: "여행",
    운동: "운동건강",
    건강: "운동건강",
    운동건강: "운동건강",
    문화: "문화여가",
    여가: "문화여가",
    문화여가: "문화여가",
    생활: "생활편의",
    생활편의: "생활편의",
    디지털: "디지털전자기기",
    전자기기: "디지털전자기기",
    디지털전자기기: "디지털전자기기",
    재정: "재정",
    금융: "재정",
  };

  function markConfirmButton(target) {
    if (target === "purpose") purposeDetailConfirmed = true;
    if (target === "category") categoryDetailConfirmed = true;
  }

  form
    .querySelector('[data-confirm-target="purpose"]')
    ?.addEventListener("click", () => {
      if (!purposeDetail.value.trim()) {
        alert("구매 목적을 입력해주세요.");
        purposeDetail.focus();
        return;
      }
      purposeInputs.forEach((input) => (input.checked = false));
      syncChoices(purposeInputs);
      markConfirmButton("purpose");
    });

  purposeDetail.addEventListener("input", () => resetConfirmButton("purpose"));

  form
    .querySelector('[data-confirm-target="category"]')
    ?.addEventListener("click", () => {
      const typedValue = categoryDetail.value.trim();
      if (!typedValue) {
        alert("비교 분야를 입력해주세요.");
        categoryDetail.focus();
        return;
      }

      const canonical = categoryAliases[normalizeCategory(typedValue)];
      const matchedInput = categoryInputs.find((input) => {
        const label = input.closest(".choice-item")?.textContent || "";
        return normalizeCategory(label) === canonical;
      });

      if (!canonical || !matchedInput) {
        alert(
          "현재 지원하는 비교 분야를 입력해주세요: 여행, 운동·건강, 문화·여가, 생활·편의, 디지털·전자기기, 재정"
        );
        categoryDetail.focus();
        return;
      }

      if (!matchedInput.checked && categoryInputs.filter((input) => input.checked).length >= 3) {
        alert("비교 분야는 최대 3개까지 선택할 수 있어요.");
        return;
      }

      matchedInput.checked = true;
      syncChoices(categoryInputs);
      markConfirmButton("category");
    });

  categoryDetail.addEventListener("input", () => resetConfirmButton("category"));

  document.querySelector(".prev-step")?.addEventListener("click", (event) => {
    const previousUrl = event.currentTarget.dataset.previousUrl;
    window.location.href = previousUrl || "/";
  });

  form.addEventListener("submit", (event) => {
    if (!validProduct()) {
      event.preventDefault();
      return;
    }

    if (!productConfirmed) {
      event.preventDefault();
      alert("상품명과 가격 옆의 확인 버튼을 눌러 상품 정보를 확정해주세요.");
      productConfirmButton?.focus();
      return;
    }

    const hasPurpose =
      purposeInputs.some((input) => input.checked) || purposeDetail.value.trim();
    if (!hasPurpose) {
      event.preventDefault();
      alert("구매 목적을 선택하거나 직접 입력해주세요.");
      purposeInputs[0]?.closest(".choice-card")?.scrollIntoView({ behavior: "smooth" });
      return;
    }

    if (purposeDetail.value.trim() && !purposeDetailConfirmed) {
      event.preventDefault();
      alert("직접 입력한 구매 목적의 확인 버튼을 눌러주세요.");
      purposeDetail.focus();
      return;
    }

    const hasCategory =
      categoryInputs.some((input) => input.checked) || categoryDetail.value.trim();
    if (!hasCategory) {
      event.preventDefault();
      alert("비교 분야를 1개 이상 선택하거나 직접 입력해주세요.");
      categoryInputs[0]?.closest(".choice-card")?.scrollIntoView({ behavior: "smooth" });
      return;
    }

    if (categoryDetail.value.trim() && !categoryDetailConfirmed) {
      event.preventDefault();
      alert("직접 입력한 비교 분야의 확인 버튼을 눌러주세요.");
      categoryDetail.focus();
    }
  });
});
