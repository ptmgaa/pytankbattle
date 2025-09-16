# ai.py
from tank import Tank, Direction
from field import Field
from util import ArmedTimer, GameObject
import random
from itertools import cycle
import heapq


# ---------- A* pathfinding ----------
def heuristic(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def neighbors(cell, field_map):
    x, y = cell
    for dx, dy, dir in ((1,0,Direction.RIGHT), (-1,0,Direction.LEFT), (0,1,Direction.DOWN), (0,-1,Direction.UP)):
        nx, ny = x+dx, y+dy
        if 0 <= nx < field_map.width and 0 <= ny < field_map.height:
            val = field_map.cells[ny][nx]
            if val is None:
                yield (nx, ny, dir)


def a_star(start, goal, field_map):
    frontier = []
    heapq.heappush(frontier, (0, start))
    came_from = {start: None}
    cost_so_far = {start: 0}

    while frontier:
        _, current = heapq.heappop(frontier)
        if current == goal:
            break
        for nx, ny, dir in neighbors(current, field_map):
            new_cost = cost_so_far[current] + 1
            if (nx, ny) not in cost_so_far or new_cost < cost_so_far[(nx, ny)]:
                cost_so_far[(nx, ny)] = new_cost
                priority = new_cost + heuristic((nx, ny), goal)
                heapq.heappush(frontier, (priority, (nx, ny)))
                came_from[(nx, ny)] = (current, dir)

    current = goal
    path = []
    while current != start:
        prev = came_from.get(current)
        if not prev:
            return []
        current, dir = prev
        path.append(dir)
    path.reverse()
    return path


# ---------- Tank AI ----------
class TankAI:
    SPAWNING_DELAY = 1.5
    FIRE_TIMER = 1.0

    @staticmethod
    def dir_delay():
        return random.uniform(0.3, 1.5)

    def __init__(self, tank: Tank, field: Field):
        self.tank = tank
        self.field = field

        self.fire_timer = ArmedTimer(delay=self.FIRE_TIMER)
        self.dir_timer = ArmedTimer(delay=self.dir_delay())
        self.spawn_timer = ArmedTimer(delay=self.SPAWNING_DELAY)

    def _destroy(self):
        self.tank.to_destroy = True

    def _degrade(self):
        if self.tank.color == Tank.Color.PLAIN:
            self.tank.color = Tank.Color.GREEN
        else:
            self._destroy()

    # --- kiểm tra đường thẳng hàng/cột ---
    def find_target_in_line(self):
        # ưu tiên căn cứ
        if hasattr(self.field, 'my_base') and self.field.my_base and not self.field.my_base.broken:
            if self.clear_line(self.field.my_base.position):
                return self.field.my_base
        # tank người chơi
        if hasattr(self.field, 'game') and self.field.game.my_tank:
            t = self.field.game.my_tank
            if self.clear_line(t.position):
                return t
        return None

    def clear_line(self, target_pos):
        # Kiểm tra xem tank có thể bắn thẳng tới target không
        tx, ty = target_pos
        x, y = self.tank.position
        map = self.field.map

        c1, r1 = map.col_row_from_coords(x, y)
        c2, r2 = map.col_row_from_coords(tx, ty)

        if c1 == c2:  # cùng cột
            step = 1 if r2 > r1 else -1
            for r in range(r1 + step, r2, step):
                if map.cells[r][c1] is not None:
                    return False
            return True
        elif r1 == r2:  # cùng hàng
            step = 1 if c2 > c1 else -1
            for c in range(c1 + step, c2, step):
                if map.cells[r1][c] is not None:
                    return False
            return True
        return False

    def align_direction_to(self, target):
        tx, ty = target.position
        x, y = self.tank.position
        if abs(tx - x) > abs(ty - y):
            self.tank.direction = Direction.RIGHT if tx > x else Direction.LEFT
        else:
            self.tank.direction = Direction.DOWN if ty > y else Direction.UP

    def pick_direction(self):
        c, r = self.field.map.col_row_from_coords(*self.tank.position)
        # Chọn mục tiêu: căn cứ > tank người chơi
        targets = []
        if hasattr(self.field, 'my_base') and self.field.my_base and not self.field.my_base.broken:
            bx, by = self.field.map.col_row_from_coords(*self.field.my_base.position)
            targets.append((bx, by))
        if hasattr(self.field, 'game') and self.field.game.my_tank:
            tx, ty = self.field.map.col_row_from_coords(*self.field.game.my_tank.position)
            targets.append((tx, ty))

        for goal in targets:
            path = a_star((c, r), goal, self.field.map)
            if path:
                return path[0]

        # fallback random
        prohibited_dir = set()
        if c <= 1: prohibited_dir.add(Direction.LEFT)
        if r <= 1: prohibited_dir.add(Direction.UP)
        if c >= self.field.map.width - 2: prohibited_dir.add(Direction.RIGHT)
        if r >= self.field.map.height - 2: prohibited_dir.add(Direction.DOWN)
        choices = list(Direction.all() - prohibited_dir)
        if not choices:
            choices = list(Direction.all())
        return random.choice(choices)

    def update(self):
        if self.tank.is_spawning:
            if self.spawn_timer.tick():
                if self.field.oc_map.test_rect(self.tank.bounding_rect, good_values=(None, self.tank)):
                    self.tank.is_spawning = False
                else:
                    return
            else:
                return

        if self.tank.hit:
            if self.tank.tank_type == Tank.Type.ENEMY_HEAVY:
                self._degrade()
            else:
                self._destroy()
            self.tank.hit = False

        # --- chủ động bắn nếu thấy đường thẳng ---
        target = self.find_target_in_line()
        if target and self.fire_timer.tick():
            self.align_direction_to(target)
            self.tank.fire()
            self.fire_timer.start()
        else:
            if self.fire_timer.tick():
                self.tank.fire()
                self.fire_timer.start()

        # --- thay đổi hướng di chuyển định kỳ ---
        if self.dir_timer.tick():
            self.tank.direction = self.pick_direction()
            self.dir_timer.delay = self.dir_delay()
            self.dir_timer.start()

        # --- di chuyển, tránh đứng im ---
        prev_pos = self.tank.position
        self.tank.move_tank(self.tank.direction)

        # nếu sau khi move mà không di chuyển được (bị kẹt) → chọn hướng khác
        if self.tank.position == prev_pos:
            self.tank.direction = self.pick_direction()
            self.tank.move_tank(self.tank.direction)

    def reset(self):
        self.tank.direction = Direction.random()


# ---------- Enemy Fraction AI ----------
class EnemyFractionAI:
    MAX_ENEMIES = 5
    RESPAWN_TIMER = 5.0

    def __init__(self, field: Field, tanks: GameObject, total_enemies=None):
        self.tanks = tanks
        self.field = field

        self.spawn_points = { (x, y): None for x, y in field.respawn_points(True) }

        self.spawn_timer = ArmedTimer(self.RESPAWN_TIMER)
        self.dynamic_timer = ArmedTimer(5.0)  # cứ 5s spawn thêm tank

        self.spawn_increment = 3  # số tank spawn thêm mỗi lần

        self.enemy_queue = cycle([
            Tank.Type.ENEMY_SIMPLE,
            Tank.Type.ENEMY_FAST,
            Tank.Type.ENEMY_MIDDLE,
            Tank.Type.ENEMY_HEAVY,
        ])

        self._enemy_queue_iter = iter(self.enemy_queue)

        self.total_to_spawn = total_enemies if total_enemies else 100
        self.spawned_count = 0
        self.killed_count = 0  # đã tiêu diệt bao nhiêu

        self.try_to_spawn_tank()

    @property
    def all_enemies(self):
        return [t for t in self.tanks if t.fraction == Tank.ENEMY]

    @property
    def enemies_left_to_spawn(self):
        return max(0, self.total_to_spawn - self.spawned_count + len(self.all_enemies))

    @property
    def has_more_enemies(self):
        return self.total_to_spawn is None or self.total_to_spawn > 0

    def get_next_enemy(self, pos):
        if self.spawned_count >= self.total_to_spawn:
            return None  # đã spawn đủ quota, không spawn thêm

        t_type = next(self._enemy_queue_iter)
        new_tank = Tank(Tank.ENEMY, Tank.Color.PLAIN, t_type)
        new_tank.is_spawning = True
        new_tank.ai = TankAI(new_tank, self.field)

        if random.uniform(0, 1) > 0.35:
            new_tank.is_bonus = True

        new_tank.place(self.field.get_center_of_cell(*pos))

        self.spawned_count += 1
        return new_tank

    def try_to_spawn_tank(self):
        free_locations = list()
        for loc, tank in list(self.spawn_points.items()):
            if isinstance(tank, Tank):
                if not tank.is_spawning:
                    self.spawn_points[loc] = None
            else:
                free_locations.append(loc)

        # Nếu còn chỗ trống và còn tank để spawn
        if free_locations and self.has_more_enemies:
            # Spawn tối đa 2 con mỗi lần (nếu còn chỗ)
            for _ in range(2):
                if not free_locations or not self.has_more_enemies:
                    break
                pos = random.choice(free_locations)
                free_locations.remove(pos)

                tank = self.get_next_enemy(pos)
                if tank:
                    self.spawn_points[pos] = tank
                    self.tanks.add_child(tank)

    def stop_all_moving(self):
        for t in self.all_enemies:
            t.stop()

    def update(self):
        # spawn mỗi 5s
        if self.dynamic_timer.tick():
            self.dynamic_timer.start()

            remaining = self.total_to_spawn - self.spawned_count
            if remaining > 0:
                to_spawn = min(self.spawn_increment,
                               remaining,
                               self.MAX_ENEMIES - len(self.all_enemies))
                for _ in range(to_spawn):
                    self.try_to_spawn_tank()

        # update AI cho tất cả enemy
        for enemy_tank in self.all_enemies:
            self.update_one_tank(enemy_tank)

    def update_one_tank(self, t: Tank):
        t.to_destroy = False
        t.ai.update()
