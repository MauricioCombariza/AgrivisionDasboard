import numpy as np

def nearest_neighbor_route(points):
    n = len(points)
    if n == 0:
        return []
    visited = [False] * n
    route = [0]  # Comenzamos por el primer punto
    visited[0] = True

    for _ in range(n - 1):
        last = route[-1]
        next_idx = None
        min_dist = float('inf')
        for j in range(n):
            if not visited[j]:
                dist = np.linalg.norm(points[last] - points[j])
                if dist < min_dist:
                    min_dist = dist
                    next_idx = j

        if next_idx is None:
            # Esto no debería pasar, pero prevenimos errores
            break

        route.append(next_idx)
        visited[next_idx] = True

    return route
