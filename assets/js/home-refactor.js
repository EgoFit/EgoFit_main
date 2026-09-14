document.addEventListener("DOMContentLoaded", function () {
    if (!document.body.classList.contains("public-site")) {
        return;
    }

    initSearchSubmitButtons();
    initToastNotifications();
    initFlashMessages();
    initRevealAnimations();
    initScrollToTop();
    initHeaderDropdowns();
    initHeaderMegaMenus();
    initOffcanvasAccessibility();
    initFormSubmitLoading();
    initWorkoutLibraryModals();
});

function initSearchSubmitButtons() {
    document.querySelectorAll("[data-search-submit]").forEach(function (trigger) {
        trigger.addEventListener("click", function () {
            const form = trigger.closest("form");
            if (form) {
                form.requestSubmit ? form.requestSubmit() : form.submit();
            }
        });
    });
}

function initToastNotifications() {
    document.querySelectorAll(".notification").forEach(function (notification) {
        window.setTimeout(function () {
            notification.classList.add("is-visible");
        }, 100);

        window.setTimeout(function () {
            notification.classList.add("is-dismissed");
            window.setTimeout(function () {
                notification.remove();
            }, 400);
        }, 5200);
    });
}

function initFlashMessages() {
    document.querySelectorAll("[data-auto-dismiss-messages]").forEach(function (container) {
        const messages = container.querySelectorAll(".message-box, .flash-message");

        messages.forEach(function (message, index) {
            window.setTimeout(function () {
                message.classList.add("is-visible");
            }, index * 120);

            const dismissButton = message.querySelector(".dismiss-button");
            if (dismissButton) {
                dismissButton.addEventListener("click", function () {
                    dismissMessage(message);
                });
            }
        });
    });
}

function dismissMessage(message) {
    message.classList.add("is-dismissed");
    window.setTimeout(function () {
        message.remove();
    }, 320);
}

function revealNodesNearViewport(nodes) {
    const viewportBottom = window.innerHeight + Math.round(window.innerHeight * 0.35);

    nodes.forEach(function (node) {
        const rect = node.getBoundingClientRect();
        if (rect.top < viewportBottom && rect.bottom > -96) {
            node.classList.add("is-visible");
        }
    });
}

function initRevealAnimations() {
    const siteContent = document.querySelector(".site-content");
    if (!siteContent) {
        return;
    }

    const revealNodes = siteContent.querySelectorAll("[data-reveal]");
    if (!revealNodes.length) {
        return;
    }

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        revealNodes.forEach(function (node) {
            node.classList.add("is-visible");
        });
        return;
    }

    revealNodesNearViewport(revealNodes);
    document.documentElement.classList.add("reveal-enabled");

    if (!("IntersectionObserver" in window)) {
        revealNodes.forEach(function (node) {
            node.classList.add("is-visible");
        });
        return;
    }

    const observer = new IntersectionObserver(
        function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-visible");
                    observer.unobserve(entry.target);
                }
            });
        },
        {
            threshold: 0.08,
            rootMargin: "0px 0px 12% 0px",
        }
    );

    revealNodes.forEach(function (node) {
        if (!node.classList.contains("is-visible")) {
            observer.observe(node);
        }
    });

    window.setTimeout(function () {
        revealNodesNearViewport(revealNodes);
    }, 120);
}

function initScrollToTop() {
    const button = document.getElementById("scrollToTopBtn");
    if (!button) {
        return;
    }

    const toggleVisibility = function () {
        const shouldShow = window.scrollY > 360;
        button.classList.toggle("is-visible", shouldShow);
        button.hidden = !shouldShow;
    };

    toggleVisibility();
    window.addEventListener("scroll", toggleVisibility, { passive: true });

    button.addEventListener("click", function () {
        window.scrollTo({
            top: 0,
            behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
        });
    });
}

function initHeaderDropdowns() {
    document.querySelectorAll(".modern-user").forEach(function (dropdownRoot) {
        const trigger = dropdownRoot.querySelector(".modern-user-btn");
        const menu = dropdownRoot.querySelector(".modern-user__menu");
        if (!trigger || !menu) {
            return;
        }

        trigger.setAttribute("aria-haspopup", "menu");
        trigger.setAttribute("aria-expanded", "false");

        const menuItems = Array.from(menu.querySelectorAll("a"));
        menuItems.forEach(function (item, index) {
            item.setAttribute("role", "menuitem");
            item.setAttribute("tabindex", index === 0 ? "0" : "-1");
        });

        dropdownRoot.addEventListener("keydown", function (event) {
            const isOpen = trigger.getAttribute("aria-expanded") === "true";
            if (!isOpen) {
                return;
            }

            const currentIndex = menuItems.indexOf(document.activeElement);
            let nextIndex = currentIndex;

            if (event.key === "ArrowDown") {
                event.preventDefault();
                nextIndex = currentIndex < menuItems.length - 1 ? currentIndex + 1 : 0;
            } else if (event.key === "ArrowUp") {
                event.preventDefault();
                nextIndex = currentIndex > 0 ? currentIndex - 1 : menuItems.length - 1;
            } else if (event.key === "Home") {
                event.preventDefault();
                nextIndex = 0;
            } else if (event.key === "End") {
                event.preventDefault();
                nextIndex = menuItems.length - 1;
            } else if (event.key === "Escape") {
                trigger.setAttribute("aria-expanded", "false");
                trigger.focus();
                return;
            } else {
                return;
            }

            menuItems.forEach(function (item, index) {
                item.setAttribute("tabindex", index === nextIndex ? "0" : "-1");
            });
            menuItems[nextIndex].focus();
        });
    });

    const observer = new MutationObserver(function () {
        document.querySelectorAll(".modern-user-btn").forEach(function (trigger) {
            const menu = trigger.parentElement && trigger.parentElement.querySelector(".modern-user__menu");
            const expanded = menu && window.getComputedStyle(menu).display !== "none" && !menu.hasAttribute("hidden");
            trigger.setAttribute("aria-expanded", expanded ? "true" : "false");
        });
    });

    document.querySelectorAll(".modern-user").forEach(function (dropdownRoot) {
        observer.observe(dropdownRoot, {
            attributes: true,
            subtree: true,
            attributeFilter: ["style", "class"],
        });
    });
}

function initHeaderMegaMenus() {
    const stack = document.querySelector(".modern-header__stack");
    if (!stack) {
        return;
    }

    const mega = stack.querySelector(".modern-header__mega");
    if (!mega) {
        return;
    }

    const configs = [
        {
            triggerSelector: ".modern-menu-item--browse",
            dropdownSelector: ".modern-dropdown--browse",
            openClass: "is-mega-open--browse",
        },
    ];

    let closeTimer = null;

    function setExpanded(trigger, expanded) {
        const link = trigger && trigger.querySelector(".modern-menu-link");
        if (link) {
            link.setAttribute("aria-expanded", expanded ? "true" : "false");
        }
    }

    function closeMegaMenus() {
        configs.forEach(function (config) {
            stack.classList.remove(config.openClass);
            const dropdown = mega.querySelector(config.dropdownSelector);
            const trigger = stack.querySelector(config.triggerSelector);
            if (dropdown) {
                dropdown.classList.remove("is-open");
            }
            setExpanded(trigger, false);
        });
    }

    function openMegaMenu(config) {
        clearTimeout(closeTimer);
        configs.forEach(function (item) {
            stack.classList.remove(item.openClass);
            const dropdown = mega.querySelector(item.dropdownSelector);
            if (dropdown) {
                dropdown.classList.remove("is-open");
            }
            setExpanded(stack.querySelector(item.triggerSelector), false);
        });

        const dropdown = mega.querySelector(config.dropdownSelector);
        const trigger = stack.querySelector(config.triggerSelector);
        if (!dropdown || !trigger) {
            return;
        }

        stack.classList.add(config.openClass);
        dropdown.classList.add("is-open");
        setExpanded(trigger, true);
    }

    function scheduleClose() {
        clearTimeout(closeTimer);
        closeTimer = window.setTimeout(closeMegaMenus, 180);
    }

    configs.forEach(function (config) {
        const trigger = stack.querySelector(config.triggerSelector);
        const dropdown = mega.querySelector(config.dropdownSelector);
        if (!trigger || !dropdown) {
            return;
        }

        setExpanded(trigger, false);

        trigger.addEventListener("mouseenter", function () {
            openMegaMenu(config);
        });

        trigger.addEventListener("focusin", function () {
            openMegaMenu(config);
        });

        dropdown.addEventListener("mouseenter", function () {
            clearTimeout(closeTimer);
        });

        dropdown.addEventListener("mouseleave", scheduleClose);
    });

    mega.addEventListener("mouseenter", function () {
        clearTimeout(closeTimer);
    });

    mega.addEventListener("mouseleave", scheduleClose);

    stack.addEventListener("mouseleave", function (event) {
        if (!stack.contains(event.relatedTarget)) {
            scheduleClose();
        }
    });

    stack.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeMegaMenus();
        }
    });
}

function initOffcanvasAccessibility() {
    const header = document.querySelector(".modern-header");
    if (!header) {
        return;
    }

    const panel = header.querySelector(".modern-offcanvas__panel");
    const openButton = header.querySelector('[aria-label="باز کردن منو"], [aria-label="Open menu"]');
    if (!panel || !openButton) {
        return;
    }

    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    panel.setAttribute("aria-label", "منوی اصلی");

    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") {
            return;
        }

        const isOpen = !panel.className.includes("translate-x-full") && panel.className.includes("translate-x-0");
        if (!isOpen) {
            return;
        }

        const closeButton = panel.querySelector('[aria-label="بستن منو"], [aria-label="Close menu"]');
        if (closeButton) {
            closeButton.click();
        }
    });
}

function initFormSubmitLoading() {
    document.querySelectorAll("form[data-submit-loading]").forEach(function (form) {
        form.addEventListener("submit", function () {
            const submitButton = form.querySelector('[type="submit"]');
            if (!submitButton || submitButton.classList.contains("is-loading")) {
                return;
            }

            submitButton.classList.add("is-loading");
            submitButton.setAttribute("aria-busy", "true");
        });
    });

    if (typeof resetSubmitLoadingStates === "function") {
        window.addEventListener("pageshow", resetSubmitLoadingStates);
    }
}

function initWorkoutLibraryModals() {
    const triggers = document.querySelectorAll("[data-library-modal-trigger]");
    if (!triggers.length) {
        return;
    }

    const modal = document.createElement("div");
    modal.className = "workout-library-modal";
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    modal.innerHTML = `
        <div class="workout-library-modal__backdrop" data-library-modal-close></div>
        <section class="workout-library-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="workout-library-modal-title">
            <header class="workout-library-modal__header">
                <button class="workout-library-modal__close" type="button" aria-label="بستن" data-library-modal-close>&times;</button>
            </header>
            <div class="workout-library-modal__content" id="workout-library-modal-content"></div>
        </section>
    `;
    document.body.appendChild(modal);

    const content = modal.querySelector(".workout-library-modal__content");
    const dialog = modal.querySelector(".workout-library-modal__dialog");
    const closeButton = modal.querySelector(".workout-library-modal__close");
    let lastFocusedElement = null;

    function getFocusableElements() {
        return Array.from(dialog.querySelectorAll("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])"))
            .filter(function (element) {
                return !element.hasAttribute("disabled") && !element.getAttribute("aria-hidden");
            });
    }

    function closeModal() {
        if (modal.hidden) {
            return;
        }

        modal.hidden = true;
        modal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("workout-library-modal-open");
        content.replaceChildren();

        if (lastFocusedElement && document.contains(lastFocusedElement)) {
            lastFocusedElement.focus();
        }
        lastFocusedElement = null;
    }

    function openModal(trigger) {
        const template = trigger.querySelector(".workout-library-modal-template");
        if (!template) {
            return;
        }

        lastFocusedElement = document.activeElement;
        content.replaceChildren(template.content.cloneNode(true));

        const heading = content.querySelector("h2");
        if (heading) {
            heading.id = "workout-library-modal-title";
        }

        modal.hidden = false;
        modal.setAttribute("aria-hidden", "false");
        document.body.classList.add("workout-library-modal-open");
        closeButton.focus();
    }

    document.addEventListener("click", function (event) {
        const trigger = event.target.closest("[data-library-modal-trigger]");
        if (trigger) {
            event.preventDefault();
            openModal(trigger);
            return;
        }

        if (event.target.closest("[data-library-modal-close]")) {
            closeModal();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (modal.hidden) {
            const trigger = event.target.closest && event.target.closest("[data-library-modal-trigger]");
            if (!trigger || (event.key !== "Enter" && event.key !== " ")) {
                return;
            }

            event.preventDefault();
            openModal(trigger);
            return;
        }

        if (event.key === "Escape") {
            event.preventDefault();
            closeModal();
            return;
        }

        if (event.key !== "Tab") {
            return;
        }

        const focusableElements = getFocusableElements();
        if (!focusableElements.length) {
            event.preventDefault();
            closeButton.focus();
            return;
        }

        const first = focusableElements[0];
        const last = focusableElements[focusableElements.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    });
}
