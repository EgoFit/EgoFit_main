(function () {
    "use strict";

    var mediaModal = document.querySelector("[data-media-modal]");
    if (!mediaModal || mediaModal.dataset.initialized === "true") {
        return;
    }

    var modalImage = mediaModal.querySelector("[data-media-modal-image]");
    var modalVideo = mediaModal.querySelector("[data-media-modal-video]");
    var modalTitle = mediaModal.querySelector(".admin-media-modal__title");
    var closeButton = mediaModal.querySelector(".admin-media-modal__close");
    if (!modalImage || !modalVideo || !modalTitle || !closeButton) {
        return;
    }

    // The admin content shell may create a stacking context or clip fixed
    // children. Keep the lightbox at the document root on every viewport.
    if (mediaModal.parentElement !== document.body) {
        document.body.appendChild(mediaModal);
    }
    mediaModal.dataset.initialized = "true";

    var returnFocusTo = null;

    function resolveMediaUrl(rawUrl) {
        try {
            var url = new URL(rawUrl, document.baseURI);
            return url.protocol === "http:" || url.protocol === "https:" ? url.href : "";
        } catch (error) {
            return "";
        }
    }

    function closeMediaModal() {
        if (mediaModal.hidden) {
            return;
        }

        mediaModal.hidden = true;
        mediaModal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("admin-media-modal-open");
        modalImage.removeAttribute("src");
        modalVideo.pause();
        modalVideo.removeAttribute("src");
        modalVideo.load();

        if (returnFocusTo && returnFocusTo.isConnected) {
            returnFocusTo.focus({ preventScroll: true });
        }
        returnFocusTo = null;
    }

    function openMediaModal(trigger) {
        var kind = trigger.dataset.mediaKind;
        var url = resolveMediaUrl(trigger.dataset.mediaUrl || "");
        if ((kind !== "image" && kind !== "video") || !url) {
            return;
        }

        returnFocusTo = trigger;
        modalTitle.textContent = trigger.dataset.mediaTitle || "";
        modalImage.hidden = kind !== "image";
        modalVideo.hidden = kind !== "video";

        if (kind === "image") {
            modalImage.src = url;
            modalImage.alt = trigger.dataset.mediaTitle || "";
        } else {
            modalVideo.src = url;
        }

        mediaModal.hidden = false;
        mediaModal.setAttribute("aria-hidden", "false");
        document.body.classList.add("admin-media-modal-open");
        closeButton.focus({ preventScroll: true });
    }

    document.addEventListener("click", function (event) {
        var target = event.target;
        if (!target || typeof target.closest !== "function") {
            return;
        }

        var trigger = target.closest("[data-media-open]");
        if (trigger) {
            event.preventDefault();
            openMediaModal(trigger);
            return;
        }

        if (!mediaModal.hidden && target.closest("[data-media-close]")) {
            closeMediaModal();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && !mediaModal.hidden) {
            closeMediaModal();
        }
    });
})();
