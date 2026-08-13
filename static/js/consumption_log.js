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

    const categoryFilter =
        document.getElementById("category-filter");

    const purposeFilter =
        document.getElementById("purpose-filter");

    const dateFilter =
        document.getElementById("date-filter");


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


    /* =========================================
    공통 함수
    ========================================= */

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


        /* 분야 */

        if (
            categoryFilter &&
            categoryFilter.value !== "all"
        ) {
            params.set(
                "category",
                categoryFilter.value
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


        /* 날짜 */

        if (
            dateFilter &&
            dateFilter.value
        ) {
            params.set(
                "date_from",
                dateFilter.value
            );

            params.set(
                "date_to",
                dateFilter.value
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
    팝업 닫기
    ========================================= */

    function closeModal() {

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


                currentPage = 1;

                consumptionData = [];


                fetchSpendingRecords({
                    page: 1,
                    append: false,
                });
            }
        );
    });


    /* =========================================
    분야 필터
    ========================================= */

    if (categoryFilter) {

        categoryFilter.addEventListener(
            "change",
            () => {

                currentPage = 1;

                consumptionData = [];


                fetchSpendingRecords({
                    page: 1,
                    append: false,
                });
            }
        );
    }


    /* =========================================
    목적 필터
    ========================================= */

    if (purposeFilter) {

        purposeFilter.addEventListener(
            "change",
            () => {

                currentPage = 1;

                consumptionData = [];


                fetchSpendingRecords({
                    page: 1,
                    append: false,
                });
            }
        );
    }


    /* =========================================
    날짜 필터
    ========================================= */

    if (dateFilter) {

        dateFilter.addEventListener(
            "change",
            () => {

                currentPage = 1;

                consumptionData = [];


                fetchSpendingRecords({
                    page: 1,
                    append: false,
                });
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

    fetchSpendingStats();

    fetchSpendingRecords({
        page: 1,
        append: false,
    });
});