document.addEventListener("DOMContentLoaded", () => {


    const bars = document.querySelectorAll(
        ".opportunity-bar"
    );


    const MAX_HEIGHT = 450;



    bars.forEach(bar => {


        const count = Number(
            bar.dataset.count
        );


        if (!count) return;



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


            bar.appendChild(block);


        }


    });



});