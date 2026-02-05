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
