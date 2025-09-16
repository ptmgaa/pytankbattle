import pygame
from field import Field
from projectile import Projectile
from tank import Tank
from util import *
from ui import *
from explosion import Explosion
from my_base import MyBase
from bonus import Bonus, BonusType
from ai import EnemyFractionAI
from bonus_field_protect import FieldProtector
from score_node import ScoreLayer
import random
import time
import datetime


class Game:
    ENEMIES_PER_LEVEL = 100

    def __init__(self):
        self.r = random.Random()
        self.scene = GameObject()
        self.running = True
        self.score = 0

        # field
        self.field = Field()
        self.field.load_from_file('data/level1.txt')
        self.scene.add_child(self.field)
        self.field_protector = FieldProtector(self.field)

        # base
        self.my_base = MyBase()
        self.my_base.position = self.field.map.coord_by_col_and_row(12, 24)
        self.scene.add_child(self.my_base)

        # tanks
        self.tanks = GameObject()
        self.scene.add_child(self.tanks)
        self.my_tank = None
        self.make_my_tank()

        # AI
        self.ai = EnemyFractionAI(self.field, self.tanks, total_enemies=self.ENEMIES_PER_LEVEL)

        # projectiles
        self.projectiles = GameObject()
        self.scene.add_child(self.projectiles)

        # bonuses
        self.bonuses = GameObject()
        self.scene.add_child(self.bonuses)

        # score
        self.score_layer = ScoreLayer()
        self.scene.add_child(self.score_layer)

        self.freeze_timer = Timer(10)
        self.freeze_timer.done = True
        self.font_debug = pygame.font.Font(None, 18)

        # UI message
        self._msg = None
        self._msg_timer = Timer(2.0)
        self._victory_announced = False

        # Win/lose labels
        self.over_label = None
        self.win_label = None

        # test bonus
        self.make_bonus(*self.field.map.coord_by_col_and_row(13, 22), BonusType.TOP_TANK)

    def respawn_tank(self, t: Tank):
        is_friend = self.is_friend(t)
        pos = random.choice(self.field.respawn_points(not is_friend))
        t.place(self.field.get_center_of_cell(*pos))
        if is_friend:
            t.tank_type = t.Type.LEVEL_1

    def make_my_tank(self):
        self.my_tank = Tank(Tank.FRIEND, Tank.Color.YELLOW, Tank.Type.LEVEL_1)
        self.respawn_tank(self.my_tank)
        self.my_tank.activate_shield()
        self.tanks.add_child(self.my_tank)
        self.my_tank_move_to_direction = None

    def switch_my_tank(self):
        if not self.my_tank:
            return
        old_tank = self.my_tank
        t, d, p = old_tank.tank_type, old_tank.direction, old_tank.position

        # Xóa tank cũ
        old_tank.remove_from_parent()

        # Lấy loại tank kế tiếp
        types = list(Tank.Type)
        current_index = types.index(t)
        next_type = types[(current_index + 1) % len(types)]

        # Tạo tank mới với type mới
        new_tank = Tank(Tank.FRIEND, Tank.Color.YELLOW, next_type)
        new_tank.position = new_tank.old_position = p
        new_tank.direction = d
        new_tank.activate_shield()

        self.tanks.add_child(new_tank)
        self.my_tank = new_tank
        print(f"Switched tank to {next_type.name}")

    @property
    def frozen_enemy_time(self):
        return not self.freeze_timer.done

    def _on_destroyed_tank(self, t: Tank):
        if t.is_bonus:
            self.make_bonus(*t.center_point)
        if t.fraction == t.ENEMY:
            if t.tank_type == t.Type.ENEMY_SIMPLE:
                ds = 100
            elif t.tank_type == t.Type.ENEMY_FAST:
                ds = 200
            elif t.tank_type == t.Type.ENEMY_MIDDLE:
                ds = 300
            elif t.tank_type == t.Type.ENEMY_HEAVY:
                ds = 400
            else:
                ds = 0
            self.score += ds
            self.score_layer.add(*t.center_point, ds)

    def make_bonus(self, x, y, t=None):
        bonus = Bonus(BonusType.random() if t is None else t, x, y)
        self.bonuses.add_child(bonus)

    def make_explosion(self, x, y, expl_type):
        self.scene.add_child(Explosion(x, y, expl_type))

    def is_friend(self, tank):
        return tank.fraction == tank.FRIEND

    def fire(self, tank=None):
        tank = self.my_tank if tank is None else tank
        tank.want_to_fire = False
        if self.is_game_over and self.is_friend(tank):
            return
        if tank.try_fire():
            power = Projectile.POWER_HIGH if tank.tank_type.can_crash_concrete else Projectile.POWER_NORMAL
            projectile = Projectile(*tank.gun_point, tank.direction, sender=tank, power=power)
            self.projectiles.add_child(projectile)

    def move_tank(self, direction: Direction, tank=None):
        tank = self.my_tank if tank is None else tank
        tank.remember_position()
        tank.move_tank(direction)

    def apply_bonus(self, t: Tank, bonus: BonusType):
        if bonus == BonusType.DESTRUCTION:
            enemies = [ent for ent in list(self.tanks)
                       if isinstance(ent, Tank) and not ent.is_spawning and ent.fraction == Tank.ENEMY]
            for enemy in enemies:
                self.kill_tank(enemy)
            self.show_message("DESTRUCTION: all enemies cleared")
        elif bonus == BonusType.CASK:
            t.shielded = True
            t.activate_shield()
            self.show_message("CASK: Shielded!")
        elif bonus == BonusType.UPGRADE:
            t.upgrade()
            self.show_message(f"UPGRADE: {t.tank_type.name}")
        elif bonus == BonusType.TIMER:
            self.freeze_timer.start()
            self.show_message("TIMER: enemies frozen")
        elif bonus == BonusType.STIFF_BASE:
            self.field_protector.activate()
            self.show_message("STIFF_BASE: base protected")
        elif bonus == BonusType.TOP_TANK:
            self.switch_my_tank()
            self.show_message(f"TOP_TANK: switched to {self.my_tank.tank_type.name}")
        elif bonus == BonusType.GUN:
            self.show_message("GUN: not implemented")
            print("Bonus GUN picked (no effect implemented).")
        else:
            print(f'Bonus {bonus} not implemented yet.')

    def update_bonuses(self):
        for b in list(self.bonuses):  # type: Bonus
            if b.intersects_rect(self.my_tank.bounding_rect):
                b.remove_from_parent()
                self.apply_bonus(self.my_tank, b.type)

    @property
    def all_mature_tanks(self):
        return (t for t in self.tanks if not t.is_spawning)

    @property
    def is_game_over(self):
        return self.my_base.broken

    @property
    def is_victory(self):
        try:
            no_more = not self.ai.has_more_enemies
            alive = len(self.ai.all_enemies)
            return (not self.is_game_over) and no_more and (alive == 0)
        except Exception:
            return False

    def _log_result(self, result_label: str):
        try:
            with open('results.log', 'a') as f:
                f.write(f"{datetime.datetime.now().isoformat()} {result_label} score={self.score}\n")
        except Exception as e:
            print("Failed to write results.log:", e)

    def _on_win(self):
        if not getattr(self, '_won', False):
            self._won = True
            self._log_result("WIN")
            self.show_message("YOU WIN!")
            print("WIN - score:", self.score)
            self.ai.total_to_spawn = 0
            self.ai.stop_all_moving()
            self.win_label = GameWinLabel()

    def make_game_over(self):
        if not self.my_base.broken:
            self.my_base.broken = True
        go = GameOverLabel()
        go.place_at_center(self.field)
        self.scene.add_child(go)
        self._log_result("LOSE")
        self.show_message("GAME OVER")
        print("GAME OVER - score:", self.score)
        self.over_label = go

    def update_tanks(self):
        for tank in self.all_mature_tanks:
            self.field.oc_map.fill_rect(tank.bounding_rect, tank, only_if_empty=True)

        if not self.is_game_over:
            if self.my_tank_move_to_direction is None:
                self.my_tank.stop()
                self.my_tank.align()
            else:
                self.move_tank(self.my_tank_move_to_direction, self.my_tank)

        self.freeze_timer.tick()
        if self.frozen_enemy_time:
            self.ai.stop_all_moving()
        else:
            if not getattr(self, '_won', False):
                self.ai.update()

        for tank in list(self.all_mature_tanks):
            if tank.want_to_fire:
                self.fire(tank)
            if tank.to_destroy:
                tank.remove_from_parent()
            bb = tank.bounding_rect
            if not self.field.oc_map.test_rect(bb, good_values=(None, tank)):
                push_back = True
            else:
                push_back = self.field.intersect_rect(bb)
            if push_back:
                tank.undo_move()

    def hit_tank(self, t: Tank):
        destroy = False
        if self.is_friend(t):
            destroy = True
            self.respawn_tank(t)
        else:
            t.hit = True
            self.ai.update_one_tank(t)
            if t.to_destroy:
                destroy = True
                t.remove_from_parent()
                self._on_destroyed_tank(t)
        if destroy:
            self.make_explosion(*t.center_point, Explosion.TYPE_FULL)

    def kill_tank(self, t: Tank):
        self.make_explosion(*t.center_point, Explosion.TYPE_FULL)
        if self.is_friend(t):
            self.respawn_tank(t)
        else:
            self.ai.update_one_tank(t)
            t.remove_from_parent()

    def show_message(self, msg, duration=2.0):
        self._msg = msg
        self._msg_timer.delay = duration
        self._msg_timer.start()

    def update_projectiles(self):
        for p in list(self.projectiles):  # type: Projectile
            r = extend_rect((*p.position, 0, 0), 2)
            self.field.oc_map.fill_rect(r, p)

        remove_projectiles_waitlist = set()
        for p in list(self.projectiles):
            p.update()
            something = self.field.oc_map.get_cell_by_coords(*p.position)
            if something and something is not p and isinstance(something, Projectile):
                remove_projectiles_waitlist.add(p)
                remove_projectiles_waitlist.add(something)

            was_stricken_object = False
            x, y = p.position
            if self.field.check_hit(p):
                was_stricken_object = True
                self.make_explosion(*p.position, Explosion.TYPE_SUPER_SHORT)
            elif self.my_base.check_hit(x, y):
                self.make_game_over()
                was_stricken_object = True
                self.make_explosion(*self.my_base.center_point, Explosion.TYPE_FULL)
            else:
                for t in self.all_mature_tanks:
                    if t is not p.sender and t.check_hit(x, y):
                        was_stricken_object = True
                        if not t.shielded and p.sender.fraction != t.fraction:
                            self.make_explosion(*p.position, Explosion.TYPE_SHORT)
                            self.hit_tank(t)
                        break
            if was_stricken_object:
                remove_projectiles_waitlist.add(p)

        for p in remove_projectiles_waitlist:
            p.remove_from_parent()

    def update(self):
        if not self.running:
            return

        self.field.oc_map.clear()
        self.field.oc_map.fill_rect(self.my_base.bounding_rect, self.my_base)

        self.field_protector.update()
        self.score_layer.update()

        self.update_tanks()
        self.update_bonuses()
        self.update_projectiles()
        self._msg_timer.tick()

        if self.is_game_over:
            self.running = False
            self.make_game_over()
        elif self.is_victory:
            self.running = False
            self._on_win()

    def render(self, screen):
        self.scene.visit(screen)

        score_label = self.font_debug.render(str(self.score), 1, (255, 255, 255))
        screen.blit(score_label, (GAME_WIDTH - 50, 5))

        dbg_text = f'Objects: {self.scene.total_children - 1}'
        if self.is_game_over:
            dbg_text = 'Press R to restart! ' + dbg_text
        dbg_label = self.font_debug.render(dbg_text, 1, (255, 255, 255))
        screen.blit(dbg_label, (5, 5))

        try:
            t = self.my_tank
            shield_remaining = 0.0
            if hasattr(t, '_shield_timer') and not t._shield_timer.done:
                shield_remaining = max(0.0, round(t._shield_timer.delay - (time.monotonic() - t._shield_timer.last_time), 1))
            level = t.tank_type.name
            hud = f'Level: {level}  Shield: {shield_remaining}s'
        except Exception:
            hud = ''
        enemies_left = self.ai.enemies_left_to_spawn
        enemies_left_text = str(enemies_left) if enemies_left is not None else '∞'
        hud2 = f'Enemies left: {enemies_left_text}  Score: {self.score}'
        hud_label = self.font_debug.render(hud, 1, (255, 255, 255))
        hud2_label = self.font_debug.render(hud2, 1, (255, 255, 255))
        screen.blit(hud_label, (5, GAME_HEIGHT - 40))
        screen.blit(hud2_label, (5, GAME_HEIGHT - 22))

        if self._msg and not self._msg_timer.done:
            msg_label = self.font_debug.render(self._msg, 1, (255, 255, 0))
            mx = (GAME_WIDTH - msg_label.get_width()) // 2
            my = 10
            screen.blit(msg_label, (mx, my))

        if self.over_label:
            self.over_label.render(screen)
        if self.win_label:
            self.win_label.render(screen)