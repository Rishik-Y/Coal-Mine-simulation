import csv
from collections import defaultdict
import networkx as nx
import matplotlib.pyplot as plt
import heapq

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
truck = Truck(truck_id=1, capacity=70, location='Dump_site')

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

# List of mines (exclude dump site)
mines = [node for node in node_capacities if node != 'Dump_site']
simulate_truck_deplete(truck, mines, 'Dump_site')
