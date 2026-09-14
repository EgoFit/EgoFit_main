document.addEventListener("DOMContentLoaded", function () {
    document.addEventListener("submit", handleCommentSubmit);
});

function handleCommentSubmit(event) {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) {
        return;
    }

    if (form.id !== "comment-form" && !form.id.startsWith("reply-form-")) {
        return;
    }

    event.preventDefault();

    const textarea = form.querySelector("textarea");
    const textValue = textarea ? textarea.value.trim() : "";
    const container = document.getElementById("tabThree");
    const endpoint = container ? container.dataset.commentEndpoint : "";

    if (!endpoint) {
        showFloatingMessage("امکان ثبت دیدگاه در حال حاضر وجود ندارد.", "#dc2626");
        return;
    }

    if (textValue.length < 5) {
        showFloatingMessage(
            form.id === "comment-form"
                ? "لطفا دیدگاه خود را حداقل در ۵ کاراکتر وارد کنید."
                : "لطفا پاسخ خود را حداقل در ۵ کاراکتر وارد کنید.",
            "#dc2626"
        );
        return;
    }

    submitCommentForm(form, endpoint, container);
}

async function submitCommentForm(form, endpoint, container) {
    const submitButton = form.querySelector('button[type="submit"]');
    const originalButtonText = submitButton ? submitButton.textContent : "";

    try {
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.classList.add("is-loading");
        }

        const response = await fetch(endpoint, {
            method: "POST",
            body: new FormData(form),
            credentials: "same-origin",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
        });

        if (!response.ok) {
            throw new Error("Request failed");
        }

        const html = await response.text();
        const parser = new DOMParser();
        const documentFragment = parser.parseFromString(html, "text/html");
        const nextSection = documentFragment.querySelector("#tabThree");

        if (nextSection && container) {
            container.replaceWith(nextSection);
        }

        showFloatingMessage(
            form.id === "comment-form"
                ? "دیدگاه شما ثبت شد و بعد از بررسی نمایش داده می‌شود."
                : "پاسخ شما ثبت شد و بعد از بررسی نمایش داده می‌شود.",
            "#2563eb"
        );
    } catch (error) {
        showFloatingMessage(
            form.id === "comment-form"
                ? "خطا در ثبت دیدگاه. دوباره تلاش کنید."
                : "خطا در ثبت پاسخ. دوباره تلاش کنید.",
            "#dc2626"
        );
    } finally {
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.classList.remove("is-loading");
            submitButton.textContent = originalButtonText;
        }
    }
}

function showFloatingMessage(message, backgroundColor) {
    const notification = document.createElement("div");
    notification.className = "success-message bg-primary text-primary-foreground rounded-full";
    notification.textContent = message;
    notification.style.position = "fixed";
    notification.style.top = "-100px";
    notification.style.right = "50%";
    notification.style.transform = "translateX(50%)";
    notification.style.zIndex = "9999";
    notification.style.padding = "10px 24px";
    notification.style.borderRadius = "999px";
    notification.style.boxShadow = "0 18px 40px rgba(15, 23, 42, 0.18)";
    notification.style.background = backgroundColor;
    notification.style.color = "#ffffff";
    notification.style.fontWeight = "800";
    notification.style.fontSize = "14px";
    notification.style.textAlign = "center";
    notification.style.transition = "top 320ms ease, opacity 220ms ease";

    document.body.appendChild(notification);

    window.setTimeout(() => {
        notification.style.top = "20px";
    }, 25);

    window.setTimeout(() => {
        notification.style.opacity = "0";
        window.setTimeout(() => {
            notification.remove();
        }, 220);
    }, 2900);
}
