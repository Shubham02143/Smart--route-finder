document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("route-form");
    const startSelect = document.getElementById("start");
    const destinationSelect = document.getElementById("destination");
    const trafficCheckbox = document.getElementById("traffic");
    const swapButton = document.getElementById("swap-button");
    const button = document.getElementById("find-route-button");

    const resultCard = document.getElementById("result-card");
    const resultTitle = document.getElementById("result-title");
    const resultDescription = document.getElementById("result-description");
    const totalDistance = document.getElementById("total-distance");
    const routeSequence = document.getElementById("route-sequence");
    const routeLegs = document.getElementById("route-legs");

    const loadingMessage = document.getElementById("loading-message");
    const errorMessage = document.getElementById("error-message");
    const highlightedRoads = document.getElementById("highlighted-roads");

    const historyList = document.getElementById("history-list");
    const clearHistoryButton = document.getElementById("clear-history");

    // The first automatic calculation (page load) is not saved.
    let readyToSave = false;

    function clearHighlightedRoads() {
        highlightedRoads.replaceChildren();
    }

    function drawRoute(route) {
        clearHighlightedRoads();

        if (!Array.isArray(route) || route.length < 2) {
            return;
        }

        for (let i = 0; i < route.length - 1; i++) {
            const fromCity = route[i];
            const toCity = route[i + 1];

            const road = document.querySelector(
                `.road[data-from="${fromCity}"][data-to="${toCity}"], ` +
                `.road[data-from="${toCity}"][data-to="${fromCity}"]`
            );

            if (!road) {
                console.warn(`Road not found between ${fromCity} and ${toCity}`);
                continue;
            }

            const originalLine = road.querySelector(".road-line");

            if (!originalLine) {
                continue;
            }

            const highlightedLine = document.createElementNS(
                "http://www.w3.org/2000/svg",
                "line"
            );

            ["x1", "y1", "x2", "y2"].forEach(attribute => {
                highlightedLine.setAttribute(
                    attribute,
                    originalLine.getAttribute(attribute)
                );
            });

            highlightedLine.setAttribute("class", "highlighted-road-line");
            highlightedRoads.appendChild(highlightedLine);
        }
    }

    function showLegs(legs) {
        routeLegs.replaceChildren();

        if (!Array.isArray(legs)) {
            return;
        }

        legs.forEach(leg => {
            const item = document.createElement("li");

            const name = document.createElement("span");
            name.textContent = `${leg.from} → ${leg.to}`;

            const info = document.createElement("span");
            info.className = "leg-info";

            const dot = document.createElement("span");
            dot.className = `traffic-dot traffic-${leg.traffic}`;

            info.append(dot, `${leg.km} km · ${leg.traffic} traffic`);
            item.append(name, info);
            routeLegs.appendChild(item);
        });
    }

    function showResult(data) {
        resultCard.hidden = false;

        if (!data.route) {
            resultTitle.textContent = "No Route Found";
            resultDescription.textContent =
                data.message || "No connected route exists.";
            totalDistance.textContent = "—";
            routeSequence.replaceChildren();
            routeLegs.replaceChildren();
            clearHighlightedRoads();
            return;
        }

        resultTitle.textContent = "Shortest Route Found";
        resultDescription.textContent = data.traffic
            ? "Calculated with traffic delays included."
            : "Your route has been calculated.";

        totalDistance.textContent = data.distance;
        routeSequence.replaceChildren();

        data.route.forEach((city, index) => {
            const cityElement = document.createElement("span");
            cityElement.className = "city";
            cityElement.textContent = city;
            routeSequence.appendChild(cityElement);

            if (index < data.route.length - 1) {
                const arrow = document.createElement("span");
                arrow.className = "arrow";
                arrow.textContent = "→";
                routeSequence.appendChild(arrow);
            }
        });

        showLegs(data.legs);
        drawRoute(data.route);
    }

    // ----- Search history (comes from the SQLite database) -----

    async function loadHistory() {
        if (!historyList) return;

        try {
            const response = await fetch("/history");
            const items = await response.json();

            historyList.replaceChildren();

            if (items.length === 0) {
                const empty = document.createElement("li");
                empty.className = "history-empty";
                empty.textContent = "No searches yet.";
                historyList.appendChild(empty);
                return;
            }

            items.forEach(item => {
                const row = document.createElement("li");

                const title = document.createElement("span");
                title.className = "history-route";
                title.textContent = `${item.start} → ${item.destination}`;

                const details = document.createElement("span");
                details.className = "history-details";
                details.textContent =
                    `${item.distance} km · ` +
                    `${item.traffic ? "traffic on" : "traffic off"} · ` +
                    item.time;

                row.append(title, details);
                historyList.appendChild(row);
            });
        } catch (error) {
            console.warn("Could not load history", error);
        }
    }

    if (clearHistoryButton) {
        clearHistoryButton.addEventListener("click", async () => {
            await fetch("/clear-history", { method: "POST" });
            loadHistory();
        });
    }

    // ----- Form -----

    form.addEventListener("submit", async event => {
        event.preventDefault();

        errorMessage.hidden = true;
        errorMessage.textContent = "";

        loadingMessage.hidden = false;
        button.disabled = true;
        button.textContent = "Calculating...";

        try {
            const response = await fetch("/calculate", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    start: startSelect.value,
                    destination: destinationSelect.value,
                    traffic: trafficCheckbox.checked,
                    save: readyToSave
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.error || "Unable to calculate the route."
                );
            }

            showResult(data);
            readyToSave = true;
            loadHistory();
        } catch (error) {
            errorMessage.textContent =
                error.message || "Something went wrong. Please try again.";
            errorMessage.hidden = false;
        } finally {
            loadingMessage.hidden = true;
            button.disabled = false;
            button.textContent = "Find Shortest Route";
        }
    });

    // Swap the two cities and recalculate
    swapButton.addEventListener("click", () => {
        const temporary = startSelect.value;
        startSelect.value = destinationSelect.value;
        destinationSelect.value = temporary;
        form.requestSubmit();
    });

    // Recalculate when traffic mode changes
    trafficCheckbox.addEventListener("change", () => {
        form.requestSubmit();
    });

    // Show history and the default route when the page opens
    loadHistory();
    form.requestSubmit();
});