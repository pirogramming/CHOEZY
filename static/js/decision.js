// =====================================
// CHOEZY AI 구매 의사결정
// 생성 버튼 → POST → 성공 시 페이지 새로고침
// =====================================


document.addEventListener(
    "DOMContentLoaded",
    () => {

        const button =
            document.getElementById(
                "decision-create-btn"
            );

        if (!button) {

            return;

        }

        button.addEventListener(
            "click",
            () => createDecision(button)
        );

    }
);


async function createDecision(
    button
) {

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

    // 응답에 5~20초가 걸립니다. 버튼 비활성화는 UX 장치일 뿐이고
    // 중복 생성은 서버가 select_for_update()로 막습니다. (docs/API.md §2.11)
    button.disabled = true;
    button.textContent = "AI가 분석하는 중...";

    hideError();

    try {

        const response =
            await fetch(
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

            window.location.reload();

            return;

        }

        const body =
            await response.json();

        showError(
            body.error?.message
            ?? "AI 의사결정 생성에 실패했습니다."
        );

    } catch(error) {

        console.error(
            error
        );

        showError(
            "네트워크 오류로 요청하지 못했습니다."
        );

    }

    button.disabled = false;
    button.textContent = "AI 의사결정 받기";

}


function getCsrfToken() {

    const input =
        document.querySelector(
            "[name=csrfmiddlewaretoken]"
        );

    return input ? input.value : "";

}


function showError(
    message
) {

    const element =
        document.getElementById(
            "decision-error"
        );

    if (!element) {

        return;

    }

    element.textContent = message;
    element.hidden = false;

}


function hideError() {

    const element =
        document.getElementById(
            "decision-error"
        );

    if (element) {

        element.hidden = true;

    }

}
