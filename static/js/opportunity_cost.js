document.addEventListener("DOMContentLoaded", () => {


    const decisionButton = document.getElementById(
        "opportunity-decision-btn"
    );


    if (decisionButton) {


        decisionButton.addEventListener("click", () => {
            createDecisionAndContinue(decisionButton);
        });


    }


    const bars = document.querySelectorAll(
        ".opportunity-bar"
    );


    const MAX_HEIGHT = 450;


    const PALETTE = [
        "#A8E6CF",
        "#BFD8B8",
        "#9FD8D2",
        "#A7D8F0",
        "#B8CFE5",
        "#FFD8A8",
        "#F9E7A1",
        "#F6B8C8",
        "#F7C7A3",
    ];



    bars.forEach((bar, index) => {


        const count = Number(
            bar.dataset.count
        );


        if (!count) return;


        const color = PALETTE[index] || PALETTE[PALETTE.length - 1];



        // 블록 하나의 높이
        const blockHeight = MAX_HEIGHT / count;



        const integerPart = Math.floor(count);


        const decimalPart = count - integerPart;



        /*
            정수 블록 생성
        */

        for(let i = integerPart - 1; i >= 0; i--){


            const block = document.createElement("div");


            block.classList.add(
                "opportunity-block"
            );


            block.style.height =
                `${blockHeight}px`;


            block.style.background = color;


            bar.appendChild(block);


        }



        /*
            소수 블록 생성
            예) 1.4 -> 0.4 블록
        */

        if(decimalPart > 0){


            const block =
                document.createElement("div");


            block.classList.add(
                "opportunity-block"
            );


            block.style.height =
                `${blockHeight * decimalPart}px`;


            block.style.background = color;


            bar.appendChild(block);


        }


    });



});


async function createDecisionAndContinue(button) {


    const considerationId = button.dataset.considerationId;
    const decisionUrl = button.dataset.decisionUrl;
    const originalContent = button.innerHTML;
    const errorElement = document.getElementById(
        "opportunity-decision-error"
    );


    button.disabled = true;
    button.textContent = "AI가 분석하는 중...";


    if (errorElement) {
        errorElement.hidden = true;
    }


    try {


        const response = await fetch(
            `/api/analyses/considerations/${considerationId}/decision/`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                },
                body: JSON.stringify({}),
            }
        );


        if (response.ok) {
            window.location.assign(decisionUrl);
            return;
        }


        const body = await response.json();


        // 이미 생성된 결과라면 중간 화면을 다시 보여주지 않고 곧바로
        // 기존 의사결정 결과로 이동합니다.
        if (response.status === 409 && body.error?.code === "ALREADY_EXISTS") {
            window.location.assign(decisionUrl);
            return;
        }


        throw new Error(
            body.error?.message ?? "AI 의사결정 생성에 실패했습니다."
        );


    } catch (error) {


        console.error(error);


        if (errorElement) {
            errorElement.textContent = error.message
                || "네트워크 오류로 요청하지 못했습니다.";
            errorElement.hidden = false;
        }


        button.disabled = false;
        button.innerHTML = originalContent;


    }


}


function getCsrfToken() {


    const input = document.querySelector("[name=csrfmiddlewaretoken]");
    return input ? input.value : "";


}
