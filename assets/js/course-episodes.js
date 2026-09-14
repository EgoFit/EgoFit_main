document.addEventListener("DOMContentLoaded", function () {
    const videoSource = document.getElementById("video-source");
    const videoPlayer = document.getElementById("episode-video");
    const episodeTriggers = Array.from(document.querySelectorAll("[data-episode-trigger]"));

    if (!videoSource || !videoPlayer) {
        return;
    }

    const loadEpisode = (trigger) => {
        const videoUrl = trigger.dataset.videoUrl;
        if (!videoUrl) {
            return;
        }

        videoSource.src = videoUrl;
        videoPlayer.load();
        const playPromise = videoPlayer.play();
        if (playPromise && typeof playPromise.catch === "function") {
            playPromise.catch(() => {
                // Browsers may block autoplay; loading the source is still enough.
            });
        }
    };

    episodeTriggers.forEach((trigger) => {
        trigger.addEventListener("click", function (event) {
            event.preventDefault();
            loadEpisode(trigger);
        });
    });

    if (episodeTriggers.length > 0) {
        loadEpisode(episodeTriggers[0]);
    }
});
