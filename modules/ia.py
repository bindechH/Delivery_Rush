"""
IA systems for Delivery Rush.

This module provides:
- MapNavigator: road navigation helpers + A* pathfinding.
- TrafficAI: simple traffic vehicles with seek/arrive path following.
- PursuitAI: enemy/police pursuit logic prepared for future mission systems.
- AIManager: update loop, alert state machine, and world-entity export.

The code is intentionally gameplay-oriented (simple steering, low CPU cost)
so it can be integrated incrementally.
"""

from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
import random
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


TilePoint = Tuple[int, int]
WorldPoint = Tuple[float, float]
RectLike = Any

# Approximate conversion used by gameplay tuning.
WORLD_UNITS_PER_KMH = 2.0
TRAFFIC_CRUISE_KMH = 30.0
TRAFFIC_MAX_KMH = 36.0
ROBBER_CAR_POOL: Tuple[Tuple[str, str], ...] = (
    ("MUSCLECAR", "Black"),
    ("SPORT", "Red"),
    ("COUPE", "Blue"),
    ("SEDAN", "Black"),
)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _normalize_angle_deg(angle: float) -> float:
    return angle % 360.0


def _shortest_angle_delta(current: float, target: float) -> float:
    return (target - current + 180.0) % 360.0 - 180.0


def _distance(a: WorldPoint, b: WorldPoint) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _kmh_to_world_speed(speed_kmh: float) -> float:
    return max(0.0, speed_kmh * WORLD_UNITS_PER_KMH)


def _distance_sq(a: WorldPoint, b: WorldPoint) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def _rect_components(rect: RectLike) -> Optional[Tuple[float, float, float, float]]:
    if rect is None:
        return None
    if hasattr(rect, "x") and hasattr(rect, "y") and hasattr(rect, "width") and hasattr(rect, "height"):
        return float(rect.x), float(rect.y), float(rect.width), float(rect.height)
    if isinstance(rect, dict):
        keys = ("x", "y", "w", "h")
        if all(k in rect for k in keys):
            return float(rect["x"]), float(rect["y"]), float(rect["w"]), float(rect["h"])
        keys = ("x", "y", "width", "height")
        if all(k in rect for k in keys):
            return float(rect["x"]), float(rect["y"]), float(rect["width"]), float(rect["height"])
    if isinstance(rect, (tuple, list)) and len(rect) == 4:
        return float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])
    return None


def _rect_center(rect: RectLike) -> Optional[WorldPoint]:
    comp = _rect_components(rect)
    if comp is None:
        return None
    x, y, w, h = comp
    return x + w * 0.5, y + h * 0.5


def _rect_distance(rect_a: RectLike, rect_b: RectLike) -> float:
    ca = _rect_center(rect_a)
    cb = _rect_center(rect_b)
    if ca is None or cb is None:
        return float("inf")
    return _distance(ca, cb)


def _rects_overlap(rect_a: RectLike, rect_b: RectLike) -> bool:
    a = _rect_components(rect_a)
    b = _rect_components(rect_b)
    if a is None or b is None:
        return False
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by)


# ---------------------------------------------------------------------------
# Navigation / A*
# ---------------------------------------------------------------------------


class MapNavigator:
    """Road-oriented navigation helpers on top of GameMap."""

    def __init__(self, game_map: Any, allow_diagonal: bool = False):
        self.game_map = game_map
        self.allow_diagonal = allow_diagonal

    def world_to_tile(self, world_x: float, world_y: float) -> TilePoint:
        tw = max(1, int(getattr(self.game_map, "tile_width", 32)))
        th = max(1, int(getattr(self.game_map, "tile_height", 32)))
        return int(world_x // tw), int(world_y // th)

    def tile_to_world(self, tx: int, ty: int, centered: bool = True) -> WorldPoint:
        tw = max(1, int(getattr(self.game_map, "tile_width", 32)))
        th = max(1, int(getattr(self.game_map, "tile_height", 32)))
        if centered:
            return tx * tw + tw * 0.5, ty * th + th * 0.5
        return float(tx * tw), float(ty * th)

    def in_bounds(self, tx: int, ty: int) -> bool:
        w = int(getattr(self.game_map, "map_width_tiles", 0))
        h = int(getattr(self.game_map, "map_height_tiles", 0))
        return 0 <= tx < w and 0 <= ty < h

    def is_road_tile(self, tx: int, ty: int) -> bool:
        if not self.in_bounds(tx, ty):
            return False

        collision_grid = getattr(self.game_map, "_collision_grid", None)
        if collision_grid is not None:
            try:
                if bool(collision_grid[ty][tx]):
                    return False
            except (IndexError, TypeError):
                return False

        road_grid = getattr(self.game_map, "_road_grid", None)
        if road_grid is not None:
            try:
                return bool(road_grid[ty][tx])
            except (IndexError, TypeError):
                return False

        if hasattr(self.game_map, "is_road_at"):
            wx, wy = self.tile_to_world(tx, ty, centered=True)
            return bool(self.game_map.is_road_at(wx, wy))

        return True

    def get_road_neighbors(self, tile: TilePoint) -> List[TilePoint]:
        tx, ty = tile
        dirs4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        dirs8 = [(-1, -1), (1, -1), (-1, 1), (1, 1)]
        dirs = dirs4 + dirs8 if self.allow_diagonal else dirs4
        out: List[TilePoint] = []
        for dx, dy in dirs:
            nx, ny = tx + dx, ty + dy
            if self.is_road_tile(nx, ny):
                out.append((nx, ny))
        return out

    def find_nearest_road_tile(self, tile: TilePoint, max_radius: int = 16) -> Optional[TilePoint]:
        tx, ty = tile
        if self.is_road_tile(tx, ty):
            return tile

        for radius in range(1, max_radius + 1):
            x0, x1 = tx - radius, tx + radius
            y0, y1 = ty - radius, ty + radius

            for x in range(x0, x1 + 1):
                for y in (y0, y1):
                    if self.is_road_tile(x, y):
                        return x, y
            for y in range(y0 + 1, y1):
                for x in (x0, x1):
                    if self.is_road_tile(x, y):
                        return x, y

        return None

    def _heuristic(self, a: TilePoint, b: TilePoint, kind: str) -> float:
        dx = abs(a[0] - b[0])
        dy = abs(a[1] - b[1])
        if kind == "manhattan":
            return float(dx + dy)
        return math.hypot(dx, dy)

    def find_road_path(
        self,
        start_world: WorldPoint,
        goal_world: WorldPoint,
        heuristic: str = "euclidean",
        max_expansions: int = 40000,
        turn_penalty: float = 0.1,
    ) -> List[WorldPoint]:
        start = self.world_to_tile(start_world[0], start_world[1])
        goal = self.world_to_tile(goal_world[0], goal_world[1])

        start = self.find_nearest_road_tile(start)
        goal = self.find_nearest_road_tile(goal)

        if start is None or goal is None:
            return []
        if start == goal:
            return [self.tile_to_world(start[0], start[1], centered=True)]

        counter = 0
        open_heap: List[Tuple[float, int, TilePoint]] = []
        heapq.heappush(open_heap, (0.0, counter, start))

        came_from: Dict[TilePoint, TilePoint] = {}
        g_score: Dict[TilePoint, float] = {start: 0.0}
        closed: set[TilePoint] = set()

        expansions = 0
        while open_heap and expansions < max_expansions:
            _, _, current = heapq.heappop(open_heap)
            if current in closed:
                continue
            if current == goal:
                break
            closed.add(current)
            expansions += 1

            prev = came_from.get(current)
            prev_dir = None
            if prev is not None:
                prev_dir = (current[0] - prev[0], current[1] - prev[1])

            for neighbor in self.get_road_neighbors(current):
                step_cost = math.hypot(neighbor[0] - current[0], neighbor[1] - current[1])
                if prev_dir is not None:
                    cur_dir = (neighbor[0] - current[0], neighbor[1] - current[1])
                    if cur_dir != prev_dir:
                        step_cost += turn_penalty

                tentative = g_score[current] + step_cost
                if tentative >= g_score.get(neighbor, float("inf")):
                    continue

                came_from[neighbor] = current
                g_score[neighbor] = tentative
                counter += 1
                f_score = tentative + self._heuristic(neighbor, goal, heuristic)
                heapq.heappush(open_heap, (f_score, counter, neighbor))

        if goal not in came_from and goal != start:
            return []

        path_tiles = [goal]
        while path_tiles[-1] != start:
            parent = came_from.get(path_tiles[-1])
            if parent is None:
                return []
            path_tiles.append(parent)
        path_tiles.reverse()

        path_world = [self.tile_to_world(tx, ty, centered=True) for tx, ty in path_tiles]

        # Keep exact destination if it is close to the last tile center.
        if _distance(path_world[-1], goal_world) <= max(getattr(self.game_map, "tile_width", 32), getattr(self.game_map, "tile_height", 32)):
            path_world[-1] = goal_world

        return path_world


# ---------------------------------------------------------------------------
# Traffic AI
# ---------------------------------------------------------------------------


@dataclass
class AIEntityState:
    x: float
    y: float
    angle: float
    car: Tuple[str, str]
    on_road: bool
    ai_kind: str
    ai_state: str


class TrafficAI:
    """Simple traffic car: waypoint following + local steering."""

    def __init__(
        self,
        ai_id: str,
        spawn_pos: WorldPoint,
        car: Tuple[str, str] = ("MICRO", "White"),
        waypoints: Optional[Sequence[WorldPoint]] = None,
        loop_waypoints: bool = True,
        max_speed: float = _kmh_to_world_speed(TRAFFIC_MAX_KMH),
        cruise_speed: float = _kmh_to_world_speed(TRAFFIC_CRUISE_KMH),
        accel: float = _kmh_to_world_speed(26.0),
        brake: float = _kmh_to_world_speed(40.0),
        turn_speed: float = 170.0,
        size: int = 134,
        hitbox_scale: float = 0.175,
        arrive_radius: float = 12.0,
        slow_radius: float = 230.0,
        rng: Optional[random.Random] = None,
    ):
        self.ai_id = ai_id
        self.entity_type = "traffic"

        self.x = float(spawn_pos[0])
        self.y = float(spawn_pos[1])
        self.angle = 0.0
        self.speed = 0.0

        self.max_speed = max_speed
        self.cruise_speed = min(cruise_speed, max_speed)
        self.accel = accel
        self.brake = brake
        self.turn_speed = turn_speed

        self.size = size
        self.hitbox_scale = hitbox_scale
        self.car = car

        self.on_road = True
        self.ai_state = "driving"

        self.arrive_radius = arrive_radius
        self.slow_radius = max(slow_radius, arrive_radius + 1.0)
        self.loop_waypoints = loop_waypoints
        self.waypoints: List[WorldPoint] = list(waypoints or [])
        self.waypoint_index = 0 if self.waypoints else -1

        # Dynamic traffic uses a small look-ahead so targets are not one tile away.
        self.dynamic_waypoint_hops = 3
        self.dynamic_min_distance = 24.0

        self._dynamic_waypoint: Optional[WorldPoint] = None
        self._last_road_tile: Optional[TilePoint] = None
        self._stuck_timer = 0.0

        self._rng = rng or random.Random()

        # Simple wall-following traffic behavior (right-hand side preference).
        self.sensor_max_dist = 220.0
        self.sensor_step = 8.0
        self.front_block_dist = 54.0
        self.side_open_dist = 96.0
        self.right_target_dist = 44.0
        self.right_min_dist = 18.0
        self._turn_commit_timer = 0.0
        self._turn_command = 0.0

        # Requested behavior tuning.
        self.angle_render_offset = 0.0
        self.turn_probability = 0.0
        self.force_straight_road_follow = True
        self.turn_slow_factor = 0.58
        self.turn_slow_time = 0.55
        self.lane_bias_max_deg = 10.0
        self.front_stop_dist = max(68.0, self.size * 0.50)
        self.front_slow_dist = max(145.0, self.size * 1.10)
        self._desired_heading_angle = 0.0
        self._junction_cooldown = 0.0
        self._turn_slow_timer = 0.0

        # Simple autopilot mode: planner is intentionally staggered so newly
        # spawned cars do not all compute routes on the same frame.
        self.simple_ai_mode = True
        self._plan_delay_remaining = self._rng.uniform(0.25, 1.35)
        self._path_replan_interval = self._rng.uniform(0.9, 1.7)
        self._path_replan_timer = 0.0
        self._path_steps_ahead = 26
        self._planned_path: List[WorldPoint] = []
        self._planned_path_index = 0
        self._lane_offset_ratio = 0.0
        self._corridor_heading: Optional[float] = None
        self._prefer_right_turn = (sum(ord(ch) for ch in self.ai_id) % 2) == 0
        self._debug_ai: Dict[str, Any] = {}
        self._simple_stuck_timer = 0.0
        self._simple_blocked_timer = 0.0

    def _pick_neighbor_tile(
        self,
        navigator: MapNavigator,
        origin: TilePoint,
        avoid_tile: Optional[TilePoint] = None,
    ) -> Optional[TilePoint]:
        neighbors = navigator.get_road_neighbors(origin)
        if not neighbors:
            return None
        if avoid_tile is not None and len(neighbors) > 1:
            filtered = [t for t in neighbors if t != avoid_tile]
            if filtered:
                neighbors = filtered
        return self._rng.choice(neighbors)

    def get_hitbox_rect(self) -> Tuple[float, float, float, float]:
        hit_size = max(2.0, self.size * self.hitbox_scale)
        offset = (self.size - hit_size) * 0.5
        return self.x + offset, self.y + offset, hit_size, hit_size

    def to_world_entity(self) -> Dict[str, Any]:
        desired_heading = self._nearest_cardinal_angle(self._desired_heading_angle or self.angle)
        payload = {
            "x": float(self.x),
            "y": float(self.y),
            "angle": float(_normalize_angle_deg(self.angle + self.angle_render_offset)),
            "car": [self.car[0], self.car[1]],
            "on_road": bool(self.on_road),
            "ai": True,
            "ai_kind": self.entity_type,
            "ai_state": self.ai_state,
            "debug_speed": float(self.speed),
            "debug_heading": float(desired_heading),
            "debug_ai": dict(self._debug_ai),
        }

        if self._corridor_heading is not None:
            payload["debug_corridor_heading"] = float(self._nearest_cardinal_angle(self._corridor_heading))

        if self._planned_path:
            idx = max(0, min(self._planned_path_index, len(self._planned_path) - 1))
            target = self._planned_path[idx]
            payload["debug_target"] = {"x": float(target[0]), "y": float(target[1])}
            payload["debug_path_index"] = int(idx)
            payload["debug_path_len"] = int(len(self._planned_path))
            payload["debug_path"] = [
                [float(pt[0]), float(pt[1])]
                for pt in self._planned_path[idx : idx + 8]
            ]
            return payload

        waypoint = self._current_waypoint()
        if waypoint is not None:
            payload["debug_target"] = {"x": float(waypoint[0]), "y": float(waypoint[1])}

        path_points: List[WorldPoint] = []
        if self.waypoints and self.waypoint_index >= 0:
            for wp in self.waypoints[self.waypoint_index : self.waypoint_index + 6]:
                path_points.append((float(wp[0]), float(wp[1])))
        elif self._dynamic_waypoint is not None:
            path_points.append((float(self._dynamic_waypoint[0]), float(self._dynamic_waypoint[1])))

        if path_points:
            payload["debug_path"] = [[pt[0], pt[1]] for pt in path_points]

        return payload

    def _current_waypoint(self) -> Optional[WorldPoint]:
        if self.waypoints and 0 <= self.waypoint_index < len(self.waypoints):
            return self.waypoints[self.waypoint_index]
        return self._dynamic_waypoint

    def _pick_next_waypoint(self, navigator: MapNavigator) -> Optional[WorldPoint]:
        if self.waypoints:
            if self.waypoint_index < 0:
                self.waypoint_index = 0
            else:
                nxt = self.waypoint_index + 1
                if nxt >= len(self.waypoints):
                    self.waypoint_index = 0 if self.loop_waypoints else len(self.waypoints) - 1
                else:
                    self.waypoint_index = nxt
            return self.waypoints[self.waypoint_index]

        center = (self.x + self.size * 0.5, self.y + self.size * 0.5)
        start_tile = navigator.world_to_tile(center[0], center[1])

        nxt_tile = self._pick_neighbor_tile(navigator, start_tile, avoid_tile=self._last_road_tile)
        if nxt_tile is None:
            nxt_tile = navigator.find_nearest_road_tile(start_tile, max_radius=8)
            if nxt_tile is None:
                self._dynamic_waypoint = None
                return None
            self._last_road_tile = start_tile
            self._dynamic_waypoint = navigator.tile_to_world(nxt_tile[0], nxt_tile[1], centered=True)
            return self._dynamic_waypoint

        # Project a few hops ahead so the waypoint is far enough to create movement.
        prev_tile = start_tile
        for _ in range(max(0, self.dynamic_waypoint_hops - 1)):
            hop = self._pick_neighbor_tile(navigator, nxt_tile, avoid_tile=prev_tile)
            if hop is None:
                break
            prev_tile, nxt_tile = nxt_tile, hop

        waypoint = navigator.tile_to_world(nxt_tile[0], nxt_tile[1], centered=True)
        if _distance(center, waypoint) < self.dynamic_min_distance:
            extra = self._pick_neighbor_tile(navigator, nxt_tile, avoid_tile=prev_tile)
            if extra is not None:
                nxt_tile = extra
                waypoint = navigator.tile_to_world(nxt_tile[0], nxt_tile[1], centered=True)

        self._last_road_tile = start_tile
        self._dynamic_waypoint = waypoint
        return self._dynamic_waypoint

    def _compute_arrive_speed(self, dist_to_target: float) -> float:
        if dist_to_target <= self.arrive_radius:
            return 0.0
        if dist_to_target >= self.slow_radius:
            return self.cruise_speed
        t = (dist_to_target - self.arrive_radius) / max(1.0, self.slow_radius - self.arrive_radius)
        return self.cruise_speed * _clamp(t, 0.0, 1.0)

    def _brake_for_blocker(self, obstacles: Iterable[RectLike]) -> float:
        look_ahead = max(self.size * 1.1, self.speed * 0.85)
        if look_ahead <= 0.0:
            return self.cruise_speed

        rad = math.radians(self.angle)
        fwd_x, fwd_y = math.cos(rad), math.sin(rad)
        side_x, side_y = -fwd_y, fwd_x

        my_center = (self.x + self.size * 0.5, self.y + self.size * 0.5)
        speed_cap = self.cruise_speed

        for obs in obstacles:
            comp = _rect_components(obs)
            if comp is None:
                continue
            ox, oy, ow, oh = comp
            obs_center = (ox + ow * 0.5, oy + oh * 0.5)
            rel_x = obs_center[0] - my_center[0]
            rel_y = obs_center[1] - my_center[1]

            ahead = rel_x * fwd_x + rel_y * fwd_y
            if ahead <= 0.0 or ahead > look_ahead:
                continue

            lateral = abs(rel_x * side_x + rel_y * side_y)
            lane_half = self.size * 0.35 + max(ow, oh) * 0.35
            if lateral > lane_half:
                continue

            ratio = _clamp(ahead / look_ahead, 0.0, 1.0)
            # Allow full stop when blocker is close in front.
            speed_cap = min(speed_cap, max(0.0, self.cruise_speed * ratio))

        return speed_cap

    def _avoid_obstacles(self, obstacles: Iterable[RectLike]) -> float:
        avoid_dist = max(self.size * 1.2, self.speed * 0.9)
        if avoid_dist <= 0.0:
            return 0.0

        rad = math.radians(self.angle)
        fwd_x, fwd_y = math.cos(rad), math.sin(rad)
        side_x, side_y = -fwd_y, fwd_x
        my_center = (self.x + self.size * 0.5, self.y + self.size * 0.5)

        steer = 0.0
        for obs in obstacles:
            comp = _rect_components(obs)
            if comp is None:
                continue
            ox, oy, ow, oh = comp
            obs_center = (ox + ow * 0.5, oy + oh * 0.5)
            rel_x = obs_center[0] - my_center[0]
            rel_y = obs_center[1] - my_center[1]

            ahead = rel_x * fwd_x + rel_y * fwd_y
            if ahead <= 0.0 or ahead > avoid_dist:
                continue

            lateral_signed = rel_x * side_x + rel_y * side_y
            lateral = abs(lateral_signed)
            lane_half = self.size * 0.45 + max(ow, oh) * 0.35
            if lateral > lane_half:
                continue

            weight = 1.0 - _clamp(ahead / avoid_dist, 0.0, 1.0)
            direction = -1.0 if lateral_signed > 0 else 1.0
            steer += direction * (34.0 * weight)

        return _clamp(steer, -38.0, 38.0)

    def _raycast_wall_distance(
        self,
        game_map: Any,
        origin: WorldPoint,
        angle_deg: float,
        max_dist: Optional[float] = None,
    ) -> float:
        max_d = float(max_dist if max_dist is not None else self.sensor_max_dist)
        step = max(1.0, float(self.sensor_step))

        has_road_check = hasattr(game_map, "is_road_at")
        has_collision_check = hasattr(game_map, "is_collision_at")
        if not has_road_check and not has_collision_check:
            return max_d

        rad = math.radians(angle_deg)
        dx = math.cos(rad)
        dy = math.sin(rad)

        dist = step
        while dist <= max_d:
            sx = origin[0] + dx * dist
            sy = origin[1] + dy * dist

            # Fast path: map road grid lookup is much cheaper than scanning all
            # collision rects for each ray step.
            if has_road_check:
                if not game_map.is_road_at(sx, sy):
                    return dist
            elif has_collision_check:
                if game_map.is_collision_at(sx, sy):
                    return dist

            dist += step

        return max_d

    def _nearest_cardinal_angle(self, angle_deg: float) -> float:
        idx = int(round(_normalize_angle_deg(angle_deg) / 90.0)) % 4
        return float(idx * 90)

    def _heading_step(self, heading_angle: float) -> TilePoint:
        idx = int(round(_normalize_angle_deg(heading_angle) / 90.0)) % 4
        dirs = ((1, 0), (0, 1), (-1, 0), (0, -1))
        return dirs[idx]

    def _open_headings_for_tile(self, navigator: MapNavigator, tile: TilePoint) -> List[float]:
        tx, ty = tile
        checks = [
            (1, 0, 0.0),
            (0, 1, 90.0),
            (-1, 0, 180.0),
            (0, -1, 270.0),
        ]
        out: List[float] = []
        for dx, dy, heading in checks:
            if navigator.is_road_tile(tx + dx, ty + dy):
                out.append(heading)
        return out

    def _constrain_heading_to_road(self, navigator: MapNavigator, tile: TilePoint, desired_angle: float) -> float:
        desired = self._nearest_cardinal_angle(desired_angle)
        open_headings = self._open_headings_for_tile(navigator, tile)
        if not open_headings:
            return desired

        for heading in open_headings:
            if abs(_shortest_angle_delta(desired, heading)) < 1e-3:
                self._corridor_heading = None
                return heading

        if len(open_headings) == 2 and abs(_shortest_angle_delta(open_headings[0], open_headings[1])) >= 179.0:
            if self._corridor_heading is not None:
                ref = self._nearest_cardinal_angle(self._corridor_heading)
            elif self.speed > 0.2:
                ref = self._nearest_cardinal_angle(self.angle)
            else:
                ref = desired

            forward = min(open_headings, key=lambda h: abs(_shortest_angle_delta(ref, h)))
            self._corridor_heading = forward
            return forward

        self._corridor_heading = None
        return min(open_headings, key=lambda h: abs(_shortest_angle_delta(desired, h)))

    def _is_path_target_passed(
        self,
        center: WorldPoint,
        path: Sequence[WorldPoint],
        target_index: int,
    ) -> bool:
        if target_index < 0 or target_index >= len(path) - 1:
            return False

        tx, ty = path[target_index]
        nx, ny = path[target_index + 1]
        seg_x = nx - tx
        seg_y = ny - ty
        seg_len_sq = seg_x * seg_x + seg_y * seg_y
        if seg_len_sq <= 1e-6:
            return False

        rel_x = center[0] - tx
        rel_y = center[1] - ty
        progress = rel_x * seg_x + rel_y * seg_y
        return progress > seg_len_sq * 0.08

    def _lane_offset(self, heading_angle: float, navigator: MapNavigator) -> WorldPoint:
        game_map = navigator.game_map
        lane_size = min(
            float(getattr(game_map, "tile_width", 32) or 32),
            float(getattr(game_map, "tile_height", 32) or 32),
        )
        offset = lane_size * self._lane_offset_ratio
        rad = math.radians(self._nearest_cardinal_angle(heading_angle) + 90.0)
        return math.cos(rad) * offset, math.sin(rad) * offset

    def _build_trace_path(self, navigator: MapNavigator, steps: int) -> List[WorldPoint]:
        center = (self.x + self.size * 0.5, self.y + self.size * 0.5)
        tile = navigator.world_to_tile(center[0], center[1])
        road_tile = navigator.find_nearest_road_tile(tile, max_radius=4)
        if road_tile is None:
            return []

        heading = self._nearest_cardinal_angle(self._desired_heading_angle or self.angle)
        heading = self._constrain_heading_to_road(navigator, road_tile, heading)
        cur = road_tile
        path: List[WorldPoint] = []

        for _ in range(max(4, int(steps))):
            heading = self._constrain_heading_to_road(navigator, cur, heading)
            forward_open = self._is_direction_open(navigator, cur, heading)
            right_open = self._is_direction_open(navigator, cur, heading + 90.0)
            left_open = self._is_direction_open(navigator, cur, heading - 90.0)

            if not forward_open:
                if right_open and left_open:
                    heading = _normalize_angle_deg(heading + (90.0 if self._prefer_right_turn else -90.0))
                elif right_open:
                    heading = _normalize_angle_deg(heading + 90.0)
                elif left_open:
                    heading = _normalize_angle_deg(heading - 90.0)
                else:
                    heading = _normalize_angle_deg(heading + 180.0)
            elif (not self.force_straight_road_follow) and (right_open or left_open):
                options = [0.0]
                if right_open:
                    options.append(90.0)
                if left_open:
                    options.append(-90.0)
                if self._rng.random() < self.turn_probability:
                    heading = _normalize_angle_deg(heading + self._rng.choice(options))

            step = self._heading_step(heading)
            nxt = (cur[0] + step[0], cur[1] + step[1])
            if not navigator.is_road_tile(nxt[0], nxt[1]):
                break

            base = navigator.tile_to_world(nxt[0], nxt[1], centered=True)
            ox, oy = self._lane_offset(heading, navigator)
            path.append((base[0] + ox, base[1] + oy))
            cur = nxt

        return path

    def _update_simple_autopilot(
        self,
        dt: float,
        game_map: Any,
        navigator: MapNavigator,
        obs: List[RectLike],
    ) -> None:
        self._debug_ai = {
            "mode": "simple",
            "phase": "planning",
            "simple_ai_mode": bool(self.simple_ai_mode),
            "force_straight": bool(self.force_straight_road_follow),
            "speed": float(self.speed),
            "path_len": int(len(self._planned_path)),
            "path_index": int(self._planned_path_index),
            "plan_delay": float(self._plan_delay_remaining),
            "replan_timer": float(self._path_replan_timer),
            "replan_interval": float(self._path_replan_interval),
            "corridor_heading": (
                float(self._nearest_cardinal_angle(self._corridor_heading))
                if self._corridor_heading is not None
                else None
            ),
            "stuck_timer": float(self._simple_stuck_timer),
            "blocked_timer": float(self._simple_blocked_timer),
        }

        if self._plan_delay_remaining > 0.0:
            self._plan_delay_remaining = max(0.0, self._plan_delay_remaining - dt)
            self.speed = max(0.0, self.speed - self.brake * dt)
            self.ai_state = "planning"
            self._debug_ai.update(
                {
                    "phase": "planning",
                    "speed": float(self.speed),
                    "desired_speed": 0.0,
                    "plan_delay": float(self._plan_delay_remaining),
                }
            )
            return

        self._path_replan_timer += dt
        needs_replan = (
            not self._planned_path
            or self._planned_path_index >= len(self._planned_path)
            or self._path_replan_timer >= self._path_replan_interval
        )
        self._debug_ai["needs_replan"] = bool(needs_replan)
        if needs_replan:
            self._planned_path = self._build_trace_path(navigator, self._path_steps_ahead)
            self._planned_path_index = 0
            self._path_replan_timer = 0.0
            self._debug_ai["phase"] = "replan"

        if not self._planned_path:
            self.speed = max(0.0, self.speed - self.brake * dt)
            self.ai_state = "idle"
            self._debug_ai.update(
                {
                    "phase": "idle",
                    "speed": float(self.speed),
                    "desired_speed": 0.0,
                    "path_len": 0,
                    "path_index": 0,
                }
            )
            return

        center = (self.x + self.size * 0.5, self.y + self.size * 0.5)

        tile = navigator.world_to_tile(center[0], center[1])
        road_tile = navigator.find_nearest_road_tile(tile, max_radius=3)
        open_headings: List[float] = []
        forward_open = False
        right_open = False
        left_open = False
        if road_tile is not None:
            heading = self._nearest_cardinal_angle(self._desired_heading_angle or self.angle)
            open_headings = self._open_headings_for_tile(navigator, road_tile)
            forward_open = self._is_direction_open(navigator, road_tile, heading)
            right_open = self._is_direction_open(navigator, road_tile, heading + 90.0)
            left_open = self._is_direction_open(navigator, road_tile, heading - 90.0)
            self._debug_ai.update(
                {
                    "road_tile": [int(road_tile[0]), int(road_tile[1])],
                    "open_headings": [float(h) for h in open_headings],
                    "base_heading": float(heading),
                    "forward_open": bool(forward_open),
                    "right_open": bool(right_open),
                    "left_open": bool(left_open),
                }
            )
            if not forward_open and not right_open and not left_open:
                self._desired_heading_angle = _normalize_angle_deg(heading + 180.0)
                self._planned_path = self._build_trace_path(navigator, self._path_steps_ahead)
                self._planned_path_index = 0
        else:
            self._debug_ai.update(
                {
                    "road_tile": None,
                    "open_headings": [],
                    "base_heading": float(self._nearest_cardinal_angle(self._desired_heading_angle or self.angle)),
                    "forward_open": False,
                    "right_open": False,
                    "left_open": False,
                }
            )

        idx = max(0, min(self._planned_path_index, len(self._planned_path) - 1))
        reach_dist = max(24.0, self.arrive_radius * 1.6)
        advance_guard = 0
        while idx < len(self._planned_path) - 1 and advance_guard < 8:
            target = self._planned_path[idx]
            dist = _distance(center, target)
            if dist <= reach_dist or self._is_path_target_passed(center, self._planned_path, idx):
                idx += 1
                advance_guard += 1
                continue
            break

        self._planned_path_index = idx
        target = self._planned_path[idx]
        dist = _distance(center, target)

        to_x = target[0] - center[0]
        to_y = target[1] - center[1]
        target_angle = math.degrees(math.atan2(to_y, to_x)) if dist > 0.001 else self.angle
        self._desired_heading_angle = self._nearest_cardinal_angle(target_angle)

        desired_angle = self._nearest_cardinal_angle(target_angle)
        if road_tile is not None:
            desired_angle = self._constrain_heading_to_road(navigator, road_tile, desired_angle)

        front_wall = self._raycast_wall_distance(game_map, center, desired_angle)
        blocker_d = self._front_blocker_distance(obs)

        desired_speed = self.cruise_speed
        if front_wall <= self.front_block_dist:
            desired_speed = min(desired_speed, self.cruise_speed * 0.30)
        elif front_wall < self.front_slow_dist:
            ratio = (front_wall - self.front_block_dist) / max(1.0, self.front_slow_dist - self.front_block_dist)
            desired_speed = min(desired_speed, self.cruise_speed * _clamp(ratio, 0.30, 1.0))

        if blocker_d <= self.front_stop_dist:
            desired_speed = 0.0
        elif blocker_d < self.front_slow_dist:
            ratio = (blocker_d - self.front_stop_dist) / max(1.0, self.front_slow_dist - self.front_stop_dist)
            desired_speed = min(desired_speed, self.cruise_speed * _clamp(ratio, 0.0, 1.0))

        turn_error = abs(_shortest_angle_delta(self.angle, desired_angle))
        if turn_error > 26.0:
            desired_speed = min(desired_speed, self.cruise_speed * 0.40)
        elif turn_error > 14.0:
            desired_speed = min(desired_speed, self.cruise_speed * 0.58)

        self._apply_player_like_turning(desired_angle, dt)

        if self.speed < desired_speed:
            self.speed = min(desired_speed, self.speed + self.accel * dt)
        else:
            self.speed = max(desired_speed, self.speed - self.brake * dt)

        pre_move_center = center
        rad = math.radians(self.angle)
        move_dx = math.cos(rad) * self.speed * dt
        move_dy = math.sin(rad) * self.speed * dt
        collided = self._move_with_collision_guard(game_map, move_dx, move_dy)

        self._enforce_world_bounds(game_map)
        self._resolve_map_collisions(game_map)
        self._resolve_dynamic_collisions(obs)
        self._enforce_world_bounds(game_map)
        self._enforce_road_constraint(game_map, navigator, dt)

        post_center = (self.x + self.size * 0.5, self.y + self.size * 0.5)
        move_progress = _distance(pre_move_center, post_center)
        move_expected = max(0.8, desired_speed * dt * 0.2)

        if desired_speed > 5.0 and (collided or move_progress <= move_expected):
            self._simple_stuck_timer += dt
        else:
            self._simple_stuck_timer = 0.0

        blocked_now = front_wall <= max(16.0, self.front_block_dist * 0.45)
        if blocked_now:
            self._simple_blocked_timer += dt
        else:
            self._simple_blocked_timer = 0.0

        recovery_triggered = self._simple_stuck_timer >= 0.75 or self._simple_blocked_timer >= 0.75
        recovery_heading: Optional[float] = None
        if recovery_triggered:
            if road_tile is not None:
                open_for_recovery = self._open_headings_for_tile(navigator, road_tile)
                if open_for_recovery:
                    ref_heading = self._nearest_cardinal_angle(self._desired_heading_angle or self.angle)
                    ray_limit = max(self.sensor_max_dist, self.front_slow_dist * 1.2)
                    scored: List[Tuple[float, float]] = []
                    for heading in open_for_recovery:
                        ray = self._raycast_wall_distance(game_map, post_center, heading, max_dist=ray_limit)
                        delta = abs(_shortest_angle_delta(ref_heading, heading))
                        straight_bonus = 8.0 if delta < 1e-3 else 0.0
                        score = float(ray + straight_bonus - 0.15 * delta)
                        scored.append((score, heading))

                    if scored:
                        scored.sort(key=lambda item: item[0], reverse=True)
                        recovery_heading = self._nearest_cardinal_angle(scored[0][1])
                        self._desired_heading_angle = recovery_heading
                        self._corridor_heading = recovery_heading

            self._planned_path = self._build_trace_path(navigator, self._path_steps_ahead)
            self._planned_path_index = 0
            self._path_replan_timer = 0.0
            self.speed = min(self.speed, self.cruise_speed * 0.45)
            self._simple_stuck_timer = 0.0
            self._simple_blocked_timer = 0.0

        if self.speed <= 0.8 and desired_speed <= 0.1:
            self.ai_state = "stopped"
        elif self.speed > 1.0:
            self.ai_state = "driving"
        else:
            self.ai_state = "idle"

        blocker_debug = None if math.isinf(blocker_d) else float(blocker_d)
        self._debug_ai.update(
            {
                "phase": "drive",
                "speed": float(self.speed),
                "desired_speed": float(desired_speed),
                "target_point": [float(target[0]), float(target[1])],
                "distance_to_target": float(dist),
                "target_angle": float(target_angle),
                "desired_angle": float(desired_angle),
                "desired_heading": float(self._desired_heading_angle),
                "turn_error": float(turn_error),
                "front_wall": float(front_wall),
                "front_blocker": blocker_debug,
                "path_len": int(len(self._planned_path)),
                "path_index": int(self._planned_path_index),
                "move_progress": float(move_progress),
                "move_expected": float(move_expected),
                "collided_step": bool(collided),
                "stuck_timer": float(self._simple_stuck_timer),
                "blocked_timer": float(self._simple_blocked_timer),
                "recovery": bool(recovery_triggered),
                "recovery_heading": (
                    float(recovery_heading)
                    if isinstance(recovery_heading, (int, float))
                    else None
                ),
                "state": str(self.ai_state),
            }
        )

    def _is_direction_open(self, navigator: MapNavigator, tile: TilePoint, heading_angle: float) -> bool:
        idx = int(round(_normalize_angle_deg(heading_angle) / 90.0)) % 4
        dirs = ((1, 0), (0, 1), (-1, 0), (0, -1))
        dx, dy = dirs[idx]
        return navigator.is_road_tile(tile[0] + dx, tile[1] + dy)

    def _front_blocker_distance(self, obstacles: Iterable[RectLike]) -> float:
        look_ahead = max(self.front_slow_dist, self.speed * 1.25 + self.front_stop_dist)
        if look_ahead <= 0.0:
            return float("inf")

        rad = math.radians(self.angle)
        fwd_x, fwd_y = math.cos(rad), math.sin(rad)
        side_x, side_y = -fwd_y, fwd_x
        my_center = (self.x + self.size * 0.5, self.y + self.size * 0.5)

        nearest = float("inf")
        for obs in obstacles:
            comp = _rect_components(obs)
            if comp is None:
                continue

            ox, oy, ow, oh = comp
            obs_center = (ox + ow * 0.5, oy + oh * 0.5)
            rel_x = obs_center[0] - my_center[0]
            rel_y = obs_center[1] - my_center[1]

            ahead = rel_x * fwd_x + rel_y * fwd_y
            if ahead <= 0.0 or ahead > look_ahead:
                continue

            lateral = abs(rel_x * side_x + rel_y * side_y)
            lane_half = self.size * 0.32 + max(ow, oh) * 0.33
            if lateral > lane_half:
                continue

            nearest = min(nearest, max(0.0, ahead - max(ow, oh) * 0.2))

        return nearest

    def _resolve_overlap_with_rect(self, rect: RectLike, speed_loss: float = 0.45) -> bool:
        me = _rect_components(self.get_hitbox_rect())
        other = _rect_components(rect)
        if me is None or other is None:
            return False

        mx, my, mw, mh = me
        ox, oy, ow, oh = other

        overlap_w = min(mx + mw, ox + ow) - max(mx, ox)
        overlap_h = min(my + mh, oy + oh) - max(my, oy)
        if overlap_w <= 0.0 or overlap_h <= 0.0:
            return False

        if overlap_w < overlap_h:
            if mx + mw * 0.5 < ox + ow * 0.5:
                self.x -= overlap_w
            else:
                self.x += overlap_w
        else:
            if my + mh * 0.5 < oy + oh * 0.5:
                self.y -= overlap_h
            else:
                self.y += overlap_h

        self.speed *= _clamp(speed_loss, 0.0, 1.0)
        if self.speed < 0.5:
            self.speed = 0.0
        return True

    def _resolve_map_collisions(self, game_map: Any) -> None:
        if hasattr(game_map, "check_rect_collision"):
            collisions = game_map.check_rect_collision(self.get_hitbox_rect())
            if not collisions:
                return
            for rect in collisions:
                self._resolve_overlap_with_rect(rect, speed_loss=0.42)
            return

        collision_rects = getattr(game_map, "collision_rects", None)
        if not collision_rects:
            return
        for rect in collision_rects:
            self._resolve_overlap_with_rect(rect, speed_loss=0.42)

    def _has_map_collision(self, game_map: Any) -> bool:
        if hasattr(game_map, "check_collision"):
            try:
                return bool(game_map.check_collision(self.get_hitbox_rect()))
            except Exception:
                pass
        if hasattr(game_map, "check_rect_collision"):
            try:
                return bool(game_map.check_rect_collision(self.get_hitbox_rect()))
            except Exception:
                pass
        return False

    def _move_with_collision_guard(self, game_map: Any, dx: float, dy: float, max_step: float = 8.0) -> bool:
        """Moves in small sub-steps so fast frames cannot tunnel through collision tiles."""
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return False

        step_limit = max(1.0, float(max_step))
        steps = max(1, int(math.ceil(max(abs(dx), abs(dy)) / step_limit)))
        step_x = dx / steps
        step_y = dy / steps

        collided = False
        for _ in range(steps):
            if abs(step_x) > 1e-6:
                self.x += step_x
                if self._has_map_collision(game_map):
                    self.x -= step_x
                    collided = True

            if abs(step_y) > 1e-6:
                self.y += step_y
                if self._has_map_collision(game_map):
                    self.y -= step_y
                    collided = True

            if collided:
                self.speed *= 0.55
                break

        return collided

    def _resolve_dynamic_collisions(self, obstacles: Iterable[RectLike]) -> None:
        for rect in obstacles:
            self._resolve_overlap_with_rect(rect, speed_loss=0.33)

    def _apply_player_like_turning(self, desired_angle: float, dt: float) -> None:
        # Keep AI turn response stable at AI speed scales; still slower at top speed.
        speed_ratio = min(1.0, max(0.0, self.speed) / max(1.0, self.max_speed))
        steer_factor = 1.0 / (1.0 + 2.2 * speed_ratio)
        low_speed_ref = max(24.0, self.max_speed * 0.35)
        low_speed_limit = min(1.0, max(0.0, self.speed) / low_speed_ref)
        steer_factor *= max(0.35, low_speed_limit)

        delta = _shortest_angle_delta(self.angle, desired_angle)
        max_turn = self.turn_speed * steer_factor * dt
        self.angle = _normalize_angle_deg(self.angle + _clamp(delta, -max_turn, max_turn))

    def _enforce_world_bounds(self, game_map: Any) -> None:
        world_w = float(getattr(game_map, "width_px", 0.0))
        world_h = float(getattr(game_map, "height_px", 0.0))
        if world_w > 0.0:
            self.x = _clamp(self.x, 0.0, max(0.0, world_w - self.size))
        if world_h > 0.0:
            self.y = _clamp(self.y, 0.0, max(0.0, world_h - self.size))

    def _enforce_road_constraint(self, game_map: Any, navigator: MapNavigator, dt: float) -> None:
        if not hasattr(game_map, "is_road_at"):
            self.on_road = True
            return

        cx = self.x + self.size * 0.5
        cy = self.y + self.size * 0.5
        probe = self.size * 0.18
        probes = (
            (cx, cy),
            (cx + probe, cy),
            (cx - probe, cy),
            (cx, cy + probe),
            (cx, cy - probe),
        )
        on_road = any(bool(game_map.is_road_at(px, py)) for px, py in probes)
        self.on_road = on_road
        if on_road:
            return

        tile = navigator.world_to_tile(cx, cy)
        nearest = navigator.find_nearest_road_tile(tile, max_radius=8)
        if nearest is None:
            self.speed *= 0.7
            return

        road_cx, road_cy = navigator.tile_to_world(nearest[0], nearest[1], centered=True)
        to_x = road_cx - cx
        to_y = road_cy - cy
        dist = math.hypot(to_x, to_y)
        if dist <= 1e-3:
            self.speed *= 0.8
            return

        recover_speed = min(self.max_speed * 0.42, max(40.0, self.cruise_speed * 0.30))
        step = min(dist, recover_speed * dt)
        move_dx = (to_x / dist) * step
        move_dy = (to_y / dist) * step
        self._move_with_collision_guard(game_map, move_dx, move_dy, max_step=6.0)
        self.speed = min(self.speed, recover_speed)

    def _update_motion_towards(
        self,
        target: Optional[WorldPoint],
        desired_speed: float,
        dt: float,
        game_map: Any,
        navigator: MapNavigator,
        obstacles: Iterable[RectLike],
    ) -> None:
        desired_speed = _clamp(desired_speed, 0.0, self.max_speed)

        if target is None:
            self.speed = max(0.0, self.speed - self.brake * dt)
            self.ai_state = "idle" if self.speed < 1.0 else "coasting"
            self._debug_ai = {
                "mode": "motion",
                "phase": "idle",
                "speed": float(self.speed),
                "desired_speed": float(desired_speed),
                "target_point": None,
                "state": str(self.ai_state),
            }
            return

        cx = self.x + self.size * 0.5
        cy = self.y + self.size * 0.5
        to_x = target[0] - cx
        to_y = target[1] - cy
        dist = math.hypot(to_x, to_y)

        if dist > 0.001:
            desired_angle = math.degrees(math.atan2(to_y, to_x))
        else:
            desired_angle = self.angle

        desired_angle += self._avoid_obstacles(obstacles)

        delta = _shortest_angle_delta(self.angle, desired_angle)
        max_turn = self.turn_speed * dt
        self.angle = _normalize_angle_deg(self.angle + _clamp(delta, -max_turn, max_turn))

        speed_cap = self._brake_for_blocker(obstacles)
        desired_speed = min(desired_speed, speed_cap)

        turn_error = abs(_shortest_angle_delta(self.angle, desired_angle))
        if turn_error > 28.0:
            desired_speed = min(desired_speed, self.cruise_speed * 0.45)
        elif turn_error > 16.0:
            desired_speed = min(desired_speed, self.cruise_speed * 0.62)

        if self.speed < desired_speed:
            self.speed = min(desired_speed, self.speed + self.accel * dt)
        else:
            self.speed = max(desired_speed, self.speed - self.brake * dt)

        rad = math.radians(self.angle)
        move_dx = math.cos(rad) * self.speed * dt
        move_dy = math.sin(rad) * self.speed * dt
        self._move_with_collision_guard(game_map, move_dx, move_dy)

        self._enforce_world_bounds(game_map)
        self._enforce_road_constraint(game_map, navigator, dt)

        if self.speed < 8.0 and (desired_speed > 20.0 or target is not None):
            self._stuck_timer += dt
            if self._stuck_timer > 1.2:
                self._pick_next_waypoint(navigator)
                self._stuck_timer = 0.0
        else:
            self._stuck_timer = 0.0

        self.ai_state = "driving" if self.speed > 1.0 else "idle"

        self._debug_ai = {
            "mode": "motion",
            "phase": "drive",
            "speed": float(self.speed),
            "desired_speed": float(desired_speed),
            "target_point": [float(target[0]), float(target[1])],
            "distance_to_target": float(dist),
            "desired_angle": float(desired_angle),
            "turn_error": float(turn_error),
            "state": str(self.ai_state),
        }

    def update(
        self,
        dt: float,
        game_map: Any,
        obstacles: Optional[Iterable[RectLike]] = None,
        navigator: Optional[MapNavigator] = None,
    ) -> None:
        if dt <= 0.0:
            return

        if navigator is None:
            navigator = MapNavigator(game_map)

        obs = list(obstacles or [])

        if self.simple_ai_mode:
            self._update_simple_autopilot(dt, game_map, navigator, obs)
            return

        if self._junction_cooldown > 0.0:
            self._junction_cooldown = max(0.0, self._junction_cooldown - dt)
        if self._turn_slow_timer > 0.0:
            self._turn_slow_timer = max(0.0, self._turn_slow_timer - dt)

        center = (self.x + self.size * 0.5, self.y + self.size * 0.5)
        tile = navigator.world_to_tile(center[0], center[1])
        road_tile = navigator.find_nearest_road_tile(tile, max_radius=3)
        if road_tile is None:
            road_tile = tile

        # Keep heading goals on cardinal axes only: 0/90/180/270.
        if abs(_shortest_angle_delta(self._desired_heading_angle, self.angle)) > 120.0:
            self._desired_heading_angle = self._nearest_cardinal_angle(self.angle)

        base_heading = self._nearest_cardinal_angle(self._desired_heading_angle)
        forward_open = self._is_direction_open(navigator, road_tile, base_heading)
        right_open = self._is_direction_open(navigator, road_tile, base_heading + 90.0)
        left_open = self._is_direction_open(navigator, road_tile, base_heading - 90.0)
        open_headings = self._open_headings_for_tile(navigator, road_tile)

        do_turn = False
        turn_delta = 0.0

        # Required behavior: if front is blocked, pick an available side turn.
        if not forward_open:
            if right_open and left_open:
                turn_delta = 90.0 if self._rng.random() < 0.5 else -90.0
                do_turn = True
            elif right_open:
                turn_delta = 90.0
                do_turn = True
            elif left_open:
                turn_delta = -90.0
                do_turn = True
        elif self._junction_cooldown <= 0.0 and not self.force_straight_road_follow:
            # Required behavior: 50% chance to turn only on one-sided branches.
            if right_open and not left_open and self._rng.random() < self.turn_probability:
                turn_delta = 90.0
                do_turn = True
            elif left_open and not right_open and self._rng.random() < self.turn_probability:
                turn_delta = -90.0
                do_turn = True

        if do_turn:
            self._desired_heading_angle = _normalize_angle_deg(base_heading + turn_delta)
            self._junction_cooldown = 0.60
            self._turn_slow_timer = self.turn_slow_time
        else:
            self._desired_heading_angle = base_heading

        target_heading = self._nearest_cardinal_angle(self._desired_heading_angle)
        front_d = self._raycast_wall_distance(game_map, center, target_heading)
        left_d = self._raycast_wall_distance(game_map, center, target_heading - 90.0)
        right_d = self._raycast_wall_distance(game_map, center, target_heading + 90.0)

        desired_angle = target_heading
        self._apply_player_like_turning(desired_angle, dt)

        desired_speed = self.cruise_speed

        if self._turn_slow_timer > 0.0:
            desired_speed = min(desired_speed, self.cruise_speed * self.turn_slow_factor)

        if abs(_shortest_angle_delta(self.angle, target_heading)) > 22.0:
            desired_speed = min(desired_speed, self.cruise_speed * self.turn_slow_factor)

        if front_d <= self.front_block_dist:
            desired_speed = min(desired_speed, self.cruise_speed * 0.30)
        elif front_d <= self.front_slow_dist:
            ratio = (front_d - self.front_block_dist) / max(1.0, self.front_slow_dist - self.front_block_dist)
            desired_speed = min(desired_speed, self.cruise_speed * _clamp(ratio, 0.30, 1.0))

        blocker_d = self._front_blocker_distance(obs)
        if blocker_d <= self.front_stop_dist:
            desired_speed = 0.0
        elif blocker_d < self.front_slow_dist:
            ratio = (blocker_d - self.front_stop_dist) / max(1.0, self.front_slow_dist - self.front_stop_dist)
            desired_speed = min(desired_speed, self.cruise_speed * _clamp(ratio, 0.0, 1.0))

        if not forward_open and not right_open and not left_open:
            desired_speed = 0.0

        desired_speed = _clamp(desired_speed, 0.0, self.max_speed)

        if self.speed < desired_speed:
            self.speed = min(desired_speed, self.speed + self.accel * dt)
        else:
            self.speed = max(desired_speed, self.speed - self.brake * dt)

        rad = math.radians(self.angle)
        move_dx = math.cos(rad) * self.speed * dt
        move_dy = math.sin(rad) * self.speed * dt
        self._move_with_collision_guard(game_map, move_dx, move_dy)

        self._enforce_world_bounds(game_map)
        self._resolve_map_collisions(game_map)
        self._resolve_dynamic_collisions(obs)
        self._enforce_world_bounds(game_map)
        self._enforce_road_constraint(game_map, navigator, dt)

        if self.speed < 2.0 and desired_speed > 8.0:
            self._stuck_timer += dt
            if self._stuck_timer > 1.3:
                escape_turn = 90.0 if right_d >= left_d else -90.0
                self._desired_heading_angle = _normalize_angle_deg(target_heading + escape_turn)
                self._junction_cooldown = 0.55
                self._turn_slow_timer = self.turn_slow_time
                self._stuck_timer = 0.0
        else:
            self._stuck_timer = 0.0

        blocker_debug = None if math.isinf(blocker_d) else float(blocker_d)
        self._debug_ai = {
            "mode": "classic",
            "phase": "drive",
            "force_straight": bool(self.force_straight_road_follow),
            "speed": float(self.speed),
            "desired_speed": float(desired_speed),
            "base_heading": float(base_heading),
            "desired_heading": float(self._desired_heading_angle),
            "desired_angle": float(desired_angle),
            "target_heading": float(target_heading),
            "road_tile": [int(road_tile[0]), int(road_tile[1])] if road_tile is not None else None,
            "open_headings": [float(h) for h in open_headings],
            "forward_open": bool(forward_open),
            "right_open": bool(right_open),
            "left_open": bool(left_open),
            "front_wall": float(front_d),
            "left_wall": float(left_d),
            "right_wall": float(right_d),
            "front_blocker": blocker_debug,
            "turn_error": float(abs(_shortest_angle_delta(self.angle, target_heading))),
            "junction_cooldown": float(self._junction_cooldown),
            "state": str(self.ai_state),
        }

        if self.speed <= 0.8 and desired_speed <= 0.1:
            self.ai_state = "stopped"
        elif self.speed > 1.0:
            self.ai_state = "driving"
        else:
            self.ai_state = "idle"

        self._debug_ai["state"] = str(self.ai_state)


# ---------------------------------------------------------------------------
# Pursuit AI (enemy / police) - prepared for future mission integration
# ---------------------------------------------------------------------------


class PursuitAI(TrafficAI):
    """
    Pursuit AI with long-term A* + local steering.

    This class is mission-ready, but intentionally generic for now:
    - can be armed/disarmed by future MissionSystem events
    - has alert state machine (idle/suspicious/chase/lost)
    - can ram when close, with cooldown
    """

    IDLE = "idle"
    SUSPICIOUS = "suspicious"
    CHASE = "chase"
    LOST = "lost"

    def __init__(
        self,
        ai_id: str,
        spawn_pos: WorldPoint,
        car: Tuple[str, str] = ("SEDAN", "Blue"),
        patrol_waypoints: Optional[Sequence[WorldPoint]] = None,
        enabled: bool = False,
        rng: Optional[random.Random] = None,
    ):
        super().__init__(
            ai_id=ai_id,
            spawn_pos=spawn_pos,
            car=car,
            waypoints=patrol_waypoints,
            loop_waypoints=True,
            max_speed=540.0,
            cruise_speed=350.0,
            accel=250.0,
            brake=420.0,
            turn_speed=220.0,
            rng=rng,
        )
        self.entity_type = "pursuit"

        self.enabled = enabled
        self.state = self.IDLE
        self.alert_level = self.IDLE

        self.target: Any = None

        self._path: List[WorldPoint] = []
        self._path_index = 0
        self._path_recompute_interval = 0.8
        self._path_recompute_timer = 0.0

        self._lost_timer = 0.0
        self._lost_timeout = 5.0
        self._drop_distance = 2600.0

        self.ram_distance = 210.0
        self.ram_speed_bonus = 135.0
        self._ram_cooldown = 1.0
        self._ram_cooldown_left = 0.0

        # Future mission-system integration data.
        self.mission_context: Dict[str, Any] = {}

    def set_target(self, player_like: Any) -> None:
        self.target = player_like

    def bind_mission_context(self, context: Optional[Dict[str, Any]]) -> None:
        self.mission_context = dict(context or {})

    def arm_for_mission(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def to_world_entity(self) -> Dict[str, Any]:
        payload = super().to_world_entity()
        debug_ai = payload.get("debug_ai")
        if not isinstance(debug_ai, dict):
            debug_ai = {}
            payload["debug_ai"] = debug_ai

        debug_ai.update(
            {
                "pursuit_state": str(self.state),
                "alert_level": str(self.alert_level),
                "path_index": int(self._path_index),
                "path_len": int(len(self._path)),
                "ram_cooldown": float(self._ram_cooldown_left),
                "enabled": bool(self.enabled),
            }
        )

        target_pos = self._target_position()
        if target_pos is not None:
            payload["debug_target"] = {"x": float(target_pos[0]), "y": float(target_pos[1])}
            center = (self.x + self.size * 0.5, self.y + self.size * 0.5)
            debug_ai["target_distance"] = float(_distance(center, target_pos))
        if self._path:
            payload["debug_path"] = [[float(pt[0]), float(pt[1])] for pt in self._path[:6]]
            payload["debug_path_index"] = int(self._path_index)
            idx = min(self._path_index, len(self._path) - 1)
            waypoint = self._path[idx]
            payload["debug_waypoint"] = {"x": float(waypoint[0]), "y": float(waypoint[1])}
        return payload

    def on_alert(self, level: str) -> None:
        lvl = (level or "").lower()
        if lvl in {"chase", "high", "critical"}:
            self.alert_level = self.CHASE
            self.state = self.CHASE
        elif lvl in {"suspicious", "medium", "warn"}:
            self.alert_level = self.SUSPICIOUS
            if self.state == self.IDLE:
                self.state = self.SUSPICIOUS
        else:
            self.alert_level = self.IDLE
            if self.state != self.CHASE:
                self.state = self.IDLE

    def can_drop_target(self, target_pos: Optional[WorldPoint] = None) -> bool:
        if target_pos is None:
            return True
        center = (self.x + self.size * 0.5, self.y + self.size * 0.5)
        if _distance(center, target_pos) > self._drop_distance:
            return True
        if self._lost_timer >= self._lost_timeout:
            return True
        return False

    def _target_position(self) -> Optional[WorldPoint]:
        tgt = self.target
        if tgt is None:
            return None

        if callable(tgt):
            out = tgt()
            if isinstance(out, (tuple, list)) and len(out) >= 2:
                return float(out[0]), float(out[1])
            return None

        if isinstance(tgt, dict) and "x" in tgt and "y" in tgt:
            x = float(tgt["x"])
            y = float(tgt["y"])
            size = float(tgt.get("size", 0.0))
            return x + size * 0.5, y + size * 0.5

        if hasattr(tgt, "x") and hasattr(tgt, "y"):
            x = float(tgt.x)
            y = float(tgt.y)
            size = float(getattr(tgt, "size", 0.0))
            return x + size * 0.5, y + size * 0.5

        return None

    def _recompute_path(self, game_map: Any, navigator: Optional[MapNavigator] = None) -> None:
        if navigator is None:
            navigator = MapNavigator(game_map)

        target_pos = self._target_position()
        if target_pos is None:
            self._path = []
            self._path_index = 0
            return

        start = (self.x + self.size * 0.5, self.y + self.size * 0.5)
        path = navigator.find_road_path(start, target_pos, heuristic="euclidean")
        if not path:
            # Fallback to direct steering if A* fails.
            path = [target_pos]

        self._path = path
        self._path_index = 0

    def _steer_to_waypoint(self) -> Optional[WorldPoint]:
        if not self._path:
            return None

        idx = min(self._path_index, len(self._path) - 1)
        wp = self._path[idx]

        center = (self.x + self.size * 0.5, self.y + self.size * 0.5)
        if _distance(center, wp) <= self.arrive_radius and self._path_index < len(self._path) - 1:
            self._path_index += 1
            wp = self._path[self._path_index]

        return wp

    def _ram_if_close(self, target_pos: Optional[WorldPoint]) -> float:
        if target_pos is None:
            return 0.0
        if self._ram_cooldown_left > 0.0:
            return 0.0

        center = (self.x + self.size * 0.5, self.y + self.size * 0.5)
        if _distance(center, target_pos) <= self.ram_distance:
            self._ram_cooldown_left = self._ram_cooldown
            return self.ram_speed_bonus

        return 0.0

    def _avoid_obstacles(self, obstacles: Iterable[RectLike]) -> float:
        # Slightly more aggressive than traffic cars.
        return super()._avoid_obstacles(obstacles) * 1.25

    def update(
        self,
        dt: float,
        game_map: Any,
        obstacles: Optional[Iterable[RectLike]] = None,
        navigator: Optional[MapNavigator] = None,
        target: Any = None,
    ) -> None:
        if dt <= 0.0:
            return

        if navigator is None:
            navigator = MapNavigator(game_map)
        obs = list(obstacles or [])

        if target is not None:
            self.set_target(target)

        if self._ram_cooldown_left > 0.0:
            self._ram_cooldown_left = max(0.0, self._ram_cooldown_left - dt)

        target_pos = self._target_position()

        # Keep pursuit enemy dormant until mission system enables it.
        if not self.enabled:
            self.state = self.IDLE
            if self.waypoints:
                wp = self._current_waypoint() or self._pick_next_waypoint(navigator)
                if wp is not None:
                    center = (self.x + self.size * 0.5, self.y + self.size * 0.5)
                    dist = _distance(center, wp)
                    if dist <= self.arrive_radius:
                        wp = self._pick_next_waypoint(navigator)
                        dist = _distance(center, wp) if wp else 0.0
                    desired = min(self.cruise_speed, self.max_speed * 0.55)
                    if wp is not None:
                        desired = min(desired, self._compute_arrive_speed(dist))
                    self._update_motion_towards(wp, desired, dt, game_map, navigator, obs)
                    self.ai_state = "patrol"
                    return

            self._update_motion_towards(None, 0.0, dt, game_map, navigator, obs)
            self.ai_state = "standby"
            return

        # Active behavior
        if target_pos is None:
            self.state = self.LOST if self.state == self.CHASE else self.IDLE

        if self.state in {self.SUSPICIOUS, self.CHASE, self.LOST} and target_pos is not None:
            self._path_recompute_timer += dt
            if self._path_recompute_timer >= self._path_recompute_interval or not self._path:
                self._path_recompute_timer = 0.0
                self._recompute_path(game_map, navigator)

        if self.alert_level == self.CHASE and target_pos is not None:
            self.state = self.CHASE

        wp = None
        desired_speed = 0.0

        if self.state == self.CHASE and target_pos is not None:
            wp = self._steer_to_waypoint() or target_pos
            desired_speed = min(self.max_speed, self.cruise_speed * 1.15 + self._ram_if_close(target_pos))
            self._lost_timer = 0.0
        elif self.state == self.SUSPICIOUS and target_pos is not None:
            wp = self._steer_to_waypoint() or target_pos
            desired_speed = min(self.max_speed, self.cruise_speed)
            self._lost_timer = 0.0
        elif self.state == self.LOST:
            wp = self._steer_to_waypoint()
            desired_speed = min(self.max_speed * 0.8, self.cruise_speed * 0.75)
            self._lost_timer += dt
            if self.can_drop_target(target_pos):
                self.state = self.IDLE
                self._path = []
                self._path_index = 0
        else:
            # Idle with optional patrol route.
            wp = self._current_waypoint()
            if wp is None:
                wp = self._pick_next_waypoint(navigator)
            if wp is not None:
                center = (self.x + self.size * 0.5, self.y + self.size * 0.5)
                dist = _distance(center, wp)
                if dist <= self.arrive_radius:
                    wp = self._pick_next_waypoint(navigator)
                    dist = _distance(center, wp) if wp else 0.0
                desired_speed = min(self.cruise_speed * 0.55, self._compute_arrive_speed(dist))

        self._update_motion_towards(wp, desired_speed, dt, game_map, navigator, obs)
        self.ai_state = self.state


class RobberAI(PursuitAI):
    """Aggressive pursuit car used by risky delivery missions."""

    def __init__(
        self,
        ai_id: str,
        spawn_pos: WorldPoint,
        car: Tuple[str, str] = ("MUSCLECAR", "Black"),
        enabled: bool = True,
        rng: Optional[random.Random] = None,
    ):
        super().__init__(
            ai_id=ai_id,
            spawn_pos=spawn_pos,
            car=car,
            patrol_waypoints=None,
            enabled=enabled,
            rng=rng,
        )
        self.entity_type = "robber"
        self.max_speed = 620.0
        self.cruise_speed = 430.0
        self.accel = 290.0
        self.brake = 440.0
        self.turn_speed = 230.0
        self.arrive_radius = 24.0
        self.slow_radius = 300.0
        self._path_recompute_interval = 0.55
        self._drop_distance = 4600.0
        self.ram_distance = 240.0
        self.ram_speed_bonus = 170.0

    def update(
        self,
        dt: float,
        game_map: Any,
        obstacles: Optional[Iterable[RectLike]] = None,
        navigator: Optional[MapNavigator] = None,
        target: Any = None,
    ) -> None:
        """Path-driven chase that can route around blockers while staying aggressive."""
        if dt <= 0.0:
            return

        obs = list(obstacles or [])

        if target is not None:
            self.set_target(target)
        if navigator is None:
            navigator = MapNavigator(game_map)

        target_pos = self._target_position()
        if target_pos is None:
            self._path = []
            self._path_index = 0
            self._update_motion_towards(None, 0.0, dt, game_map, navigator, obs)
            self.ai_state = "idle"
            return

        self.enabled = True
        self.alert_level = self.CHASE
        self.state = self.CHASE

        self._path_recompute_timer += dt
        if self._path_recompute_timer >= self._path_recompute_interval or not self._path:
            self._path_recompute_timer = 0.0
            self._recompute_path(game_map, navigator)

        chase_target = self._steer_to_waypoint() or target_pos

        cx = self.x + self.size * 0.5
        cy = self.y + self.size * 0.5
        dist = math.hypot(target_pos[0] - cx, target_pos[1] - cy)

        # Keep pressure at range, but decelerate near the player to avoid sticky bumper-chasing.
        desired_speed = min(self.max_speed, self.cruise_speed * 0.68)

        if dist > 520.0:
            catchup_bonus = min(160.0, (dist - 520.0) * 0.11)
            desired_speed = min(self.max_speed, desired_speed + catchup_bonus)
        elif 240.0 <= dist <= 420.0:
            desired_speed = min(self.max_speed, desired_speed + 40.0)

        if dist < 360.0:
            close_ratio = max(0.0, min(1.0, dist / 360.0))
            near_cap = self.cruise_speed * (0.15 + close_ratio * 0.55)
            desired_speed = min(desired_speed, near_cap)

        self._update_motion_towards(chase_target, desired_speed, dt, game_map, navigator, obs)
        self.ai_state = "chase"


# ---------------------------------------------------------------------------
# AI Manager
# ---------------------------------------------------------------------------


class AIManager:
    """Central manager for traffic + pursuit entities."""

    def __init__(self, rng: Optional[random.Random] = None, use_proximity_culling: bool = True):
        self._rng = rng or random.Random()

        self.traffic_agents: Dict[str, TrafficAI] = {}
        self.pursuit_agents: Dict[str, PursuitAI] = {}

        self.use_proximity_culling = bool(use_proximity_culling)

        self.alert_level = "idle"
        self._alert_timer = 0.0

        # Performance knobs.
        # Full AI updates are only run near the player.
        self.active_update_radius = 1700.0
        # Build obstacle lists from nearby entities only.
        self.obstacle_neighbor_radius = 620.0

        # Dynamic traffic streaming: keep traffic around players and recycle far NPCs.
        self.dynamic_traffic_enabled = True
        self.traffic_target_count = 16
        self.traffic_spawn_min_distance = 520.0
        self.traffic_spawn_radius = 1900.0
        self.traffic_despawn_radius = 3300.0
        self.traffic_center_bias = 0.68
        self.traffic_rebalance_interval = 0.25
        self.traffic_spawn_batch = 1
        self.traffic_edge_despawn_margin = 48.0
        self.traffic_spawn_attempt_factor = 10
        self._traffic_rebalance_timer = self.traffic_rebalance_interval
        self.use_dynamic_obstacles = True

        # Spawn acceleration: cache all valid road tiles once per map layout.
        self._spawn_road_cache_key: Optional[Tuple[int, int, int, int]] = None
        self._spawn_road_tiles: List[TilePoint] = []

        self._world_entities: Dict[str, Dict[str, Any]] = {}
        self._id_counters: Dict[str, int] = {"traffic": 1, "enemy": 1, "pursuit": 1, "robber": 1}

    def configure_dynamic_traffic(
        self,
        enabled: bool = True,
        target_count: Optional[int] = None,
        spawn_min_distance: Optional[float] = None,
        spawn_radius: Optional[float] = None,
        despawn_radius: Optional[float] = None,
        center_bias: Optional[float] = None,
        rebalance_interval: Optional[float] = None,
        spawn_batch: Optional[int] = None,
        edge_despawn_margin: Optional[float] = None,
    ) -> None:
        self.dynamic_traffic_enabled = bool(enabled)
        if target_count is not None:
            self.traffic_target_count = max(0, int(target_count))
        if spawn_min_distance is not None:
            self.traffic_spawn_min_distance = max(0.0, float(spawn_min_distance))
        if spawn_radius is not None:
            self.traffic_spawn_radius = max(50.0, float(spawn_radius))
        if despawn_radius is not None:
            self.traffic_despawn_radius = max(self.traffic_spawn_radius + 200.0, float(despawn_radius))
        if center_bias is not None:
            self.traffic_center_bias = _clamp(float(center_bias), 0.0, 1.0)
        if rebalance_interval is not None:
            self.traffic_rebalance_interval = max(0.1, float(rebalance_interval))
        if spawn_batch is not None:
            self.traffic_spawn_batch = max(1, int(spawn_batch))
        if edge_despawn_margin is not None:
            self.traffic_edge_despawn_margin = max(0.0, float(edge_despawn_margin))

    def configure_performance(
        self,
        active_update_radius: Optional[float] = None,
        obstacle_neighbor_radius: Optional[float] = None,
        use_dynamic_obstacles: Optional[bool] = None,
    ) -> None:
        if active_update_radius is not None:
            self.active_update_radius = max(250.0, float(active_update_radius))
        if obstacle_neighbor_radius is not None:
            self.obstacle_neighbor_radius = max(0.0, float(obstacle_neighbor_radius))
        if use_dynamic_obstacles is not None:
            self.use_dynamic_obstacles = bool(use_dynamic_obstacles)

    def _next_ai_id(self, prefix: str) -> str:
        idx = int(self._id_counters.get(prefix, 1))
        while True:
            ai_id = f"{prefix}_{idx}"
            idx += 1
            if ai_id not in self.traffic_agents and ai_id not in self.pursuit_agents:
                self._id_counters[prefix] = idx
                return ai_id

    def _normalize_focus_points(self, focus_points: Optional[Sequence[WorldPoint]]) -> List[WorldPoint]:
        out: List[WorldPoint] = []
        for p in focus_points or []:
            if p is None:
                continue
            if isinstance(p, (tuple, list)) and len(p) >= 2:
                out.append((float(p[0]), float(p[1])))
        return out

    def _road_spawn_tiles(self, navigator: MapNavigator) -> List[TilePoint]:
        game_map = navigator.game_map
        w = int(getattr(game_map, "map_width_tiles", 0))
        h = int(getattr(game_map, "map_height_tiles", 0))
        road_grid = getattr(game_map, "_road_grid", None)
        collision_grid = getattr(game_map, "_collision_grid", None)
        cache_key = (w, h, id(road_grid), id(collision_grid))

        if self._spawn_road_cache_key == cache_key and self._spawn_road_tiles:
            return self._spawn_road_tiles

        tiles: List[TilePoint] = []
        if w <= 0 or h <= 0:
            self._spawn_road_cache_key = cache_key
            self._spawn_road_tiles = tiles
            return tiles

        if road_grid is not None:
            for ty in range(h):
                try:
                    road_row = road_grid[ty]
                except (IndexError, TypeError):
                    continue

                try:
                    coll_row = collision_grid[ty] if collision_grid is not None else None
                except (IndexError, TypeError):
                    coll_row = None

                for tx in range(w):
                    try:
                        if not bool(road_row[tx]):
                            continue
                        if coll_row is not None and bool(coll_row[tx]):
                            continue
                    except (IndexError, TypeError):
                        continue
                    tiles.append((tx, ty))
        else:
            for ty in range(h):
                for tx in range(w):
                    if navigator.is_road_tile(tx, ty):
                        tiles.append((tx, ty))

        self._spawn_road_cache_key = cache_key
        self._spawn_road_tiles = tiles
        return tiles

    def _min_focus_distance_sq(self, point: WorldPoint, focus_points: Sequence[WorldPoint]) -> float:
        if not focus_points:
            return float("inf")
        return min(_distance_sq(point, fp) for fp in focus_points)

    def add_traffic(self, ai: TrafficAI) -> None:
        self.traffic_agents[ai.ai_id] = ai

    def add_pursuit(self, ai: PursuitAI) -> None:
        self.pursuit_agents[ai.ai_id] = ai

    def spawn_traffic(
        self,
        game_map: Any,
        count: int,
        car_pool: Optional[Sequence[Tuple[str, str]]] = None,
        prefix: str = "traffic",
        focus_points: Optional[Sequence[WorldPoint]] = None,
    ) -> List[TrafficAI]:
        cars = list(car_pool or [("MICRO", "White"), ("HATCHBACK", "Blue"), ("SEDAN", "Black")])
        spawned: List[TrafficAI] = []
        focus = self._normalize_focus_points(focus_points)

        navigator = MapNavigator(game_map)
        target_count = max(0, count)
        attempts = 0
        max_attempts = max(18, target_count * self.traffic_spawn_attempt_factor)
        existing_agents: List[TrafficAI] = list(self.traffic_agents.values()) + list(self.pursuit_agents.values())

        while len(spawned) < target_count and attempts < max_attempts:
            attempts += 1
            spawn_center = self._sample_road_spawn(navigator, max_tries=1, focus_points=focus)
            if spawn_center is None:
                continue

            ai_id = self._next_ai_id(prefix)
            car = self._rng.choice(cars)
            spawn_pos = (spawn_center[0] - 67.0, spawn_center[1] - 67.0)
            ai = TrafficAI(ai_id=ai_id, spawn_pos=spawn_pos, car=car, rng=self._rng)

            if not self._is_agent_spawn_valid(ai, game_map, existing_agents):
                continue

            ai._pick_next_waypoint(navigator)
            self.add_traffic(ai)
            existing_agents.append(ai)
            spawned.append(ai)

        return spawned

    def spawn_pursuit_enemy(
        self,
        game_map: Any,
        count: int = 1,
        prefix: str = "enemy",
        enabled: bool = False,
        entity_type: str = "pursuit",
        focus_points: Optional[Sequence[WorldPoint]] = None,
    ) -> List[PursuitAI]:
        kind = str(entity_type or "pursuit").lower()
        spawned: List[PursuitAI] = []
        navigator = MapNavigator(game_map)
        focus = self._normalize_focus_points(focus_points)

        target_count = max(0, count)
        attempts = 0
        max_attempts = max(16, target_count * self.traffic_spawn_attempt_factor)
        existing_agents: List[TrafficAI] = list(self.traffic_agents.values()) + list(self.pursuit_agents.values())

        while len(spawned) < target_count and attempts < max_attempts:
            attempts += 1
            spawn_center = self._sample_road_spawn(
                navigator,
                max_tries=1,
                focus_points=focus if kind == "robber" else None,
            )
            if spawn_center is None:
                continue

            ai_id = self._next_ai_id(prefix)
            spawn_pos = (spawn_center[0] - 67.0, spawn_center[1] - 67.0)
            if kind == "robber":
                ai = RobberAI(
                    ai_id=ai_id,
                    spawn_pos=spawn_pos,
                    car=self._rng.choice(ROBBER_CAR_POOL),
                    enabled=enabled,
                    rng=self._rng,
                )
            else:
                ai = PursuitAI(ai_id=ai_id, spawn_pos=spawn_pos, enabled=enabled, rng=self._rng)
                ai.entity_type = kind

            if not self._is_agent_spawn_valid(ai, game_map, existing_agents):
                continue

            ai._pick_next_waypoint(navigator)
            self.add_pursuit(ai)
            existing_agents.append(ai)
            spawned.append(ai)

        return spawned

    def count_agents_by_kind(self, ai_kind: str) -> int:
        kind = str(ai_kind or "").lower()
        if not kind:
            return 0
        return sum(1 for ai in self.pursuit_agents.values() if str(getattr(ai, "entity_type", "")).lower() == kind)

    def clear_agents_by_kind(self, ai_kind: str) -> int:
        kind = str(ai_kind or "").lower()
        if not kind:
            return 0
        removed = 0
        for ai_id in list(self.pursuit_agents.keys()):
            ai = self.pursuit_agents.get(ai_id)
            if ai is None:
                continue
            if str(getattr(ai, "entity_type", "")).lower() != kind:
                continue
            self.pursuit_agents.pop(ai_id, None)
            removed += 1
        return removed

    def ensure_robbers(
        self,
        game_map: Any,
        target_count: int,
        focus_points: Optional[Sequence[WorldPoint]] = None,
        enabled: bool = True,
    ) -> List[PursuitAI]:
        desired = max(0, int(target_count))
        robber_ids = [
            ai_id
            for ai_id, ai in self.pursuit_agents.items()
            if str(getattr(ai, "entity_type", "")).lower() == "robber"
        ]

        if len(robber_ids) > desired:
            for ai_id in robber_ids[desired:]:
                self.pursuit_agents.pop(ai_id, None)
            robber_ids = robber_ids[:desired]

        if len(robber_ids) < desired:
            self.spawn_pursuit_enemy(
                game_map,
                count=desired - len(robber_ids),
                prefix="robber",
                enabled=enabled,
                entity_type="robber",
                focus_points=focus_points,
            )

        robbers: List[PursuitAI] = []
        for ai in self.pursuit_agents.values():
            if str(getattr(ai, "entity_type", "")).lower() != "robber":
                continue
            ai.enabled = bool(enabled)
            robbers.append(ai)
        return robbers

    def _is_map_collision_free(self, rect: RectLike, game_map: Any) -> bool:
        if hasattr(game_map, "check_collision"):
            try:
                return not bool(game_map.check_collision(rect))
            except Exception:
                pass

        if hasattr(game_map, "check_rect_collision"):
            try:
                return not bool(game_map.check_rect_collision(rect))
            except Exception:
                pass

        collision_rects = getattr(game_map, "collision_rects", None)
        if not collision_rects:
            return True
        for tile_rect in collision_rects:
            if _rects_overlap(rect, tile_rect):
                return False
        return True

    def _is_agent_spawn_valid(self, agent: TrafficAI, game_map: Any, others: Optional[Iterable[TrafficAI]] = None) -> bool:
        hitbox = agent.get_hitbox_rect()

        # Never spawn inside map collision boxes.
        if not self._is_map_collision_free(hitbox, game_map):
            return False

        # Keep a small spacing between AI at spawn time.
        cx = agent.x + agent.size * 0.5
        cy = agent.y + agent.size * 0.5
        min_dist_sq = (agent.size * 0.9) * (agent.size * 0.9)
        for other in others or []:
            ox = other.x + other.size * 0.5
            oy = other.y + other.size * 0.5
            dx = cx - ox
            dy = cy - oy
            if dx * dx + dy * dy < min_dist_sq:
                return False

        return True

    def _sample_road_spawn(
        self,
        navigator: MapNavigator,
        max_tries: int = 300,
        focus_points: Optional[Sequence[WorldPoint]] = None,
    ) -> Optional[WorldPoint]:
        game_map = navigator.game_map
        w = int(getattr(game_map, "map_width_tiles", 0))
        h = int(getattr(game_map, "map_height_tiles", 0))
        if w <= 0 or h <= 0:
            return None

        road_tiles = self._road_spawn_tiles(navigator)
        if not road_tiles:
            return None

        width_px = float(getattr(game_map, "width_px", w * getattr(game_map, "tile_width", 32)))
        height_px = float(getattr(game_map, "height_px", h * getattr(game_map, "tile_height", 32)))
        world_center = (width_px * 0.5, height_px * 0.5)
        center_radius = max(
            float(getattr(game_map, "tile_width", 32)) * 10.0,
            min(width_px, height_px) * 0.28,
        )
        center_radius_sq = center_radius * center_radius
        focus = self._normalize_focus_points(focus_points)

        min_focus_sq = self.traffic_spawn_min_distance * self.traffic_spawn_min_distance
        max_focus_sq = self.traffic_spawn_radius * self.traffic_spawn_radius

        for _ in range(max_tries):
            tx, ty = self._rng.choice(road_tiles)
            spawn = navigator.tile_to_world(tx, ty, centered=True)

            if focus:
                d2 = self._min_focus_distance_sq(spawn, focus)
                if d2 < min_focus_sq:
                    continue
                if d2 > max_focus_sq * 1.4:
                    continue

            # Keep some global density near map center when no focus points are provided.
            if not focus and self._rng.random() < self.traffic_center_bias:
                if _distance_sq(spawn, world_center) > center_radius_sq:
                    continue

            return spawn

        # Fallback: return any road tile if constraints are too strict.
        tx, ty = self._rng.choice(road_tiles)
        return navigator.tile_to_world(tx, ty, centered=True)

    def _is_agent_at_world_limit(self, agent: TrafficAI, game_map: Any) -> bool:
        world_w = float(getattr(game_map, "width_px", 0.0))
        world_h = float(getattr(game_map, "height_px", 0.0))
        if world_w <= 0.0 or world_h <= 0.0:
            return False

        margin = max(0.0, self.traffic_edge_despawn_margin)
        cx = agent.x + agent.size * 0.5
        cy = agent.y + agent.size * 0.5
        return cx <= margin or cy <= margin or cx >= world_w - margin or cy >= world_h - margin

    def _despawn_far_traffic(self, game_map: Any, focus_points: Sequence[WorldPoint]) -> int:
        if not focus_points:
            return 0

        despawn_sq = self.traffic_despawn_radius * self.traffic_despawn_radius
        to_remove: List[str] = []
        for ai_id, agent in self.traffic_agents.items():
            if self._is_agent_at_world_limit(agent, game_map):
                to_remove.append(ai_id)
                continue

            center = (agent.x + agent.size * 0.5, agent.y + agent.size * 0.5)
            if self._min_focus_distance_sq(center, focus_points) > despawn_sq:
                to_remove.append(ai_id)

        for ai_id in to_remove:
            self.traffic_agents.pop(ai_id, None)
        return len(to_remove)

    def _build_neighbor_map(self, agent_centers: Dict[str, WorldPoint], radius: float) -> Dict[str, List[str]]:
        if not agent_centers:
            return {}

        if radius <= 0.0:
            return {ai_id: [] for ai_id in agent_centers.keys()}

        cell_size = max(64.0, float(radius))
        inv_cell = 1.0 / cell_size
        grid: Dict[Tuple[int, int], List[str]] = {}

        for ai_id, center in agent_centers.items():
            gx = int(math.floor(center[0] * inv_cell))
            gy = int(math.floor(center[1] * inv_cell))
            grid.setdefault((gx, gy), []).append(ai_id)

        cell_span = max(1, int(math.ceil(radius / cell_size)))
        radius_sq = radius * radius
        out: Dict[str, List[str]] = {}

        for ai_id, center in agent_centers.items():
            gx = int(math.floor(center[0] * inv_cell))
            gy = int(math.floor(center[1] * inv_cell))
            neighbors: List[str] = []

            for nx in range(gx - cell_span, gx + cell_span + 1):
                for ny in range(gy - cell_span, gy + cell_span + 1):
                    for other_id in grid.get((nx, ny), ()):
                        if other_id == ai_id:
                            continue
                        if _distance_sq(center, agent_centers[other_id]) <= radius_sq:
                            neighbors.append(other_id)

            out[ai_id] = neighbors

        return out

    def _rebalance_dynamic_traffic(
        self,
        game_map: Any,
        navigator: MapNavigator,
        focus_points: Sequence[WorldPoint],
    ) -> None:
        if not self.dynamic_traffic_enabled or not focus_points:
            return

        self._despawn_far_traffic(game_map, focus_points)

        missing = self.traffic_target_count - len(self.traffic_agents)
        if missing <= 0:
            return

        spawn_count = min(missing, self.traffic_spawn_batch)
        self.spawn_traffic(
            game_map,
            count=spawn_count,
            prefix="traffic",
            focus_points=focus_points,
        )

    def raise_alert(self, level: str = "suspicious", duration: float = 6.0) -> None:
        self.alert_level = (level or "suspicious").lower()
        self._alert_timer = max(0.0, duration)
        for ai in self.pursuit_agents.values():
            ai.on_alert(self.alert_level)

    def update_all(
        self,
        dt: float,
        game_map: Any,
        player: Any = None,
        extra_obstacles: Optional[Iterable[RectLike]] = None,
        focus_points: Optional[Sequence[WorldPoint]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        if dt <= 0.0:
            return self._world_entities

        if self._alert_timer > 0.0:
            self._alert_timer = max(0.0, self._alert_timer - dt)
            if self._alert_timer == 0.0 and self.alert_level != "idle":
                self.alert_level = "idle"
                for ai in self.pursuit_agents.values():
                    ai.on_alert("idle")

        navigator = MapNavigator(game_map)
        static_obstacles = list(extra_obstacles or [])

        player_hitbox = None
        player_center: Optional[WorldPoint] = None
        if player is not None and hasattr(player, "get_hitbox_rect"):
            player_hitbox = player.get_hitbox_rect()
        if player is not None and hasattr(player, "x") and hasattr(player, "y"):
            px = float(player.x) + float(getattr(player, "size", 0.0)) * 0.5
            py = float(player.y) + float(getattr(player, "size", 0.0)) * 0.5
            player_center = (px, py)

        merged_focus = self._normalize_focus_points(focus_points)
        if player_center is not None:
            merged_focus.append(player_center)

        if self.dynamic_traffic_enabled:
            self._traffic_rebalance_timer += dt
            if self._traffic_rebalance_timer >= self.traffic_rebalance_interval:
                self._traffic_rebalance_timer = 0.0
                self._rebalance_dynamic_traffic(game_map, navigator, merged_focus)

        all_agents: List[TrafficAI] = list(self.traffic_agents.values()) + list(self.pursuit_agents.values())

        agent_hitboxes: Dict[str, RectLike] = {}
        agent_centers: Dict[str, WorldPoint] = {}
        for agent in all_agents:
            agent_hitboxes[agent.ai_id] = agent.get_hitbox_rect()
            agent_centers[agent.ai_id] = (agent.x + agent.size * 0.5, agent.y + agent.size * 0.5)

        active_radius_sq = self.active_update_radius * self.active_update_radius
        neighbor_map: Dict[str, List[str]] = {}
        if self.use_dynamic_obstacles and self.obstacle_neighbor_radius > 0.0:
            neighbor_map = self._build_neighbor_map(agent_centers, self.obstacle_neighbor_radius)

        for agent in all_agents:
            center = agent_centers[agent.ai_id]
            should_update = True
            if self.use_proximity_culling and player_center is not None:
                should_update = _distance_sq(center, player_center) <= active_radius_sq
                if isinstance(agent, PursuitAI) and agent.enabled:
                    should_update = True

            if not should_update:
                # Far traffic stays dormant to keep frame time low.
                agent.speed = max(0.0, agent.speed - agent.brake * dt * 0.35)
                agent.ai_state = "sleep"
                continue

            obs = list(static_obstacles)
            if player_hitbox is not None and not isinstance(agent, RobberAI):
                obs.append(player_hitbox)

            if self.use_dynamic_obstacles:
                for other_id in neighbor_map.get(agent.ai_id, []):
                    hit = agent_hitboxes.get(other_id)
                    if hit is not None:
                        obs.append(hit)

            if isinstance(agent, PursuitAI):
                if player is not None:
                    agent.set_target(player)
                agent.update(dt, game_map, obstacles=obs, navigator=navigator)
            else:
                agent.update(dt, game_map, obstacles=obs, navigator=navigator)

        entities: Dict[str, Dict[str, Any]] = {}
        for ai in all_agents:
            entities[ai.ai_id] = ai.to_world_entity()

        self._world_entities = entities
        return entities

    # Server-authoritative helper alias for future multiplayer integration.
    def update_ai_world(
        self,
        dt: float,
        game_map: Any,
        player: Any = None,
        extra_obstacles: Optional[Iterable[RectLike]] = None,
        focus_points: Optional[Sequence[WorldPoint]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        return self.update_all(
            dt,
            game_map,
            player=player,
            extra_obstacles=extra_obstacles,
            focus_points=focus_points,
        )

    def get_world_entities(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._world_entities)

    def serialize_world_entities(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for entity_id, payload in self._world_entities.items():
            row = dict(payload)
            row["id"] = entity_id
            car = row.get("car", ["MICRO", "White"])
            if isinstance(car, tuple):
                row["car"] = [car[0], car[1]]
            out.append(row)
        return out

    @staticmethod
    def entities_to_other_players(world_entities: Dict[str, Dict[str, Any]], prefix: str = "AI") -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for entity_id, payload in world_entities.items():
            name = f"{prefix}:{entity_id}"
            car = payload.get("car", ["MICRO", "White"])
            if isinstance(car, (tuple, list)) and len(car) >= 2:
                car_tuple = (car[0], car[1])
            else:
                car_tuple = ("MICRO", "White")

            merged = dict(payload)
            merged.update(
                {
                    "x": payload.get("x", 0.0),
                    "y": payload.get("y", 0.0),
                    "angle": payload.get("angle", 0.0),
                    "car": car_tuple,
                    "on_road": payload.get("on_road", True),
                    "ai": True,
                    "ai_kind": payload.get("ai_kind", "traffic"),
                    "ai_state": payload.get("ai_state", "driving"),
                }
            )
            out[name] = merged
        return out


__all__ = [
    "AIEntityState",
    "MapNavigator",
    "TrafficAI",
    "PursuitAI",
    "RobberAI",
    "AIManager",
]
