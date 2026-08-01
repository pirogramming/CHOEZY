document.addEventListener("DOMContentLoaded",()=>{


const consumption =
document.querySelectorAll(
'input[name="consumption_type"]'
);


consumption.forEach(input=>{

input.addEventListener(
"change",
()=>{

let checked =
document.querySelectorAll(
'input[name="consumption_type"]:checked'
);


if(checked.length>2){

input.checked=false;

alert("최대 2개까지 선택 가능합니다.");

}

});


});




const values =
document.querySelectorAll(
'input[name="value_type"]'
);



values.forEach(input=>{

input.addEventListener(
"change",
()=>{

let checked =
document.querySelectorAll(
'input[name="value_type"]:checked'
);


if(checked.length>3){

input.checked=false;

alert("최대 3개까지 선택 가능합니다.");

}

});


});




});