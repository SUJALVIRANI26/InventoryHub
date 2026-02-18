document.getElementById("loginForm").addEventListener("submit", function(e){

    let isValid = true;

    // Get values
    let email = document.getElementById("email").value.trim();
    let password = document.getElementById("password").value.trim();
    let role = document.getElementById("role").value;

    // Clear previous errors
    document.getElementById("emailError").textContent = "";
    document.getElementById("passwordError").textContent = "";
    document.getElementById("roleError").textContent = "";

    // EMAIL VALIDATION
    if(email === ""){
        document.getElementById("emailError").textContent = "Email is required";
        isValid = false;
    }
    else if(!validateEmail(email)){
        document.getElementById("emailError").textContent = "Enter a valid email address";
        isValid = false;
    }

    // PASSWORD VALIDATION
    if(password === ""){
        document.getElementById("passwordError").textContent = "Password is required";
        isValid = false;
    }
    else if(password.length < 6){
        document.getElementById("passwordError").textContent = "Password must be at least 6 characters";
        isValid = false;
    }

    // ROLE VALIDATION
    if(role === ""){
        document.getElementById("roleError").textContent = "Please select a role";
        isValid = false;
    }

    // Prevent submission if invalid
    if(!isValid){
        e.preventDefault();
    }
});

// EMAIL REGEX HELPER
function validateEmail(email){
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}