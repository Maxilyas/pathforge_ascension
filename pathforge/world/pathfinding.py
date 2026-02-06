from __future__ import annotations
import collections
from typing import List, Tuple, Optional, Dict
from ..settings import PATH_TILES

Coord = Tuple[int,int]

def bfs_path(grid: list[list[int]], start: Coord, end: Coord) -> Optional[List[Coord]]:
    """Classic BFS, used for validity checks and previews."""
    cols = len(grid)
    rows = len(grid[0]) if cols else 0
    q = collections.deque([start])
    parent: Dict[Coord, Optional[Coord]] = {start: None}
    seen = {start}
    walk = set(PATH_TILES)

    while q:
        cx,cy = q.popleft()
        if (cx,cy) == end:
            break
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx,ny = cx+dx, cy+dy
            if 0<=nx<cols and 0<=ny<rows and (nx,ny) not in seen and grid[nx][ny] in walk:
                seen.add((nx,ny))
                parent[(nx,ny)] = (cx,cy)
                q.append((nx,ny))

    if end not in parent:
        return None

    out=[]
    cur=end
    while cur is not None:
        out.append(cur)
        cur=parent[cur]
    out.reverse()
    return out

def distance_map(grid: list[list[int]], ends: list[Coord]) -> Dict[Coord, int]:
    """Reverse BFS from end(s). Used for branching & lane preview."""
    cols = len(grid)
    rows = len(grid[0]) if cols else 0
    walk = set(PATH_TILES)

    dist: Dict[Coord, int] = {}
    q = collections.deque()

    for e in ends:
        if 0<=e[0]<cols and 0<=e[1]<rows and grid[e[0]][e[1]] in walk:
            dist[e] = 0
            q.append(e)

    while q:
        cx,cy = q.popleft()
        d = dist[(cx,cy)]
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx,ny = cx+dx, cy+dy
            if 0<=nx<cols and 0<=ny<rows and grid[nx][ny] in walk and (nx,ny) not in dist:
                dist[(nx,ny)] = d+1
                q.append((nx,ny))

    return dist


def chain_path(grid: list[list[int]], start: Coord, end: Coord) -> Optional[List[Coord]]:
    """Trace a single non-branching path from start to end.
    Rules (on the connected component reachable from START):
      - START and END have degree 1
      - every other reachable path tile has degree 2
    This makes labyrinth-style 'one long lane' predictable (no hidden shortcuts)."""
    cols = len(grid)
    rows = len(grid[0]) if cols else 0
    walk = set(PATH_TILES)

    # BFS reachable from start
    from collections import deque
    seen = set()
    q = deque([start])
    if not (0 <= start[0] < cols and 0 <= start[1] < rows):
        return None
    if grid[start[0]][start[1]] not in walk:
        return None
    seen.add(start)
    while q:
        cx, cy = q.popleft()
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = cx+dx, cy+dy
            if 0<=nx<cols and 0<=ny<rows and (nx,ny) not in seen and grid[nx][ny] in walk:
                seen.add((nx,ny))
                q.append((nx,ny))

    if end not in seen:
        return None

    def neigh(c: Coord) -> list[Coord]:
        cx, cy = c
        out=[]
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = cx+dx, cy+dy
            if 0<=nx<cols and 0<=ny<rows and (nx,ny) in seen:
                out.append((nx,ny))
        return out

    # degree check
    for c in seen:
        d = len(neigh(c))
        if c in (start, end):
            if d != 1:
                return None
        else:
            if d != 2:
                return None

    # trace deterministically
    path=[start]
    prev=None
    cur=start
    visited=set([start])
    while cur != end:
        ns = neigh(cur)
        nxt = ns[0] if ns[0] != prev else ns[1]
        if nxt in visited:
            return None
        visited.add(nxt)
        path.append(nxt)
        prev, cur = cur, nxt

        # sanity guard
        if len(path) > len(seen) + 2:
            return None

    return path
