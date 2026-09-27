(function () {
    "use strict";

    function getThemeColors() {
        var dark = document.documentElement.classList.contains("dark");
        return {
            text: dark ? "#cbd5e1" : "#475569",
            grid: dark ? "rgba(148, 163, 184, 0.16)" : "rgba(148, 163, 184, 0.2)"
        };
    }

    function renderMoodCharts() {
        if (typeof Chart === "undefined") return;
        var payloadNode = document.getElementById("mood-trend-data");
        if (!payloadNode) return;
        var payload = JSON.parse(payloadNode.textContent || "{}");
        var colors = getThemeColors();
        var moodPayload = payload.mood || {};
        var heartRatePayload = payload.heart_rate || {};
        var moodLabels = moodPayload.labels || [];
        var series = moodPayload.series || {};
        var moodDefinitions = [
            ["anxiety", "اضطراب", "#ef4444"],
            ["motivation", "انگیزه", "#2563eb"],
            ["sleep", "خواب", "#8b5cf6"],
            ["training", "تمرین", "#10b981"]
        ];
        document.querySelectorAll("[data-mood-chart]").forEach(function (canvas) {
            if (canvas._moodChart) canvas._moodChart.destroy();
            canvas._moodChart = new Chart(canvas.getContext("2d"), {
                type: "line",
                data: {
                    labels: moodLabels,
                    datasets: moodDefinitions.map(function (definition) {
                        return {
                            label: definition[1],
                            data: series[definition[0]] || [],
                            borderColor: definition[2],
                            backgroundColor: definition[2],
                            borderWidth: 2,
                            pointRadius: 3,
                            pointHoverRadius: 5,
                            tension: 0.3,
                            fill: false
                        };
                    })
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: "index", intersect: false },
                    plugins: {
                        legend: { position: "bottom", labels: { color: colors.text, usePointStyle: true, padding: 16 } },
                        tooltip: { rtl: true }
                    },
                    scales: {
                        y: { min: 0, max: 10, ticks: { stepSize: 1, color: colors.text }, grid: { color: colors.grid } },
                        x: { ticks: { color: colors.text, maxRotation: 45, minRotation: 0 }, grid: { color: colors.grid } }
                    }
                }
            });
        });
        document.querySelectorAll("[data-heart-rate-chart]").forEach(function (canvas) {
            if (canvas._heartRateChart) canvas._heartRateChart.destroy();
            canvas._heartRateChart = new Chart(canvas.getContext("2d"), {
                type: "line",
                data: {
                    labels: heartRatePayload.labels || [],
                    datasets: [{
                        label: "ضربان قلب (BPM)",
                        data: heartRatePayload.data || [],
                        borderColor: "#f59e0b",
                        backgroundColor: "rgba(245, 158, 11, 0.14)",
                        borderWidth: 3,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        tension: 0.3,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: "index", intersect: false },
                    plugins: {
                        legend: { position: "bottom", labels: { color: colors.text, usePointStyle: true, padding: 16 } },
                        tooltip: { rtl: true, callbacks: { label: function (context) { return " " + context.parsed.y + " BPM"; } } }
                    },
                    scales: {
                        y: { suggestedMin: 40, suggestedMax: 180, ticks: { color: colors.text, callback: function (value) { return value + " BPM"; } }, grid: { color: colors.grid } },
                        x: { ticks: { color: colors.text, maxRotation: 45, minRotation: 0 }, grid: { color: colors.grid } }
                    }
                }
            });
        });
    }

    document.addEventListener("DOMContentLoaded", renderMoodCharts);
    document.addEventListener("themechange", renderMoodCharts);
})();
