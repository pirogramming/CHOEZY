document.addEventListener("DOMContentLoaded", () => {

    /* =========================================
       더미 소비 데이터
       -----------------------------------------
       추후 API 연결 시 이 부분을 fetch로 교체
    ========================================= */

    const consumptionData = [
        {
            id: 1,
            date: "2026.08.03",
            name: "MacBook Air",
            category: "digital",
            categoryName: "전자기기",
            purpose: "study",
            purposeName: "공부/자기계발",
            price: 1390000,
            status: "purchased",
            statusName: "구매함",
            satisfaction: 4,
            image: "💻",
            analysis:
                "구매 전 여러 대안을 비교하고 기회비용을 확인한 소비예요."
        },
        {
            id: 2,
            date: "2026.07.10",
            name: "나이키 에어포스 1",
            category: "fashion",
            categoryName: "패션",
            purpose: "daily",
            purposeName: "일상",
            price: 129000,
            status: "purchased",
            statusName: "구매함",
            satisfaction: 4,
            image: "👟",
            analysis:
                "필요성과 가격을 비교한 뒤 구매한 소비예요."
        },
        {
            id: 3,
            date: "2026.07.21",
            name: "소니 ZV-1F 카메라",
            category: "digital",
            categoryName: "전자기기",
            purpose: "hobby",
            purposeName: "취미/여가",
            price: 620000,
            status: "not_purchased",
            statusName: "구매 안 함",
            satisfaction: null,
            image: "📷",
            analysis:
                "비교 결과 현재 상황에서는 구매하지 않는 선택을 했어요."
        },
        {
            id: 4,
            date: "2026.06.28",
            name: "소니 WH-1000XM5",
            category: "digital",
            categoryName: "전자기기",
            purpose: "hobby",
            purposeName: "취미/여가",
            price: 499000,
            status: "not_purchased",
            statusName: "구매 안 함",
            satisfaction: null,
            image: "🎧",
            analysis:
                "기회비용을 확인한 뒤 구매하지 않기로 결정했어요."
        },
        {
            id: 5,
            date: "2026.06.20",
            name: "제주도 여행",
            category: "travel",
            categoryName: "여행",
            purpose: "travel",
            purposeName: "여행",
            price: 350000,
            status: "purchased",
            statusName: "구매함",
            satisfaction: 5,
            image: "✈️",
            analysis:
                "상품 구매 대신 여행을 선택한 소비 기록이에요."
        },
        {
            id: 6,
            date: "2026.06.15",
            name: "온라인 Python 강의",
            category: "culture",
            categoryName: "문화",
            purpose: "study",
            purposeName: "공부/자기계발",
            price: 200000,
            status: "pending",
            statusName: "구매 보류",
            satisfaction: null,
            image: "💻",
            analysis:
                "현재는 구매를 보류하고 추가로 고민하고 있는 상품이에요."
        }
    ];


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


    /* Modal contents */

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
    let visibleCount = 4;


    /* =========================================
       금액 포맷
    ========================================= */

    function formatPrice(price) {
        return `${price.toLocaleString("ko-KR")}원`;
    }


    /* =========================================
       별점
    ========================================= */

    function renderStars(score) {

        if (!score) {
            return `<span class="item-stars empty">-</span>`;
        }

        return `
            <span class="item-stars">
                ${"★".repeat(score)}
                ${"☆".repeat(5 - score)}
            </span>
        `;
    }


    function renderModalStars(score) {

        if (!score) {
            return "-";
        }

        return (
            "★".repeat(score) +
            "☆".repeat(5 - score)
        );
    }


    /* =========================================
       상태 클래스
    ========================================= */

    function getStatusClass(status) {

        if (status === "purchased") {
            return "purchased";
        }

        if (status === "pending") {
            return "pending";
        }

        return "not-purchased";
    }


    /* =========================================
       필터링
    ========================================= */

    function getFilteredData() {

        const selectedCategory =
            categoryFilter.value;

        const selectedPurpose =
            purposeFilter.value;

        const selectedDate =
            dateFilter.value;


        return consumptionData.filter((item) => {

            const statusMatch =
                currentStatus === "all" ||
                item.status === currentStatus;


            const categoryMatch =
                selectedCategory === "all" ||
                item.category === selectedCategory;


            const purposeMatch =
                selectedPurpose === "all" ||
                item.purpose === selectedPurpose;


            let dateMatch = true;

            if (selectedDate) {

                const normalizedDate =
                    item.date.replaceAll(".", "-");

                dateMatch =
                    normalizedDate === selectedDate;
            }


            return (
                statusMatch &&
                categoryMatch &&
                purposeMatch &&
                dateMatch
            );
        });
    }


    /* =========================================
       소비 카드 생성
    ========================================= */

    function createConsumptionCard(item) {

        const statusClass =
            getStatusClass(item.status);


        return `
            <article
                class="consumption-item"
                data-id="${item.id}"
                tabindex="0"
            >

                <div class="product-thumbnail">
                    ${item.image}
                </div>


                <div class="product-main">

                    <div class="product-name">
                        ${item.name}
                    </div>

                    <div class="product-meta">
                        <span>${item.categoryName}</span>
                        <span>${item.purposeName}</span>
                    </div>

                </div>


                <div class="item-info">

                    <div class="item-info-label">
                        기록 날짜
                    </div>

                    <div class="item-info-value">
                        ${item.date}
                    </div>

                </div>


                <div class="item-info">

                    <div class="item-info-label">
                        실제 가격
                    </div>

                    <div class="item-info-value">
                        ${formatPrice(item.price)}
                    </div>

                </div>


                <div class="purchase-status ${statusClass}">
                    ${item.statusName}
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

        const filteredData =
            getFilteredData();


        const visibleData =
            filteredData.slice(0, visibleCount);


        consumptionList.innerHTML =
            visibleData
                .map(createConsumptionCard)
                .join("");


        /* 빈 상태 */

        if (filteredData.length === 0) {

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

        if (
            filteredData.length > visibleCount
        ) {

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
       카드 클릭 이벤트
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

                    const id =
                        Number(card.dataset.id);

                    const item =
                        consumptionData.find(
                            (data) =>
                                data.id === id
                        );

                    if (item) {
                        openModal(item);
                    }
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

                        const id =
                            Number(card.dataset.id);

                        const item =
                            consumptionData.find(
                                (data) =>
                                    data.id === id
                            );

                        if (item) {
                            openModal(item);
                        }
                    }
                }
            );
        });
    }


    /* =========================================
       상세 팝업 열기
    ========================================= */

    function openModal(item) {

        modalProductImage.textContent =
            item.image;

        modalCategory.textContent =
            item.categoryName;

        modalProductName.textContent =
            item.name;

        modalPrice.textContent =
            formatPrice(item.price);

        modalRecordDate.textContent =
            item.date;

        modalRealPrice.textContent =
            formatPrice(item.price);

        modalPurpose.textContent =
            item.purposeName;

        modalStatus.textContent =
            item.statusName;

        modalStatus.className =
            `modal-status ${getStatusClass(item.status)}`;

        modalSatisfactionStars.textContent =
            renderModalStars(item.satisfaction);

        modalAnalysisText.textContent =
            item.analysis;


        modal.classList.remove("hidden");

        modal.setAttribute(
            "aria-hidden",
            "false"
        );

        document.body.classList.add(
            "modal-open"
        );
    }


    /* =========================================
       상세 팝업 닫기
    ========================================= */

    function closeModal() {

        modal.classList.add("hidden");

        modal.setAttribute(
            "aria-hidden",
            "true"
        );

        document.body.classList.remove(
            "modal-open"
        );
    }


    /* =========================================
       팝업 이벤트
    ========================================= */

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
                !modal.classList.contains("hidden")
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

                visibleCount = 4;

                renderList();
            }
        );
    });


    /* =========================================
       상세 필터
    ========================================= */

    categoryFilter.addEventListener(
        "change",
        () => {

            visibleCount = 4;

            renderList();
        }
    );


    purposeFilter.addEventListener(
        "change",
        () => {

            visibleCount = 4;

            renderList();
        }
    );


    dateFilter.addEventListener(
        "change",
        () => {

            visibleCount = 4;

            renderList();
        }
    );


    /* =========================================
       더보기
    ========================================= */

    loadMoreButton.addEventListener(
        "click",
        () => {

            visibleCount += 4;

            renderList();
        }
    );


    /* =========================================
       소비 요약 계산
    ========================================= */

    function updateSummary() {

        const purchasedItems =
            consumptionData.filter(
                (item) =>
                    item.status === "purchased"
            );


        /* 이번 달 소비 */

        const totalSpending =
            purchasedItems.reduce(
                (total, item) =>
                    total + item.price,
                0
            );


        monthlySpending.textContent =
            `${totalSpending.toLocaleString("ko-KR")} 원`;


        /* 카테고리별 소비 횟수 */

        const categoryCount = {};

        consumptionData.forEach((item) => {

            categoryCount[item.categoryName] =
                (categoryCount[item.categoryName] || 0) +
                1;
        });


        let mostCategory = "-";
        let maxCount = 0;

        Object.entries(categoryCount)
            .forEach(([category, count]) => {

                if (count > maxCount) {

                    maxCount = count;
                    mostCategory = category;
                }
            });


        mostSpentCategory.textContent =
            mostCategory;


        /* 평균 만족도 */

        const satisfactionItems =
            consumptionData.filter(
                (item) =>
                    item.satisfaction !== null
            );


        if (satisfactionItems.length > 0) {

            const totalSatisfaction =
                satisfactionItems.reduce(
                    (total, item) =>
                        total + item.satisfaction,
                    0
                );


            const average =
                totalSatisfaction /
                satisfactionItems.length;


            averageSatisfaction.textContent =
                `${average.toFixed(1)} 점`;

        } else {

            averageSatisfaction.textContent =
                "-";
        }


        /* 구매 확정률 */

        const completedItems =
            consumptionData.filter(
                (item) =>
                    item.status === "purchased" ||
                    item.status === "not_purchased"
            );


        if (completedItems.length > 0) {

            const rate =
                (
                    purchasedItems.length /
                    completedItems.length
                ) * 100;


            purchaseRate.textContent =
                `${Math.round(rate)} %`;

        } else {

            purchaseRate.textContent =
                "-";
        }
    }


    /* =========================================
       초기 실행
    ========================================= */

    updateSummary();
    renderList();

});