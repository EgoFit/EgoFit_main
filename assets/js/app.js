function resetSubmitLoadingStates(root) {
    var scope = root && typeof root.querySelectorAll === "function" ? root : document;
    scope.querySelectorAll(".is-loading").forEach(function (button) {
        button.classList.remove("is-loading");
        button.removeAttribute("aria-busy");
        if (button.dataset.originalLabel) {
            button.textContent = button.dataset.originalLabel;
        }
    });
}

function initSwiper(selector, options) {
    if (!document.querySelector(selector)) {
        return null;
    }
    return new Swiper(selector, options);
}

initSwiper(".col3-swiper-slider", {
  spaceBetween: 20,
  navigation: {
    nextEl: ".swiper-button-next",
    prevEl: ".swiper-button-prev",
  },
  breakpoints: {
    992: {
      slidesPerView: 3,
    },
    576: {
      slidesPerView: 2,
    },
    0: {
      slidesPerView: 1,
    },
  },
});

initSwiper(".col4-swiper-slider", {
  spaceBetween: 20,
  navigation: {
    nextEl: ".swiper-button-next",
    prevEl: ".swiper-button-prev",
  },
  breakpoints: {
    992: {
      slidesPerView: 4,
    },
    768: {
      slidesPerView: 3,
    },
    480: {
      slidesPerView: 2,
    },
    0: {
      slidesPerView: 1,
    },
  },
});

initSwiper(".auto-swiper-slider", {
  slidesPerView: "auto",
  spaceBetween: 30,
  navigation: {
    nextEl: ".swiper-button-next",
    prevEl: ".swiper-button-prev",
  },
});

initSwiper(".card-swiper-slider", {
  effect: "cards",
  grabCursor: true,
  autoplay: {
    delay: 3000,
  },
  cardsEffect: {
    rotate: 50,
    slideShadows: false,
  },
  navigation: {
    nextEl: ".swiper-button-next",
    prevEl: ".swiper-button-prev",
  },
});

const players = document.querySelectorAll(".js-player");

if (players.length) {
  Array.from(players).map(
    (p) =>
      new Plyr(p, {
        // options
      })
  );
}

const scrollToTopBtn = document.getElementById("scrollToTopBtn");

if (scrollToTopBtn) {
  scrollToTopBtn.addEventListener("click", function () {
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  });
}

document.addEventListener("DOMContentLoaded", function () {
    resetSubmitLoadingStates();
});

window.addEventListener("pageshow", function () {
    resetSubmitLoadingStates();
});
