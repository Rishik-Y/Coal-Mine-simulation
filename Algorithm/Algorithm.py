import csv
from collections import defaultdict
import networkx as nx
import matplotlib.pyplot as plt
import heapq
import functools
import itertools
import copy

# Read edges from CSV
edges = []
with open('edges.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        edges.append((row['source'], row['destination'], int(row['distance'])))

# Build graph
G = nx.Graph()
for src, dst, dist in edges:
    G.add_edge(src, dst, weight=dist)

# Draw graph
# Use edge distances to influence layout
edge_lengths = {(src, dst): dist for src, dst, dist in edges}

# Kamada-Kawai layout uses edge weights as distances
G_for_layout = nx.Graph()
for src, dst, dist in edges:
    G_for_layout.add_edge(src, dst, weight=dist)

pos = nx.kamada_kawai_layout(G_for_layout, weight='weight')
plt.figure(figsize=(8,6))
nx.draw(G, pos, with_labels=True, node_color='lightblue', node_size=1200, font_size=12, font_weight='bold', edge_color='gray')
labels = nx.get_edge_attributes(G, 'weight')
nx.draw_networkx_edge_labels(G, pos, edge_labels=labels)
plt.title("Coal Mine Network Map (Edge Lengths = Distances)")
# Save the graph as an image instead of displaying it
plt.savefig("map.png")
# plt.show()  # Commented out to avoid display issues

class Truck:
    def __init__(self, truck_id, capacity, location):
        self.truck_id = truck_id
        self.capacity = capacity
        self.location = location
        self.loaded = 0
        self.total_time = 0
        self.route = []

    def __str__(self):
        return f"Truck {self.truck_id}: Location={self.location}, Capacity={self.capacity}kg, Loaded={self.loaded}kg, Total Time={self.total_time}s"

# Read node capacities
node_capacities = {}
with open('nodes.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        node_capacities[row['source']] = int(row['source_capacity'])

# Dijkstra's algorithm for shortest path (fastest path since 1km=1s)
def dijkstra(graph, start, end):
    queue = [(0, start, [])]
    visited = set()
    while queue:
        (cost, node, path) = heapq.heappop(queue)
        if node in visited:
            continue
        visited.add(node)
        path = path + [node]
        if node == end:
            return (cost, path)
        for neighbor in graph[node]:
            if neighbor[0] not in visited:
                heapq.heappush(queue, (cost + neighbor[1], neighbor[0], path))
    return (float('inf'), [])

# Build adjacency list for Dijkstra
adjacency = defaultdict(list)
for src, dst, dist in edges:
    adjacency[src].append((dst, dist))
    adjacency[dst].append((src, dist))

# Initialize truck
truck = Truck(truck_id=1, capacity=100, location='Dump_site')

# Simulate truck visiting each mine, loading, and returning to dump site
def simulate_truck(truck, mines, dump_site):
    for mine in mines:
        if node_capacities[mine] == 0:
            continue  # Skip empty mines
        # Fastest path from current location to mine
        time_to_mine, path_to_mine = dijkstra(adjacency, truck.location, mine)
        print(f"Truck Route: {' -> '.join(path_to_mine)}: Time Taken: {time_to_mine}s")
        truck.total_time += time_to_mine
        truck.route += path_to_mine[1:]  # skip current location
        truck.location = mine
        # Load coal
        load_amount = min(truck.capacity, node_capacities[mine])
        truck.loaded = load_amount
        node_capacities[mine] -= load_amount
        print(f"Truck loaded {load_amount}kg coal at {mine}")
        # Fastest path back to dump site
        time_to_dump, path_to_dump = dijkstra(adjacency, truck.location, dump_site)
        print(f"Truck Route: {' -> '.join(path_to_dump)}: Time Taken: {time_to_dump}s")
        truck.total_time += time_to_dump
        truck.route += path_to_dump[1:]
        truck.location = dump_site
        # Unload coal
        node_capacities[dump_site] += truck.loaded
        print(f"Truck unloaded: {truck.loaded}kg coal at {dump_site}")
        truck.loaded = 0
    print(f"Simulation complete. Total time: {truck.total_time}s. Final dump site coal: {node_capacities[dump_site]}kg")

# Simulate truck visiting each mine until all coal is depleted
def simulate_truck_deplete(truck, mines, dump_site):
    while any(node_capacities[mine] > 0 for mine in mines):
        for mine in mines:
            while node_capacities[mine] > 0:
                # Fastest path from current location to mine
                time_to_mine, path_to_mine = dijkstra(adjacency, truck.location, mine)
                print(f"Truck Route: {' -> '.join(path_to_mine)}: Time Taken: {time_to_mine}s")
                truck.total_time += time_to_mine
                truck.route += path_to_mine[1:]  # skip current location
                truck.location = mine
                # Load coal
                load_amount = min(truck.capacity, node_capacities[mine])
                truck.loaded = load_amount
                node_capacities[mine] -= load_amount
                print(f"Truck loaded {load_amount}kg coal at {mine}")
                # Fastest path back to dump site
                time_to_dump, path_to_dump = dijkstra(adjacency, truck.location, dump_site)
                print(f"Truck Route: {' -> '.join(path_to_dump)}: Time Taken: {time_to_dump}s")
                truck.total_time += time_to_dump
                truck.route += path_to_dump[1:]
                truck.location = dump_site
                # Unload coal
                node_capacities[dump_site] += truck.loaded
                print(f"Truck unloaded: {truck.loaded}kg coal at {dump_site}")
                truck.loaded = 0
    print(f"Simulation complete. Total time: {truck.total_time}s. Final dump site coal: {node_capacities[dump_site]}kg")

def dp_min_time(node_capacities, truck_capacity, adjacency, dump_site):
    mines = [node for node in node_capacities if node != dump_site]
    mine_indices = {mine: i for i, mine in enumerate(mines)}
    initial_state = tuple(node_capacities[mine] for mine in mines)

    @functools.lru_cache(maxsize=None)
    def dp(state, truck_location):
        # If all mines are depleted
        if all(coal == 0 for coal in state):
            # Return time to dump site if not already there
            if truck_location == dump_site:
                return 0
            else:
                t, _ = dijkstra(adjacency, truck_location, dump_site)
                return t
        min_time = float('inf')
        # Try all possible combinations of mines to visit in one trip
        for r in range(1, len(mines)+1):
            for combo in itertools.combinations([i for i, coal in enumerate(state) if coal > 0], r):
                # Can truck carry all selected coal?
                coal_to_pick = [min(state[i], truck.capacity) for i in combo]
                if sum(coal_to_pick) > truck.capacity:
                    continue
                # Try all orders
                for order in itertools.permutations(combo):
                    route = [truck_location] + [mines[i] for i in order] + [dump_site]
                    time = 0
                    for i in range(len(route)-1):
                        t, _ = dijkstra(adjacency, route[i], route[i+1])
                        time += t
                    # Update state
                    new_state = list(state)
                    remaining_capacity = truck.capacity
                    for i in order:
                        take = min(new_state[i], remaining_capacity)
                        remaining_capacity -= take
                        new_state[i] -= take
                    # Recurse
                    total_time = time + dp(tuple(new_state), dump_site)
                    if total_time < min_time:
                        min_time = total_time
        return min_time

    min_total_time = dp(initial_state, dump_site)
    print(f"Minimal total travel time to deplete all mines: {min_total_time}s")

def dp_min_time_with_procedure(node_capacities, truck_capacity, adjacency, dump_site):
    mines = [node for node in node_capacities if node != dump_site]
    initial_state = tuple(node_capacities[mine] for mine in mines)
    memo = {}
    choice = {}

    def dp(state, truck_location):
        key = (state, truck_location)
        if key in memo:
            return memo[key]
        if all(coal == 0 for coal in state):
            if truck_location == dump_site:
                memo[key] = 0
                choice[key] = None
                return 0
            else:
                t, _ = dijkstra(adjacency, truck_location, dump_site)
                memo[key] = t
                choice[key] = ([], [], [truck_location, dump_site], t)
                return t
        min_time = float('inf')
        best_trip = None
        # Try all possible combinations of mines to visit in one trip
        for r in range(1, len(mines)+1):
            for combo in itertools.combinations([i for i, coal in enumerate(state) if coal > 0], r):
                # Can truck carry all selected coal?
                coal_to_pick = [min(state[i], truck_capacity) for i in combo]
                if sum(coal_to_pick) > truck_capacity:
                    continue
                # Try all orders
                for order in itertools.permutations(combo):
                    route = [truck_location] + [mines[i] for i in order] + [dump_site]
                    time = 0
                    for i in range(len(route)-1):
                        t, _ = dijkstra(adjacency, route[i], route[i+1])
                        time += t
                    # Update state
                    new_state = list(state)
                    remaining_capacity = truck_capacity
                    for i in order:
                        take = min(new_state[i], remaining_capacity)
                        remaining_capacity -= take
                        new_state[i] -= take
                    # Recurse
                    total_time = time + dp(tuple(new_state), dump_site)
                    if total_time < min_time:
                        min_time = total_time
                        best_trip = (order, [mines[i] for i in order], route, time)
        memo[key] = min_time
        choice[key] = best_trip
        return min_time

    min_total_time = dp(initial_state, dump_site)
    print(f"Minimal total travel time to deplete all mines: {min_total_time}s\n")
    # Reconstruct procedure
    print("--- DP-based Optimal Truck Procedure ---")
    state = initial_state
    truck_location = dump_site
    trip_num = 1
    cumulative_time = 0
    while not all(coal == 0 for coal in state):
        key = (state, truck_location)
        best_trip = choice[key]
        if best_trip is None:
            break
        order, mines_order, route, trip_time = best_trip
        trip_mines = [mines[i] for i in order]
        # Print full route as requested (with return to first mine before dump_site)
        print(f"Trip {trip_num}: Truck route: {' -> '.join([dump_site] + trip_mines + [trip_mines[0], dump_site])} (Trip time: {trip_time}s)")
        remaining_capacity = truck_capacity
        new_state = list(state)
        collected_this_trip = 0
        for idx, mine in enumerate(trip_mines):
            t, path = dijkstra(adjacency, truck_location, mine)
            print(f"{truck_location} -> {mine}: Time Taken: {t}s,")
            take = min(new_state[order[idx]], remaining_capacity)
            print(f"Truck loaded {take}kg coal at {mine}")
            remaining_capacity -= take
            new_state[order[idx]] -= take
            collected_this_trip += take
            truck_location = mine
        # Final leg: from last mine to dump_site, via first mine if needed
        t, path = dijkstra(adjacency, truck_location, dump_site)
        # Print the full path from last mine to dump_site
        print(f"{truck_location} -> {' -> '.join(path[1:])}: Time Taken: {t}s")
        print(f"Truck unloaded at {dump_site}: Collected: {collected_this_trip}kg")
        cumulative_time += trip_time
        print(f"Current Time: {cumulative_time}s\n")
        truck_location = dump_site
        state = tuple(new_state)
        trip_num += 1
    print(f"All mines depleted. Total trips: {trip_num-1}. Total time: {min_total_time}s.")

# --- Run DP-based optimizer with procedure ---
print("\n--- DP-based Minimal Time Calculation & Optimal Procedure ---")
dp_node_capacities = copy.deepcopy(node_capacities)
dp_min_time_with_procedure(dp_node_capacities, truck.capacity, adjacency, 'Dump_site')