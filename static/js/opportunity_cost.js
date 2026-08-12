document.addEventListener("DOMContentLoaded", () => {


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