/* ============================================================
   Smart Inventory – accounts/validation.js
   Handles: login form, forgot-password step 1/2/3
   ============================================================ */

/* ── Helpers ────────────────────────────────────────────── */
function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function showError(id, msg) {
    const el = document.getElementById(id);
    if (el) el.textContent = msg;
}

function clearErrors(...ids) {
    ids.forEach(id => showError(id, ''));
}

/* ── Login form ─────────────────────────────────────────── */
const loginForm = document.getElementById('loginForm');
if (loginForm) {
    loginForm.addEventListener('submit', function (e) {
        let valid = true;
        const email    = document.getElementById('email').value.trim();
        const password = document.getElementById('password').value.trim();
        const role     = document.getElementById('role').value;

        clearErrors('emailError', 'passwordError', 'roleError');

        if (!email)                  { showError('emailError', 'Email is required'); valid = false; }
        else if (!isValidEmail(email)) { showError('emailError', 'Enter a valid email address'); valid = false; }

        if (!password)               { showError('passwordError', 'Password is required'); valid = false; }
        else if (password.length < 6){ showError('passwordError', 'Password must be at least 6 characters'); valid = false; }

        if (!role)                   { showError('roleError', 'Please select a role'); valid = false; }

        if (!valid) e.preventDefault();
    });
}

/* ── Forgot password – Step 1 (email entry) ──────────────── */
const forgotForm = document.getElementById('forgotForm');
if (forgotForm) {
    forgotForm.addEventListener('submit', function (e) {
        let valid = true;
        const email = document.getElementById('fpEmail').value.trim();
        clearErrors('fpEmailError');

        if (!email)                   { showError('fpEmailError', 'Email is required'); valid = false; }
        else if (!isValidEmail(email)) { showError('fpEmailError', 'Enter a valid email address'); valid = false; }

        if (!valid) e.preventDefault();
    });
}

/* ── Forgot password – Step 2 (OTP entry) ───────────────── */
const otpForm = document.getElementById('otpForm');
if (otpForm) {
    otpForm.addEventListener('submit', function (e) {
        let valid = true;
        const otp = document.getElementById('otp').value.trim();
        clearErrors('otpError');

        if (!otp)             { showError('otpError', 'OTP is required'); valid = false; }
        else if (otp.length !== 6 || !/^\d+$/.test(otp)) {
            showError('otpError', 'OTP must be 6 digits'); valid = false;
        }

        if (!valid) e.preventDefault();
    });
}

/* ── Forgot password – Step 3 (new password) ────────────── */
const resetForm = document.getElementById('resetForm');
if (resetForm) {
    resetForm.addEventListener('submit', function (e) {
        let valid = true;
        const newPw  = document.getElementById('newPassword').value.trim();
        const confPw = document.getElementById('confirmPassword').value.trim();
        clearErrors('newPasswordError', 'confirmPasswordError');

        if (!newPw)             { showError('newPasswordError', 'New password is required'); valid = false; }
        else if (newPw.length < 6) { showError('newPasswordError', 'Password must be at least 6 characters'); valid = false; }

        if (!confPw)            { showError('confirmPasswordError', 'Please confirm your password'); valid = false; }
        else if (newPw !== confPw){ showError('confirmPasswordError', 'Passwords do not match'); valid = false; }

        if (!valid) e.preventDefault();
    });
}