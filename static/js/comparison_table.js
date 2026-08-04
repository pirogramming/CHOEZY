// =====================================
// CHOEZY Comparison Table JS
// API Connected Version
// =====================================



let comparisonTabs = [];




// =====================================
// 페이지 시작
// =====================================

document.addEventListener(
    "DOMContentLoaded",
    async () => {


        const idElement =
            document.getElementById(
                "consideration-id"
            );


        if (!idElement) {

            console.error(
                "consideration id를 찾을 수 없습니다."
            );

            return;

        }



        const considerationId =
            JSON.parse(
                idElement.textContent
            );



        const data =
            await getComparisonData(
                considerationId
            );



        if (!data) {

            return;

        }



        comparisonTabs =
            data.tabs;



        renderCategoryTabs(
            comparisonTabs
        );



        if (comparisonTabs.length > 0) {

            renderTable(
                comparisonTabs[0]
            );

        }


    }
);







// =====================================
// 비교표 API 호출
// =====================================

async function getComparisonData(
    considerationId
) {


    try {


        const response =
            await fetch(
                `/api/alternatives/considerations/${considerationId}/comparison/`,
                {
                    method: "GET",
                    headers: {
                        "Content-Type": "application/json",
                    },
                }
            );



        if (!response.ok) {


            throw new Error(
                "비교 데이터를 불러오지 못했습니다."
            );


        }



        return await response.json();



    } catch(error) {


        console.error(
            error
        );


        return null;


    }


}








// =====================================
// 카테고리 버튼 생성
// =====================================

function renderCategoryTabs(
    tabs
) {


    const container =
        document.querySelector(
            ".comparison-category-wrapper"
        );



    if (!container) {

        return;

    }



    container.innerHTML = "";



    tabs.forEach(
        (tab, index) => {


            const button =
                document.createElement(
                    "button"
                );



            button.className =
                "comparison-category-btn";



            if (index === 0) {

                button.classList.add(
                    "active"
                );

            }



            button.innerHTML =
                `
                ${tab.category.emoji || ""}
                ${tab.category.name}
                `;



            button.addEventListener(
                "click",
                () => {


                    document
                    .querySelectorAll(
                        ".comparison-category-btn"
                    )
                    .forEach(
                        btn => {

                            btn.classList.remove(
                                "active"
                            );

                        }
                    );



                    button.classList.add(
                        "active"
                    );



                    renderTable(
                        tab
                    );


                }
            );



            container.appendChild(
                button
            );



        }
    );

}








// =====================================
// 비교표 렌더링
// =====================================

function renderTable(
    tab
) {


    const rows =
        tab.rows;



    if (!rows) {

        return;

    }



    rows.forEach(
        (item, index) => {


            const number =
                index + 1;



            const name =
                document.getElementById(
                    `name${number}`
                );



            const price =
                document.getElementById(
                    `price${number}`
                );



            const duration =
                document.getElementById(
                    `duration${number}`
                );



            const effect =
                document.getElementById(
                    `effect${number}`
                );





            if (name) {

                name.textContent =
                    item.name ?? "-";

            }



            if (price) {

                price.textContent =
                    item.price_display ?? "-";

            }



            if (duration) {

                duration.textContent =
                    item.duration_display ?? "-";

            }



            if (effect) {

                effect.textContent =
                    item.expected_effect ?? "-";

            }



        }
    );



    // 대안 개수가 3개보다 적을 때 빈칸 처리

    for (
        let i = rows.length + 1;
        i <= 3;
        i++
    ) {


        const fields = [
            "name",
            "price",
            "duration",
            "effect"
        ];



        fields.forEach(
            field => {


                const element =
                    document.getElementById(
                        `${field}${i}`
                    );



                if (element) {

                    element.textContent =
                        "-";

                }


            }
        );


    }



}