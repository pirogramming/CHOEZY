// 가격 입력 보조 (docs/API.md §5.1)
// 입력 중에는 천 단위 구분 기호와 한글 금액을 보여주고,
// 제출할 때는 서버가 받는 정수 문자열로 되돌립니다.

const priceInput = document.querySelector("[data-price-input]");
const priceReadback = document.querySelector("[data-price-readback]");

const PRICE_UNITS = [
    { value: 100000000, label: "억" },
    { value: 10000, label: "만" },
];


function toDigits(value) {

    return value.replace(/[^0-9]/g, "");

}


function withSeparators(digits) {

    return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");

}


function toKoreanAmount(digits) {

    let rest = Number(digits);

    if (!rest) {
        return "";
    }

    const parts = [];

    for (const unit of PRICE_UNITS) {

        const amount = Math.floor(rest / unit.value);

        if (amount > 0) {
            parts.push(withSeparators(String(amount)) + unit.label);
            rest -= amount * unit.value;
        }

    }

    if (rest > 0) {
        parts.push(withSeparators(String(rest)));
    }

    return parts.join(" ") + "원";

}


if (priceInput) {

    const render = () => {

        const digits = toDigits(priceInput.value);

        priceInput.value = withSeparators(digits);

        if (priceReadback) {
            priceReadback.textContent = toKoreanAmount(digits);
        }

    };

    render();

    priceInput.addEventListener("input", render);

    priceInput.form.addEventListener("submit", () => {
        priceInput.value = toDigits(priceInput.value);
    });

}
