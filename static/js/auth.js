const toggleBtn = document.querySelector("#password-toggle");

if(toggleBtn){

    toggleBtn.addEventListener("click",()=>{

        const password =
            document.querySelector("#password");


        if(password.type === "password"){

            password.type="text";

        }else{

            password.type="password";

        }

    });

}