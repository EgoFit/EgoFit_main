(function () {
    function selectTextOnFocus(input) {
        if (!input || input.disabled || input.readOnly) {
            return;
        }
        if (typeof input.select === "function") {
            try {
                input.select();
                return;
            } catch (err) {
                // Some browsers do not support selection APIs on every input type.
            }
        }
        if (typeof input.setSelectionRange === "function" && typeof input.value === "string") {
            try {
                input.setSelectionRange(0, input.value.length);
            } catch (err2) {
                // Ignore unsupported selection ranges.
            }
        }
    }

    function initBloodGroupChips(root) {
        root.querySelectorAll(".blood-group-chip input").forEach(function (input) {
            input.addEventListener("change", function () {
                root.querySelectorAll(".blood-group-chip").forEach(function (chip) {
                    chip.classList.remove("is-active");
                });
                if (input.checked && input.closest(".blood-group-chip")) {
                    input.closest(".blood-group-chip").classList.add("is-active");
                }
            });
        });
    }

    function getDateDisplay(element) {
        if (!element) {
            return "";
        }
        return (element.textContent || element.value || "").trim();
    }

    function setDateDisplay(element, value) {
        if (!element) {
            return;
        }
        if (element.tagName === "INPUT") {
            element.value = value;
        } else {
            element.textContent = value;
        }
    }

    function initAnalysisScreen(root) {
        var metricButtons = root.querySelectorAll("[data-analysis-metric]");
        var metricLabel = root.querySelector("[data-analysis-metric-label]");
        var metricMenu = root.querySelector("[data-analysis-metric-menu]");
        var metricToggle = root.querySelector("[data-analysis-metric-toggle]");
        var startInput = root.querySelector("[data-analysis-start]");
        var endInput = root.querySelector("[data-analysis-end]");
        var calendar = root.querySelector("[data-analysis-calendar]");
        var calendarTitle = root.querySelector("[data-analysis-calendar-title]");
        var calendarGrid = root.querySelector("[data-analysis-calendar-grid]");
        var calendarConfirm = root.querySelector("[data-analysis-calendar-confirm]");
        var calendarPrev = root.querySelector("[data-analysis-calendar-prev]");
        var calendarNext = root.querySelector("[data-analysis-calendar-next]");
        var chartCard = root.querySelector("[data-analysis-chart-card]");
        var emptyState = root.querySelector("[data-analysis-empty]");
        var filterForm = root.querySelector("[data-analysis-filter-form]");
        var metricInput = root.querySelector("[data-analysis-metric-input]");
        var startHidden = root.querySelector("[data-analysis-start-input]");
        var endHidden = root.querySelector("[data-analysis-end-input]");

        if (!metricToggle || !calendarGrid) {
            return;
        }

        var PERSIAN_MONTH_NAMES = [
            "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
            "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
        ];

        function buildMonths(year) {
            return PERSIAN_MONTH_NAMES.map(function (name, index) {
                var month = String(index + 1).padStart(2, "0");
                return {
                    label: name + " " + year,
                    prefix: String(year) + "/" + month + "/",
                };
            });
        }

        function monthIndexFromDate(dateValue) {
            if (!dateValue) {
                return 0;
            }
            var parts = dateValue.split("/");
            if (parts.length !== 3) {
                return 0;
            }
            var month = parseInt(parts[1], 10);
            if (Number.isNaN(month) || month < 1 || month > 12) {
                return 0;
            }
            return month - 1;
        }

        var jalaliYear = parseInt(root.dataset.jalaliYear || "1404", 10);
        var months = buildMonths(jalaliYear);

        var state = {
            metric: metricToggle.dataset.defaultMetric || "body_fat",
            metricLabel: metricToggle.dataset.defaultLabel || "درصد چربی بدن",
            startDate: getDateDisplay(startInput),
            endDate: getDateDisplay(endInput),
            monthIndex: monthIndexFromDate(getDateDisplay(startInput) || getDateDisplay(endInput)),
            draftStart: "",
            draftEnd: "",
        };

        function currentMonth() {
            return months[state.monthIndex] || months[0];
        }

        function closeMenus() {
            if (metricMenu) {
                metricMenu.hidden = true;
            }
            if (calendar) {
                calendar.hidden = true;
            }
            metricToggle.setAttribute("aria-expanded", "false");
        }

        function syncHiddenInputs() {
            if (metricInput) {
                metricInput.value = state.metric;
            }
            if (startHidden) {
                startHidden.value = state.startDate;
            }
            if (endHidden) {
                endHidden.value = state.endDate;
            }
        }

        function submitFilters() {
            syncHiddenInputs();
            if (filterForm) {
                filterForm.submit();
            }
        }

        function syncChartVisibility() {
            if (!chartCard || !emptyState) {
                return;
            }
        }

        function dayFromDateString(value) {
            if (!value) {
                return "";
            }
            var parts = value.split("/");
            return parts.length === 3 ? parts[2] : "";
        }

        function renderCalendar() {
            var month = currentMonth();
            if (calendarTitle) {
                calendarTitle.textContent = month.label;
            }

            calendarGrid.innerHTML = "";
            for (var day = 1; day <= 31; day += 1) {
                var button = document.createElement("button");
                button.type = "button";
                button.className = "analysis-calendar__day";
                button.textContent = String(day);
                button.dataset.day = String(day);

                var start = Number(state.draftStart || 0);
                var end = Number(state.draftEnd || 0);
                if (start && end && day >= start && day <= end) {
                    button.classList.add("is-in-range");
                }
                if (start && day === start) {
                    button.classList.add("is-start");
                }
                if (end && day === end) {
                    button.classList.add("is-end");
                }

                button.addEventListener("click", function (event) {
                    event.stopPropagation();
                    var selectedDay = Number(this.dataset.day);
                    if (!state.draftStart || (state.draftStart && state.draftEnd)) {
                        state.draftStart = String(selectedDay);
                        state.draftEnd = "";
                    } else if (selectedDay < Number(state.draftStart)) {
                        state.draftEnd = state.draftStart;
                        state.draftStart = String(selectedDay);
                    } else {
                        state.draftEnd = String(selectedDay);
                    }
                    renderCalendar();
                });

                calendarGrid.appendChild(button);
            }
        }

        metricToggle.addEventListener("click", function () {
            var expanded = metricToggle.getAttribute("aria-expanded") === "true";
            metricToggle.setAttribute("aria-expanded", expanded ? "false" : "true");
            if (metricMenu) {
                metricMenu.hidden = expanded;
            }
            if (calendar) {
                calendar.hidden = true;
            }
        });

        metricButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                state.metric = button.dataset.analysisMetric;
                state.metricLabel = button.textContent.trim();
                if (metricLabel) {
                    metricLabel.textContent = state.metricLabel;
                }
                closeMenus();
                submitFilters();
            });
        });

        [startInput, endInput].forEach(function (input) {
            if (!input) {
                return;
            }
            input.addEventListener("click", function () {
                state.draftStart = dayFromDateString(state.startDate);
                state.draftEnd = dayFromDateString(state.endDate);
                if (calendar) {
                    calendar.hidden = false;
                }
                if (metricMenu) {
                    metricMenu.hidden = true;
                }
                renderCalendar();
            });
        });

        if (calendarPrev) {
            calendarPrev.addEventListener("click", function () {
                state.monthIndex = Math.max(0, state.monthIndex - 1);
                renderCalendar();
            });
        }

        if (calendarNext) {
            calendarNext.addEventListener("click", function () {
                state.monthIndex = Math.min(months.length - 1, state.monthIndex + 1);
                renderCalendar();
            });
        }

        if (calendarConfirm) {
            calendarConfirm.addEventListener("click", function () {
                if (!state.draftStart) {
                    return;
                }
                var monthPrefix = currentMonth().prefix;
                var startValue = monthPrefix + String(state.draftStart).padStart(2, "0");
                var endDay = state.draftEnd || state.draftStart;
                var endValue = monthPrefix + String(endDay).padStart(2, "0");

                state.startDate = startValue;
                state.endDate = endValue;
                setDateDisplay(startInput, startValue);
                setDateDisplay(endInput, endValue);
                if (calendar) {
                    calendar.hidden = true;
                }
                submitFilters();
            });
        }

        document.addEventListener("click", function (event) {
            if (!root.contains(event.target)) {
                closeMenus();
            }
        });

        if (metricLabel) {
            metricLabel.textContent = state.metricLabel;
        }
        syncHiddenInputs();
        renderCalendar();
        syncChartVisibility();
    }

    function initSubmitLoading(root) {
        root.querySelectorAll("form").forEach(function (form) {
            form.addEventListener("submit", function () {
                var submitButton = form.querySelector('[type="submit"]');
                if (!submitButton || submitButton.classList.contains("is-loading")) {
                    return;
                }

                submitButton.classList.add("is-loading");
                submitButton.setAttribute("aria-busy", "true");
            });
        });
    }

    function initCoachFileChips(root) {
        var input = root.querySelector("[data-coach-file-input]");
        var list = root.querySelector("[data-coach-file-chips]");
        if (!input || !list) {
            return;
        }
        input.addEventListener("change", function () {
            list.innerHTML = "";
            Array.prototype.forEach.call(input.files, function (file) {
                var sizeMb = (file.size / (1024 * 1024)).toFixed(1);
                var chip = document.createElement("li");
                chip.className = "coach-file-chip";
                if (file.size > 15 * 1024 * 1024) {
                    chip.classList.add("is-invalid");
                }
                chip.textContent = file.name + " (" + sizeMb + " MB)";
                list.appendChild(chip);
            });
        });
    }

    document.addEventListener("focusin", function (event) {
        var target = event.target;
        if (!target || target.tagName !== "INPUT") {
            return;
        }
        if (target.dataset.selectAllOnFocus !== "true") {
            return;
        }
        window.requestAnimationFrame(function () {
            selectTextOnFocus(target);
        });
    });

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll(".blood-group-grid").forEach(initBloodGroupChips);
        document.querySelectorAll("[data-analysis-root]").forEach(initAnalysisScreen);
        document.querySelectorAll("[data-coach-form]").forEach(initCoachFileChips);
        initSubmitLoading(document);
        if (typeof resetSubmitLoadingStates === "function") {
            resetSubmitLoadingStates();
        }
    });

    window.addEventListener("pageshow", function () {
        if (typeof resetSubmitLoadingStates === "function") {
            resetSubmitLoadingStates();
        }
    });
})();
