document.addEventListener("DOMContentLoaded", function () {
    if (!document.body.classList.contains("auth-page")) {
        return;
    }

    initAuthFormLoadingStates();
    initOtpTimers();
    resetAllAuthLoadingStates();
});

function resetAuthSubmitButton(submitButton) {
    if (!submitButton) {
        return;
    }

    submitButton.classList.remove("is-loading");
    submitButton.removeAttribute("aria-busy");

    if (submitButton.dataset.originalLabel) {
        submitButton.textContent = submitButton.dataset.originalLabel;
    }
}

function resetAllAuthLoadingStates() {
    document.querySelectorAll(".auth-mobile-primary.is-loading, .auth-mobile-form form [type='submit'].is-loading").forEach(resetAuthSubmitButton);
}

function initAuthFormLoadingStates() {
    document.querySelectorAll(".auth-mobile-form form, .auth-mobile-screen form").forEach(function (form) {
        const submitButton = form.querySelector('[type="submit"]');

        form.addEventListener("submit", function () {
            if (!submitButton || submitButton.classList.contains("is-loading")) {
                return;
            }

            submitButton.classList.add("is-loading");
            submitButton.setAttribute("aria-busy", "true");

            if (!submitButton.dataset.originalLabel) {
                submitButton.dataset.originalLabel = submitButton.textContent.trim();
            }

            submitButton.textContent = "لطفاً صبر کنید…";

            window.setTimeout(function () {
                resetAuthSubmitButton(submitButton);
            }, 45000);
        });

        form.addEventListener("invalid", function () {
            resetAuthSubmitButton(submitButton);
        }, true);
    });

    window.addEventListener("pageshow", function () {
        resetAllAuthLoadingStates();
    });
}

function formatCountdown(totalSeconds) {
    const safeSeconds = Math.max(0, Number(totalSeconds) || 0);
    const minutes = Math.floor(safeSeconds / 60);
    const seconds = safeSeconds % 60;
    return String(minutes).padStart(2, "0") + ":" + String(seconds).padStart(2, "0");
}

function setResendLinkState(link, enabled) {
    if (!link) {
        return;
    }

    if (enabled) {
        link.classList.remove("is-disabled");
        link.removeAttribute("aria-disabled");
        link.removeAttribute("tabindex");
        return;
    }

    link.classList.add("is-disabled");
    link.setAttribute("aria-disabled", "true");
    link.setAttribute("tabindex", "-1");
}

function initOtpTimers() {
    const root = document.querySelector("[data-otp-timers]");
    if (!root) {
        return;
    }

    let expiresIn = Number(root.dataset.expiresIn || 0);
    let cooldownRemaining = Number(root.dataset.cooldownRemaining || 0);
    const expiryValue = root.querySelector("[data-otp-expiry-value]");
    const resendRow = root.querySelector("[data-otp-resend]");
    const resendValue = root.querySelector("[data-otp-resend-value]");
    const resendLink = document.querySelector("[data-otp-resend-link]");

    if (resendLink) {
        resendLink.addEventListener("click", function (event) {
            if (resendLink.classList.contains("is-disabled")) {
                event.preventDefault();
            }
        });
    }

    let timerId = null;

    function render() {
        if (expiryValue) {
            expiryValue.textContent = formatCountdown(expiresIn);
        }

        if (resendRow && resendValue) {
            if (cooldownRemaining > 0) {
                resendRow.hidden = false;
                resendValue.textContent = formatCountdown(cooldownRemaining);
                setResendLinkState(resendLink, false);
            } else {
                resendRow.hidden = true;
                setResendLinkState(resendLink, true);
            }
        }

        if (expiresIn <= 0 && cooldownRemaining <= 0 && timerId !== null) {
            window.clearInterval(timerId);
        }
    }

    render();
    timerId = window.setInterval(function () {
        if (expiresIn > 0) {
            expiresIn -= 1;
        }
        if (cooldownRemaining > 0) {
            cooldownRemaining -= 1;
        }
        render();
    }, 1000);
}
