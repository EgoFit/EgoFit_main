/* Analysis dashboard charts (Chart.js, vendored locally). Reads json_script payloads
   emitted by account/profile-analysis.html and renders dark-mode-aware line charts. */
(function () {
    "use strict";

    if (typeof Chart === "undefined") {
        return;
    }

    function readJSON(id) {
        var el = document.getElementById(id);
        if (!el) {
            return null;
        }
        try {
            return JSON.parse(el.textContent);
        } catch (err) {
            return null;
        }
    }

    function isDark() {
        return (
            document.documentElement.classList.contains("dark") ||
            document.body.classList.contains("dark")
        );
    }

    function themeColors() {
        var dark = isDark();
        return {
            grid: dark ? "rgba(148,163,184,0.16)" : "rgba(15,23,42,0.08)",
            ticks: dark ? "#94a3b8" : "#64748b",
            palette: dark
                ? ["#7aa2ff", "#5be3c0", "#fbbf6b", "#f472b6", "#a78bfa"]
                : ["#3454d1", "#0ea5a4", "#f59e0b", "#db2777", "#7c3aed"],
        };
    }

    var trendData = readJSON("analysis-trend-data") || {};
    var measureData = readJSON("analysis-measure-data") || {};
    var metricSeries = readJSON("analysis-metric-series") || {};
    var goalData = readJSON("analysis-goal-data") || {};
    var charts = [];

    function goalPayload(key) {
        if (Array.isArray(goalData)) {
            for (var i = 0; i < goalData.length; i += 1) {
                if (goalData[i] && goalData[i].key === key) {
                    return goalData[i];
                }
            }
            return null;
        }
        return goalData[key] || null;
    }

    function baseOptions(colors) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: { rtl: true, bodyFont: { family: "inherit" } },
            },
            scales: {
                x: {
                    grid: { color: colors.grid, drawBorder: false },
                    ticks: { color: colors.ticks, maxRotation: 0, autoSkip: true, maxTicksLimit: 6 },
                },
                y: {
                    grid: { color: colors.grid, drawBorder: false },
                    ticks: { color: colors.ticks, maxTicksLimit: 5 },
                },
            },
        };
    }

    function buildLineChart(canvas, labels, values, colors) {
        var color = colors.palette[0];
        return new Chart(canvas.getContext("2d"), {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        data: values,
                        borderColor: color,
                        backgroundColor: color + "22",
                        borderWidth: 2.5,
                        tension: 0.35,
                        fill: true,
                        pointRadius: values.length > 18 ? 0 : 3,
                        pointBackgroundColor: color,
                        spanGaps: true,
                    },
                ],
            },
            options: baseOptions(colors),
        });
    }

    function buildMultiChart(canvas, payload, colors) {
        var datasets = (payload.datasets || []).map(function (ds, i) {
            var color = colors.palette[i % colors.palette.length];
            return {
                label: ds.label,
                data: ds.data,
                borderColor: color,
                backgroundColor: color + "1a",
                borderWidth: 2.5,
                tension: 0.35,
                fill: false,
                pointRadius: (payload.labels || []).length > 18 ? 0 : 3,
                pointBackgroundColor: color,
                spanGaps: true,
            };
        });
        var opts = baseOptions(colors);
        opts.plugins.legend = { display: true, labels: { color: colors.ticks, usePointStyle: true } };
        return new Chart(canvas.getContext("2d"), {
            type: "line",
            data: { labels: payload.labels || [], datasets: datasets },
            options: opts,
        });
    }

    function buildGoalChart(canvas, payload, colors) {
        var actualColor = colors.palette[1];
        var datasets = [
            {
                label: payload.label,
                data: payload.values || [],
                borderColor: actualColor,
                backgroundColor: actualColor + "1a",
                borderWidth: 2.5,
                tension: 0.35,
                fill: true,
                pointRadius: (payload.labels || []).length > 18 ? 0 : 3,
                pointBackgroundColor: actualColor,
                spanGaps: true,
            },
        ];
        if (payload.target_values && payload.target_values.length) {
            datasets.push({
                label: "هدف",
                data: payload.target_values,
                borderColor: colors.palette[2],
                borderWidth: 2,
                borderDash: [6, 5],
                pointRadius: 0,
                fill: false,
                spanGaps: true,
            });
        }
        var opts = baseOptions(colors);
        opts.plugins.legend = { display: true, labels: { color: colors.ticks, usePointStyle: true } };
        return new Chart(canvas.getContext("2d"), {
            type: "line",
            data: { labels: payload.labels || [], datasets: datasets },
            options: opts,
        });
    }

    var measureChart = null;
    var metricChart = null;

    function renderAll() {
        var colors = themeColors();
        charts.forEach(function (c) { c.destroy(); });
        charts = [];

        document.querySelectorAll("[data-chart]").forEach(function (canvas) {
            var key = canvas.getAttribute("data-chart");
            var series = trendData[key];
            if (!series || !series.values || !series.values.length) {
                return;
            }
            charts.push(buildLineChart(canvas, series.labels, series.values, colors));
        });

        var measureCanvas = document.querySelector("[data-measure-canvas]");
        var measureSelect = document.querySelector("[data-measure-select]");
        if (measureCanvas && measureSelect) {
            if (measureChart) {
                measureChart.destroy();
                measureChart = null;
            }
            var payload = measureData[measureSelect.value];
            if (payload) {
                measureChart = buildMultiChart(measureCanvas, payload, colors);
                charts.push(measureChart);
            }
        }

        renderMetricChart(colors);

        document.querySelectorAll("[data-goal-chart]").forEach(function (canvas) {
            var key = canvas.getAttribute("data-goal-chart");
            var payload = goalPayload(key);
            if (!payload || !payload.values || !payload.values.length) {
                return;
            }
            charts.push(buildGoalChart(canvas, payload, colors));
        });
    }

    function renderMetricChart(colors) {
        var canvas = document.querySelector("[data-metric-canvas]");
        var select = document.querySelector("[data-metric-select]");
        var empty = document.querySelector("[data-metric-empty]");
        if (!canvas || !select) {
            return;
        }
        if (metricChart) {
            metricChart.destroy();
            metricChart = null;
        }
        var series = metricSeries[select.value];
        var hasData = series && series.values && series.values.length >= 1;
        if (empty) {
            empty.hidden = !!hasData;
        }
        // Hide the canvas wrapper when there isn't enough data to plot.
        if (canvas.parentNode) {
            canvas.parentNode.style.display = hasData ? "" : "none";
        }
        if (!hasData) {
            return;
        }
        metricChart = buildLineChart(canvas, series.labels, series.values, colors);
        charts.push(metricChart);
    }

    document.addEventListener("DOMContentLoaded", function () {
        renderAll();

        var measureSelect = document.querySelector("[data-measure-select]");
        if (measureSelect) {
            measureSelect.addEventListener("change", function () {
                renderAll();
            });
        }

        var metricSelect = document.querySelector("[data-metric-select]");
        if (metricSelect) {
            metricSelect.addEventListener("change", function () {
                renderMetricChart(themeColors());
            });
        }

        // Re-theme charts when dark mode is toggled (class flips on <html>).
        var observer = new MutationObserver(function () {
            renderAll();
        });
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
        observer.observe(document.body, { attributes: true, attributeFilter: ["class"] });
    });
})();
