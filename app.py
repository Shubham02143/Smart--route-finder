from flask import Flask, render_template, request, jsonify
from datetime import datetime
import heapq
import os
import sqlite3

app = Flask(__name__)

# ---------- DATABASE (SQLite) ----------

DB_PATH = os.path.join(os.path.dirname(__file__), "routes.db")


def run_query(sql, params=(), fetch=False):
    """Open the database, run one query, and close it again."""
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    try:
        cursor = connection.execute(sql, params)
        rows = cursor.fetchall() if fetch else None
        connection.commit()
        return rows
    finally:
        connection.close()


def init_db():
    """Create the table the first time the app runs."""
    run_query("""
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start TEXT NOT NULL,
            destination TEXT NOT NULL,
            distance INTEGER NOT NULL,
            traffic INTEGER NOT NULL,
            searched_at TEXT NOT NULL
        )
    """)


def save_search(start, destination, distance, traffic):
    """Save a search, unless it is identical to the latest one."""
    latest = run_query(
        "SELECT start, destination, traffic FROM searches "
        "ORDER BY id DESC LIMIT 1",
        fetch=True
    )

    if latest:
        last = latest[0]
        if (last["start"] == start
                and last["destination"] == destination
                and last["traffic"] == int(traffic)):
            return

    run_query(
        "INSERT INTO searches "
        "(start, destination, distance, traffic, searched_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            start,
            destination,
            distance,
            int(traffic),
            datetime.now().strftime("%d %b, %I:%M %p")
        )
    )


init_db()

# ---------- ROAD DATA ----------

# City positions on the SVG graph: (x, y)
CITIES = {
    "Ludhiana":   (90, 85),
    "Khanna":     (320, 85),
    "Chandigarh": (530, 85),
    "Sirhind":    (90, 290),
    "Patiala":    (320, 195),
    "Mohali":     (530, 290),
}

# Illustrative roads: (city A, city B, distance in km, traffic level)
ROADS = [
    ("Ludhiana", "Khanna", 35, "light"),
    ("Ludhiana", "Sirhind", 70, "moderate"),
    ("Khanna", "Sirhind", 25, "light"),
    ("Khanna", "Mohali", 50, "heavy"),
    ("Sirhind", "Mohali", 40, "light"),
    ("Khanna", "Chandigarh", 60, "moderate"),
    ("Chandigarh", "Mohali", 12, "light"),
    ("Khanna", "Patiala", 55, "light"),
    ("Sirhind", "Patiala", 25, "light"),
    ("Patiala", "Mohali", 65, "moderate"),
]

# Traffic makes a road "feel" longer when traffic mode is on
TRAFFIC_FACTOR = {"light": 1.0, "moderate": 1.3, "heavy": 1.6}

# Build the graph. Every road works in both directions.
graph = {city: {} for city in CITIES}

for a, b, km, traffic in ROADS:
    graph[a][b] = {"km": km, "traffic": traffic}
    graph[b][a] = {"km": km, "traffic": traffic}


def dijkstra(graph, start, destination, use_traffic=False):
    """Shortest route using Dijkstra's algorithm.
    If use_traffic is True, busy roads cost more."""

    distances = {city: float("inf") for city in graph}
    previous = {city: None for city in graph}

    distances[start] = 0
    priority_queue = [(0, start)]

    while priority_queue:
        current_distance, current_city = heapq.heappop(priority_queue)

        if current_distance > distances[current_city]:
            continue

        if current_city == destination:
            break

        for neighbour, road in graph[current_city].items():
            cost = road["km"]
            if use_traffic:
                cost = cost * TRAFFIC_FACTOR[road["traffic"]]

            new_distance = current_distance + cost

            if new_distance < distances[neighbour]:
                distances[neighbour] = new_distance
                previous[neighbour] = current_city
                heapq.heappush(priority_queue, (new_distance, neighbour))

    if distances[destination] == float("inf"):
        return None

    route = []
    city = destination

    while city is not None:
        route.append(city)
        city = previous[city]

    route.reverse()
    return route


def get_roads():
    """Each road once, for drawing the graph."""
    roads = []

    for a, b, km, traffic in ROADS:
        first, second = sorted((a, b))
        roads.append({
            "from": first,
            "to": second,
            "distance": km,
            "traffic": traffic
        })

    return roads


# ---------- PAGES ----------

@app.route("/")
def home():
    positions = {
        city: {"x": x, "y": y}
        for city, (x, y) in CITIES.items()
    }

    return render_template(
        "index.html",
        cities=list(graph.keys()),
        roads=get_roads(),
        positions=positions
    )


@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.get_json(silent=True) or {}

    start = data.get("start")
    destination = data.get("destination")
    use_traffic = bool(data.get("traffic"))
    should_save = bool(data.get("save"))

    if start not in graph or destination not in graph:
        return jsonify({
            "error": "Please select valid starting and destination cities."
        }), 400

    if start == destination:
        return jsonify({
            "error": "Starting city and destination must be different."
        }), 400

    route = dijkstra(graph, start, destination, use_traffic)

    if route is None:
        return jsonify({
            "route": None,
            "distance": None,
            "message": "No connected route exists."
        })

    legs = []
    for a, b in zip(route, route[1:]):
        road = graph[a][b]
        legs.append({
            "from": a,
            "to": b,
            "km": road["km"],
            "traffic": road["traffic"]
        })

    total_km = sum(leg["km"] for leg in legs)

    if should_save:
        save_search(start, destination, total_km, use_traffic)

    return jsonify({
        "route": route,
        "distance": total_km,
        "legs": legs,
        "traffic": use_traffic
    })


@app.route("/history")
def history():
    """Return the 5 most recent searches."""
    rows = run_query(
        "SELECT start, destination, distance, traffic, searched_at "
        "FROM searches ORDER BY id DESC LIMIT 5",
        fetch=True
    )

    return jsonify([
        {
            "start": row["start"],
            "destination": row["destination"],
            "distance": row["distance"],
            "traffic": bool(row["traffic"]),
            "time": row["searched_at"]
        }
        for row in rows
    ])


@app.route("/clear-history", methods=["POST"])
def clear_history():
    run_query("DELETE FROM searches")
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)