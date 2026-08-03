document.addEventListener(
    "DOMContentLoaded",
    function () {


        /*
            비교 분야 최대 3개 선택
        */

        const categoryCheckbox =
            document.querySelectorAll(
                ".category input[type='checkbox']"
            );


        categoryCheckbox.forEach(
            checkbox => {

                checkbox.addEventListener(
                    "change",
                    function () {


                        const checked =
                            document.querySelectorAll(
                                ".category input[type='checkbox']:checked"
                            );


                        if (checked.length > 3) {


                            alert(
                                "비교 분야는 최대 3개까지 선택할 수 있어요."
                            );


                            checkbox.checked = false;


                            checkbox
                                .closest(".choice-item")
                                .classList.remove(
                                    "selected"
                                );


                        }


                    }
                );


            }
        );





        /*
            URL 입력 버튼
        */


        const urlButton =
            document.querySelector(
                ".url-row button"
            );


        if (urlButton) {


            urlButton.addEventListener(
                "click",
                function () {


                    alert(
                        "상품 정보를 확인합니다."
                    );


                }
            );


        }





        /*
            구매 목적 / 비교 분야 선택 효과
        */


        const choiceItems =
            document.querySelectorAll(
                ".choice-item"
            );



        choiceItems.forEach(
            item => {


                const input =
                    item.querySelector("input");


                if (!input) return;




                /*
                    label 클릭 처리
                */

                item.addEventListener(
                    "click",
                    function () {


                        /*
                            radio
                            구매 목적
                        */

                        if (
                            input.type === "radio"
                        ) {


                            const choiceList =
                                item.closest(
                                    ".choice-list"
                                );


                            choiceList
                                .querySelectorAll(
                                    ".choice-item"
                                )
                                .forEach(
                                    choice => {

                                        choice.classList.remove(
                                            "selected"
                                        );

                                        const choiceInput =
                                            choice.querySelector(
                                                "input"
                                            );


                                        if (
                                            choiceInput
                                        ) {

                                            choiceInput.checked =
                                                false;

                                        }

                                    }
                                );


                            input.checked = true;


                            item.classList.add(
                                "selected"
                            );


                        }





                        /*
                            checkbox
                            비교 분야
                        */

                        else if (
                            input.type === "checkbox"
                        ) {


                            input.checked =
                                !input.checked;



                            if (
                                input.checked
                            ) {


                                item.classList.add(
                                    "selected"
                                );


                            } else {


                                item.classList.remove(
                                    "selected"
                                );


                            }


                        }



                    }
                );



            }
        );


    }
);