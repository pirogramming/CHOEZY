document.addEventListener("DOMContentLoaded", () => {
    const usernameInput = document.getElementById("username");
    const checkButton = document.getElementById("usernameCheckButton");
    const message = document.getElementById("usernameCheckMessage");

    if (!usernameInput || !checkButton || !message) {
        return;
    }

    let checkedUsername = "";

    // 아이디 중복 확인
    checkButton.addEventListener("click", async () => {
        const username = usernameInput.value.trim();

        if (!username) {
            message.textContent = "아이디를 입력해주세요.";
            message.className = "username-check-message error";
            return;
        }

        try {
            const response = await fetch(
                `/api/accounts/check-username/?username=${encodeURIComponent(username)}`
            );

            const data = await response.json();

            if (!response.ok) {
                message.textContent = "중복 확인에 실패했습니다.";
                message.className = "username-check-message error";
                return;
            }

            if (data.available) {
                message.textContent = "사용 가능한 아이디입니다.";
                message.className = "username-check-message success";
                checkedUsername = username;
            } else {
                message.textContent = "이미 사용 중인 아이디입니다.";
                message.className = "username-check-message error";
                checkedUsername = "";
            }

        } catch (error) {
            console.error("아이디 중복 확인 오류:", error);

            message.textContent = "중복 확인 중 오류가 발생했습니다.";
            message.className = "username-check-message error";
            checkedUsername = "";
        }
    });

    // 아이디를 수정하면 중복 확인 결과 초기화
    usernameInput.addEventListener("input", () => {
        if (usernameInput.value.trim() !== checkedUsername) {
            checkedUsername = "";
            message.textContent = "";
            message.className = "username-check-message";
        }
    });
});