document.addEventListener("DOMContentLoaded", () => {
    /* =========================================
    API
    ========================================= */

    const LIST_API = "/api/analyses/spending-records/";

    const DETAIL_API = (considerationId) =>
        `/api/analyses/considerations/${considerationId}/spending-record/`;

    const STATS_API = "/api/analyses/spending-records/stats/";


    /* =========================================
    DOM
    ========================================= */

    const consumptionList =
        document.getElementById("consumption-list");

    const emptyState =
        document.getElementById("empty-state");

    const loadMoreButton =
        document.getElementById("load-more-button");

    const statusButtons =
        document.querySelectorAll(".status-button");

    const purposeFilter =
        document.getElementById("purpose-filter");

    const dateFromFilter =
        document.getElementById("date-from");

    const dateToFilter =
        document.getElementById("date-to");

    const dateFilterReset =
        document.getElementById("date-filter-reset");


    /* Modal */

    const modal =
        document.getElementById("consumption-modal");

    const modalOverlay =
        document.getElementById("modal-overlay");

    const modalClose =
        document.getElementById("modal-close");

    const modalProductImage =
        document.getElementById("modal-product-image");

    const modalCategory =
        document.getElementById("modal-category");

    const modalProductName =
        document.getElementById("modal-product-name");

    const modalPrice =
        document.getElementById("modal-price");

    const modalRecordDate =
        document.getElementById("modal-record-date");

    const modalStatus =
        document.getElementById("modal-status");

    const modalRealPrice =
        document.getElementById("modal-real-price");

    const modalPurpose =
        document.getElementById("modal-purpose");

    const modalSatisfactionStars =
        document.getElementById("modal-satisfaction-stars");

    const modalAnalysisText =
        document.getElementById("modal-analysis-text");


    /* 수정 모드 */

    const modalStatusSelect =
        document.getElementById("modal-status-select");

    const modalPurposeSelect =
        document.getElementById("modal-purpose-select");

    const modalSatisfactionEdit =
        document.getElementById("modal-satisfaction-edit");

    const modalEditButton =
        document.getElementById("modal-edit-button");

    const modalEditCancel =
        document.getElementById("modal-edit-cancel");

    const modalEditError =
        document.getElementById("modal-edit-error");


    /* Summary */

    const monthlySpending =
        document.getElementById("monthly-spending");

    const mostSpentCategory =
        document.getElementById("most-spent-category");

    const averageSatisfaction =
        document.getElementById("average-satisfaction");

    const purchaseRate =
        document.getElementById("purchase-rate");


    /* =========================================
    상태
    ========================================= */

    let currentStatus = "all";
    let currentPage = 1;
    const pageSize = 10;

    let consumptionData = [];
    let hasNext = false;


    /* 상세 팝업에 띄운 기록 */

    let currentRecord = null;
    let isEditing = false;

    /* 수정 모드에서 고른 별점. 저장 전까지는 서버 값과 별개입니다. */
    let editSatisfaction = null;


    /* =========================================
    공통 함수
    ========================================= */

    /* 필터가 바뀌면 누적된 목록을 버리고 1페이지부터 다시 불러옵니다. */

    function reloadFromFirstPage() {

        currentPage = 1;

        consumptionData = [];


        fetchSpendingRecords({
            page: 1,
            append: false,
        });
    }


    function formatPrice(price) {
        if (price === null || price === undefined) {
            return "—";
        }

        return `${Number(price).toLocaleString("ko-KR")}원`;
    }


    function getStatusClass(status) {
        if (status === "PURCHASED") {
            return "purchased";
        }

        if (status === "DEFERRED") {
            return "pending";
        }

        return "not-purchased";
    }


    function renderStars(score) {
        if (score === null || score === undefined) {
            return `
                <span class="item-stars empty">-</span>
            `;
        }

        return `
            <span class="item-stars">
                ${"★".repeat(score)}
                ${"☆".repeat(5 - score)}
            </span>
        `;
    }


    function renderModalStars(score) {
        if (score === null || score === undefined) {
            return "-";
        }

        return (
            "★".repeat(score) +
            "☆".repeat(5 - score)
        );
    }


    /* =========================================
    상단 요약 통계 API
    ========================================= */

    async function fetchSpendingStats() {
        try {
            const currentDate = new Date();

            const year =
                currentDate.getFullYear();

            const month =
                String(currentDate.getMonth() + 1)
                    .padStart(2, "0");

            const response = await fetch(
                `${STATS_API}?month=${year}-${month}`,
                {
                    method: "GET",
                    headers: {
                        "Accept": "application/json",
                    },
                    credentials: "same-origin",
                }
            );


            if (!response.ok) {
                throw new Error(
                    `통계 API 요청 실패: ${response.status}`
                );
            }


            const data =
                await response.json();


            renderSummary(data);

        } catch (error) {
            console.error(
                "소비 통계 API 요청 실패:",
                error
            );

            renderSummaryError();
        }
    }


    /* =========================================
    상단 요약 카드 출력
    ========================================= */

    function renderSummary(data) {

        /* 이번 달 소비 금액 */

        if (monthlySpending) {
            monthlySpending.textContent =
                data.total_spent_display || "0원";
        }


        /* 가장 많이 소비한 분야 */

        if (mostSpentCategory) {
            mostSpentCategory.textContent =
                data.top_category?.name || "—";
        }


        /* 평균 만족도 */

        if (averageSatisfaction) {
            averageSatisfaction.textContent =
                data.average_satisfaction_display || "—";
        }


        /* 구매 확정률 */

        if (purchaseRate) {
            purchaseRate.textContent =
                data.purchase_rate_display || "0%";
        }
    }


    function renderSummaryError() {

        if (monthlySpending) {
            monthlySpending.textContent = "—";
        }

        if (mostSpentCategory) {
            mostSpentCategory.textContent = "—";
        }

        if (averageSatisfaction) {
            averageSatisfaction.textContent = "—";
        }

        if (purchaseRate) {
            purchaseRate.textContent = "—";
        }
    }


    /* =========================================
    소비 기록 목록 API
    ========================================= */

    async function fetchSpendingRecords({
        page = 1,
        append = false,
    } = {}) {

        const params = new URLSearchParams();

        params.set("page", page);
        params.set("page_size", pageSize);


        /* 구매 상태 */

        if (currentStatus !== "all") {
            params.set(
                "purchase_status",
                currentStatus
            );
        }


        /* 목적 */

        if (
            purposeFilter &&
            purposeFilter.value !== "all"
        ) {
            params.set(
                "purpose",
                purposeFilter.value
            );
        }


        /* 기간 — 한쪽만 골라도 그 방향으로만 걸립니다. */

        if (
            dateFromFilter &&
            dateFromFilter.value
        ) {
            params.set(
                "date_from",
                dateFromFilter.value
            );
        }


        if (
            dateToFilter &&
            dateToFilter.value
        ) {
            params.set(
                "date_to",
                dateToFilter.value
            );
        }


        try {
            const response = await fetch(
                `${LIST_API}?${params.toString()}`,
                {
                    method: "GET",
                    headers: {
                        "Accept": "application/json",
                    },
                    credentials: "same-origin",
                }
            );


            if (!response.ok) {
                throw new Error(
                    `API 요청 실패: ${response.status}`
                );
            }


            const data =
                await response.json();


            if (append) {
                consumptionData = [
                    ...consumptionData,
                    ...data.results,
                ];
            } else {
                consumptionData =
                    data.results;
            }


            currentPage =
                data.page;

            hasNext =
                data.has_next;


            renderList();

        } catch (error) {

            console.error(
                "소비 기록 API 요청 실패:",
                error
            );

            consumptionData = [];

            hasNext = false;

            renderList();
        }
    }


    /* =========================================
    소비 카드 생성
    ========================================= */

    function createConsumptionCard(item) {

        const statusClass =
            getStatusClass(
                item.purchase_status
            );


        const imageContent =
            item.image_url
                ? `
                    <img
                        src="${item.image_url}"
                        alt="${item.product_name}"
                    >
                `
                : "🛍️";


        return `
            <article
                class="consumption-item"
                data-id="${item.id}"
                data-consideration-id="${item.consideration_id}"
                tabindex="0"
            >

                <div class="product-thumbnail">
                    ${imageContent}
                </div>


                <div class="product-main">

                    <div class="product-name">
                        ${item.product_name}
                    </div>

                    <div class="product-meta">
                        <span>
                            ${item.category || "—"}
                        </span>

                        <span>
                            ${item.purpose_display || "—"}
                        </span>
                    </div>

                </div>


                <div class="item-info">

                    <div class="item-info-label">
                        기록 날짜
                    </div>

                    <div class="item-info-value">
                        ${item.recorded_on_display || "—"}
                    </div>

                </div>


                <div class="item-info">

                    <div class="item-info-label">
                        실제 가격
                    </div>

                    <div class="item-info-value">
                        ${item.product_price_display || "—"}
                    </div>

                </div>


                <div class="purchase-status ${statusClass}">
                    ${item.purchase_status_display || "—"}
                </div>


                <div class="item-satisfaction">

                    <div class="item-satisfaction-label">
                        만족도
                    </div>

                    ${renderStars(item.satisfaction)}

                </div>


                <div class="item-arrow">
                    ›
                </div>

            </article>
        `;
    }


    /* =========================================
    리스트 렌더링
    ========================================= */

    function renderList() {

        consumptionList.innerHTML =
            consumptionData
                .map(createConsumptionCard)
                .join("");


        /* 빈 상태 */

        if (consumptionData.length === 0) {

            consumptionList.style.display =
                "none";

            emptyState.classList.remove(
                "hidden"
            );

        } else {

            consumptionList.style.display =
                "grid";

            emptyState.classList.add(
                "hidden"
            );
        }


        /* 더보기 */

        if (hasNext) {

            loadMoreButton.classList.remove(
                "hidden"
            );

        } else {

            loadMoreButton.classList.add(
                "hidden"
            );
        }


        bindConsumptionCards();
    }


    /* =========================================
    카드 이벤트
    ========================================= */

    function bindConsumptionCards() {

        const cards =
            document.querySelectorAll(
                ".consumption-item"
            );


        cards.forEach((card) => {

            card.addEventListener(
                "click",
                () => {

                    const considerationId =
                        card.dataset.considerationId;

                    openModal(
                        considerationId
                    );
                }
            );


            card.addEventListener(
                "keydown",
                (event) => {

                    if (
                        event.key === "Enter" ||
                        event.key === " "
                    ) {

                        event.preventDefault();

                        const considerationId =
                            card.dataset.considerationId;

                        openModal(
                            considerationId
                        );
                    }
                }
            );
        });
    }


    /* =========================================
    상세 API
    ========================================= */

    async function openModal(
        considerationId
    ) {

        try {

            const response = await fetch(
                DETAIL_API(considerationId),
                {
                    method: "GET",
                    headers: {
                        "Accept": "application/json",
                    },
                    credentials: "same-origin",
                }
            );


            if (!response.ok) {
                throw new Error(
                    `상세 API 요청 실패: ${response.status}`
                );
            }


            const item =
                await response.json();


            /* 다른 기록을 열 때 이전 수정 상태가 남지 않도록 합니다. */

            exitEditMode();

            renderModal(item);


            modal.classList.remove(
                "hidden"
            );

            modal.setAttribute(
                "aria-hidden",
                "false"
            );

            document.body.classList.add(
                "modal-open"
            );

        } catch (error) {

            console.error(
                "소비 기록 상세 조회 실패:",
                error
            );
        }
    }


    /* =========================================
    상세 팝업 데이터 출력
    ========================================= */

    function renderModal(item) {

        currentRecord = item;


        if (item.image_url) {

            modalProductImage.innerHTML = `
                <img
                    src="${item.image_url}"
                    alt="${item.product_name}"
                    style="
                        width: 100%;
                        height: 100%;
                        object-fit: cover;
                    "
                >
            `;

        } else {

            modalProductImage.textContent =
                "🛍️";
        }


        modalCategory.textContent =
            item.category || "—";


        modalProductName.textContent =
            item.product_name || "—";


        modalPrice.textContent =
            item.product_price_display || "—";


        modalRecordDate.textContent =
            item.recorded_on_display || "—";


        modalRealPrice.textContent =
            item.product_price_display || "—";


        modalPurpose.textContent =
            item.purpose_display || "—";


        modalStatus.textContent =
            item.purchase_status_display || "—";


        modalStatus.className =
            `modal-status ${getStatusClass(
                item.purchase_status
            )}`;


        modalSatisfactionStars.textContent =
            renderModalStars(
                item.satisfaction
            );


        /* 초이지 분석 */

        if (item.decision) {

            modalAnalysisText.textContent =
                item.decision.summary ||
                "초이지 AI가 분석한 소비 기록이에요.";

        } else {

            modalAnalysisText.textContent =
                "이 소비 기록에는 아직 AI 의사결정 분석 결과가 없어요.";
        }
    }


    /* =========================================
    소비 기록 수정

    바꿀 수 있는 값은 구매 여부와 만족도뿐입니다. 목적은 기록 당시
    값(`purpose_snapshot`)이라 서버가 수정을 받지 않습니다. (API.md §8.7)
    ========================================= */

    function getCsrfToken() {

        const input =
            document.querySelector(
                "[name=csrfmiddlewaretoken]"
            );

        return input ? input.value : "";
    }


    function showEditError(message) {

        modalEditError.textContent = message;

        modalEditError.classList.remove("hidden");
    }


    function hideEditError() {

        modalEditError.textContent = "";

        modalEditError.classList.add("hidden");
    }


    /* 셀렉트 글자색을 고른 상태에 맞춥니다. 읽기 전용 표시와 같은
       클래스를 써서 색은 CSS 한 곳에서만 정의합니다. */

    function applyStatusSelectColor() {

        modalStatusSelect.classList.remove(
            "purchased",
            "pending",
            "not-purchased"
        );

        modalStatusSelect.classList.add(
            getStatusClass(
                modalStatusSelect.value
            )
        );
    }


    /* 고른 점수까지 별을 채웁니다. */

    function renderEditStars() {

        const isPurchased =
            modalStatusSelect.value === "PURCHASED";


        modalSatisfactionEdit.classList.toggle(
            "disabled",
            !isPurchased
        );


        modalSatisfactionEdit
            .querySelectorAll(".star-button")
            .forEach((button) => {

                const score =
                    Number(button.dataset.score);


                button.disabled = !isPurchased;

                button.classList.toggle(
                    "filled",
                    isPurchased &&
                    editSatisfaction !== null &&
                    score <= editSatisfaction
                );
            });
    }


    function enterEditMode() {

        if (!currentRecord) {
            return;
        }


        isEditing = true;

        hideEditError();


        modalStatusSelect.value =
            currentRecord.purchase_status;

        editSatisfaction =
            currentRecord.satisfaction ?? null;


        /* 기록에 목적이 비어 있으면 어떤 항목도 고르지 않은 상태로
           둡니다. 임의로 하나를 채우면 사용자가 고르지 않은 값이
           저장됩니다. */

        modalPurposeSelect.value =
            currentRecord.purpose || "";


        modalStatus.classList.add("hidden");

        modalStatusSelect.classList.remove("hidden");


        modalPurpose.classList.add("hidden");

        modalPurposeSelect.classList.remove("hidden");


        modalSatisfactionStars.classList.add("hidden");

        modalSatisfactionEdit.classList.remove("hidden");


        modalEditCancel.classList.remove("hidden");

        modalEditButton.textContent = "저장";


        applyStatusSelectColor();

        renderEditStars();
    }


    function exitEditMode() {

        isEditing = false;

        editSatisfaction = null;

        hideEditError();


        modalStatus.classList.remove("hidden");

        modalStatusSelect.classList.add("hidden");


        modalPurpose.classList.remove("hidden");

        modalPurposeSelect.classList.add("hidden");


        modalSatisfactionStars.classList.remove("hidden");

        modalSatisfactionEdit.classList.add("hidden");


        modalEditCancel.classList.add("hidden");

        modalEditButton.textContent = "수정";

        modalEditButton.disabled = false;
    }


    async function saveRecord() {

        const purchaseStatus =
            modalStatusSelect.value;


        /* 구매함은 만족도가 반드시 있어야 합니다. 서버도 같은 규칙으로
           400을 주지만 먼저 걸러 왕복을 줄입니다. (API.md §8.7) */

        const satisfaction =
            purchaseStatus === "PURCHASED"
                ? editSatisfaction
                : null;


        if (
            purchaseStatus === "PURCHASED" &&
            satisfaction === null
        ) {
            showEditError(
                "구매함으로 저장하려면 만족도를 선택해주세요."
            );

            return;
        }


        const payload = {
            purchase_status: purchaseStatus,
            satisfaction: satisfaction,
        };


        /* 목적은 값이 있을 때만 보냅니다. 서버는 목적이 빠진 요청에서
           기존 값을 그대로 둡니다. (API.md §8.7) */

        if (modalPurposeSelect.value) {
            payload.purpose = modalPurposeSelect.value;
        }


        hideEditError();

        modalEditButton.disabled = true;

        modalEditButton.textContent = "저장 중...";


        try {

            const response = await fetch(
                DETAIL_API(
                    currentRecord.consideration_id
                ),
                {
                    method: "PATCH",
                    headers: {
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCsrfToken(),
                    },
                    credentials: "same-origin",
                    body: JSON.stringify(payload),
                }
            );


            if (!response.ok) {
                throw new Error(
                    `소비 기록 수정 실패: ${response.status}`
                );
            }


            const item =
                await response.json();


            exitEditMode();

            renderModal(item);


            /* 목록 카드와 요약 카드(구매 확정률·평균 만족도)가 함께
               달라지므로 둘 다 다시 부릅니다. */

            reloadFromFirstPage();

            fetchSpendingStats();

        } catch (error) {

            console.error(
                "소비 기록 수정 실패:",
                error
            );

            modalEditButton.disabled = false;

            modalEditButton.textContent = "저장";

            showEditError(
                "저장하지 못했어요. 잠시 후 다시 시도해주세요."
            );
        }
    }


    if (modalEditButton) {

        modalEditButton.addEventListener(
            "click",
            () => {

                if (isEditing) {

                    saveRecord();

                } else {

                    enterEditMode();
                }
            }
        );
    }


    if (modalEditCancel) {

        modalEditCancel.addEventListener(
            "click",
            () => {

                exitEditMode();


                /* 화면을 수정 전 값으로 돌려놓습니다. */

                if (currentRecord) {
                    renderModal(currentRecord);
                }
            }
        );
    }


    if (modalStatusSelect) {

        modalStatusSelect.addEventListener(
            "change",
            () => {

                /* 구매 보류·구매 안 함으로 바꾸면 만족도는 저장할 수
                   없으므로 고른 별점을 버립니다. */

                if (modalStatusSelect.value !== "PURCHASED") {
                    editSatisfaction = null;
                }

                hideEditError();

                applyStatusSelectColor();

                renderEditStars();
            }
        );
    }


    if (modalSatisfactionEdit) {

        modalSatisfactionEdit.addEventListener(
            "click",
            (event) => {

                const button =
                    event.target.closest(".star-button");


                if (!button || button.disabled) {
                    return;
                }


                const score =
                    Number(button.dataset.score);


                /* 같은 별을 다시 누르면 선택을 해제합니다. */

                editSatisfaction =
                    editSatisfaction === score
                        ? null
                        : score;


                hideEditError();

                renderEditStars();
            }
        );
    }


    /* =========================================
    팝업 닫기
    ========================================= */

    function closeModal() {

        /* 저장하지 않은 수정은 버립니다. 다시 열 때 서버 값을 새로
           받아오므로 화면을 되돌릴 필요는 없습니다. */

        exitEditMode();


        modal.classList.add(
            "hidden"
        );

        modal.setAttribute(
            "aria-hidden",
            "true"
        );

        document.body.classList.remove(
            "modal-open"
        );
    }


    modalClose.addEventListener(
        "click",
        closeModal
    );


    modalOverlay.addEventListener(
        "click",
        closeModal
    );


    document.addEventListener(
        "keydown",
        (event) => {

            if (
                event.key === "Escape" &&
                !modal.classList.contains(
                    "hidden"
                )
            ) {
                closeModal();
            }
        }
    );


    /* =========================================
    구매 상태 필터
    ========================================= */

    statusButtons.forEach((button) => {

        button.addEventListener(
            "click",
            () => {

                statusButtons.forEach(
                    (item) =>
                        item.classList.remove(
                            "active"
                        )
                );


                button.classList.add(
                    "active"
                );


                currentStatus =
                    button.dataset.status;


                reloadFromFirstPage();
            }
        );
    });


    /* =========================================
    목적 필터
    ========================================= */

    if (purposeFilter) {

        purposeFilter.addEventListener(
            "change",
            () => {

                reloadFromFirstPage();
            }
        );
    }


    /* =========================================
    기간 필터
    ========================================= */

    /* 달력에서 애초에 뒤집힌 기간을 못 고르도록 서로의 한계를 걸어둡니다. */

    function syncDateBounds() {

        if (!dateFromFilter || !dateToFilter) {
            return;
        }


        dateFromFilter.max =
            dateToFilter.value || "";

        dateToFilter.min =
            dateFromFilter.value || "";


        if (dateFilterReset) {

            const hasValue =
                Boolean(
                    dateFromFilter.value ||
                    dateToFilter.value
                );


            dateFilterReset.classList.toggle(
                "hidden",
                !hasValue
            );
        }
    }


    if (dateFromFilter && dateToFilter) {

        dateFromFilter.addEventListener(
            "change",
            () => {

                /* 시작일을 종료일보다 뒤로 옮기면 하루짜리 기간으로
                   맞춥니다. 빈 목록을 내려주는 것보다 낫습니다. */

                if (
                    dateToFilter.value &&
                    dateFromFilter.value > dateToFilter.value
                ) {
                    dateToFilter.value =
                        dateFromFilter.value;
                }


                syncDateBounds();

                reloadFromFirstPage();
            }
        );


        dateToFilter.addEventListener(
            "change",
            () => {

                if (
                    dateFromFilter.value &&
                    dateToFilter.value < dateFromFilter.value
                ) {
                    dateFromFilter.value =
                        dateToFilter.value;
                }


                syncDateBounds();

                reloadFromFirstPage();
            }
        );
    }


    if (dateFilterReset) {

        dateFilterReset.addEventListener(
            "click",
            () => {

                dateFromFilter.value = "";

                dateToFilter.value = "";


                syncDateBounds();

                reloadFromFirstPage();
            }
        );
    }


    /* =========================================
    더보기
    ========================================= */

    loadMoreButton.addEventListener(
        "click",
        () => {

            if (!hasNext) {
                return;
            }


            fetchSpendingRecords({
                page: currentPage + 1,
                append: true,
            });
        }
    );


    /* =========================================
    초기 실행
    ========================================= */

    /* 새로고침 때 브라우저가 날짜 입력값을 복원하는 경우가 있어
       초기 상태를 화면과 한 번 맞춰둡니다. */

    syncDateBounds();


    fetchSpendingStats();

    fetchSpendingRecords({
        page: 1,
        append: false,
    });
});