function initAuthPage() {
    if (!document.body.classList.contains("auth-page")) {
        return;
    }

    initAuthFormLoadingStates();
    initOtpTimers();
    initPasswordVisibilityToggles();
    initRegisterOtpFlow();
    initOtpAutofill();
    resetAllAuthLoadingStates();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAuthPage, { once: true });
} else {
    initAuthPage();
}

function initPasswordVisibilityToggles() {
    document.querySelectorAll("[data-password-toggle]").forEach(function (toggle) {
        if (toggle.dataset.passwordToggleInitialized === "true") {
            return;
        }

        const inputId = toggle.dataset.target || toggle.getAttribute("aria-controls");
        const input = (inputId && document.getElementById(inputId)) ||
            (toggle.closest(".auth-password-control") && toggle.closest(".auth-password-control").querySelector("input"));
        const label = toggle.querySelector("[data-password-toggle-label]");

        if (!input) {
            toggle.hidden = true;
            return;
        }

        toggle.dataset.passwordToggleInitialized = "true";
        toggle.addEventListener("click", function () {
            const shouldShow = input.type === "password";
            input.type = shouldShow ? "text" : "password";
            toggle.setAttribute("aria-pressed", String(shouldShow));
            toggle.setAttribute("aria-label", shouldShow ? toggle.dataset.hideLabel : toggle.dataset.showLabel);
            input.focus({ preventScroll: true });

            if (label) {
                label.textContent = shouldShow ? toggle.dataset.hideText : toggle.dataset.showText;
            }
        });
    });
}

function initOtpAutofill() {
    const container = document.querySelector("[data-otp-autofill]");
    const input = container && container.querySelector("#id_code[autocomplete='one-time-code']");
    const form = input && input.closest("form");

    if (!input || !form || !("OTPCredential" in window) || !navigator.credentials || !navigator.credentials.get) {
        return;
    }

    const controller = new AbortController();
    const stopListening = function () {
        controller.abort();
    };

    input.addEventListener("input", stopListening, { once: true });
    form.addEventListener("submit", stopListening, { once: true });

    navigator.credentials.get({
        otp: { transport: ["sms"] },
        signal: controller.signal
    }).then(function (credential) {
        if (!credential || !credential.code || input.value) {
            return;
        }

        input.value = credential.code;
        input.dispatchEvent(new Event("input", { bubbles: true }));
    }).catch(function () {
        // Unsupported SMS formats, denied permission, and canceled requests use manual entry.
    });
}

function supportsWebOtp() {
    return "OTPCredential" in window && navigator.credentials && navigator.credentials.get && window.AbortController;
}

function initRegisterOtpFlow() {
    const form = document.querySelector("[data-otp-request-form]");

    if (!form || !supportsWebOtp()) {
        return;
    }

    form.addEventListener("submit", function (event) {
        event.preventDefault();

        const controller = new AbortController();
        let receivedCode = "";
        navigator.credentials.get({
            otp: { transport: ["sms"] },
            signal: controller.signal
        }).then(function (credential) {
            if (!credential || !credential.code) {
                return;
            }

            receivedCode = credential.code;
            fillVerificationCode(receivedCode);
        }).catch(function () {
            // Unsupported SMS formats, denied permission, and canceled requests use manual entry.
        });

        const submitButton = form.querySelector('[type="submit"]');
        fetch(form.action || window.location.href, {
            method: "POST",
            body: new FormData(form),
            headers: { "X-Requested-With": "XMLHttpRequest" },
            credentials: "same-origin"
        }).then(async function (response) {
            const contentType = response.headers.get("content-type") || "";

            if (contentType.includes("application/json")) {
                const result = await response.json();
                const verificationResponse = await fetch(result.verification_url, {
                    credentials: "same-origin"
                });
                const verificationHtml = await verificationResponse.text();
                resetAuthSubmitButton(submitButton);

                if (!verificationResponse.ok || !replaceAuthScreen(verificationHtml, result.verification_url)) {
                    window.location.assign(result.verification_url);
                    return;
                }

                connectVerificationInputToAbort(controller);
                if (receivedCode) {
                    fillVerificationCode(receivedCode);
                }
                initAuthFormLoadingStates();
                initOtpTimers();
                return;
            }

            const errorHtml = await response.text();
            controller.abort();
            resetAuthSubmitButton(submitButton);
            if (replaceAuthScreen(errorHtml)) {
                initAuthFormLoadingStates();
                initOtpTimers();
                initPasswordVisibilityToggles();
                initRegisterOtpFlow();
            }
        }).catch(function () {
            controller.abort();
            resetAuthSubmitButton(submitButton);
            window.location.reload();
        });

    });
}

function replaceAuthScreen(html, nextUrl) {
    const nextDocument = new DOMParser().parseFromString(html, "text/html");
    const nextScreen = nextDocument.querySelector(".auth-mobile-screen");
    const frame = document.querySelector(".auth-mobile-frame");

    if (!nextScreen || !frame) {
        return false;
    }

    frame.replaceChildren(nextScreen);
    if (nextDocument.title) {
        document.title = nextDocument.title;
    }
    if (nextUrl) {
        window.history.replaceState(null, "", nextUrl);
    }
    return true;
}

function fillVerificationCode(code) {
    const input = document.querySelector("[data-otp-autofill] #id_code[autocomplete='one-time-code']");
    if (!input || input.value) {
        return;
    }

    input.value = code;
    input.dispatchEvent(new Event("input", { bubbles: true }));
}

function connectVerificationInputToAbort(controller) {
    const input = document.querySelector("[data-otp-autofill] #id_code");
    const form = input && input.closest("form");

    if (!input || !form) {
        return;
    }

    input.addEventListener("input", function () {
        controller.abort();
    }, { once: true });
    form.addEventListener("submit", function () {
        controller.abort();
    }, { once: true });
}

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
        if (form.dataset.authLoadingInitialized === "true") {
            return;
        }
        form.dataset.authLoadingInitialized = "true";

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

    if (!window.authFormLoadingPageshowBound) {
        window.authFormLoadingPageshowBound = true;
        window.addEventListener("pageshow", resetAllAuthLoadingStates);
    }
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
