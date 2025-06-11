import pygame
import random
import sys
import os
import math

# Константы
TILE_SIZE = 32
MAP_WIDTH = 25
MAP_HEIGHT = 18
SCREEN_WIDTH = MAP_WIDTH * TILE_SIZE
SCREEN_HEIGHT = MAP_HEIGHT * TILE_SIZE + 40  # дополнительное пространство для HUD
FPS = 60

# Цвета
WHITE = (255, 255, 255)
RED = (200, 0, 0)
DARKRED = (150, 0, 0)
BLACK = (0, 0, 0)
GRAY = (100, 100, 100)
GREEN = (0, 200, 0)
BLUE = (0, 0, 200)
PURPLE = (150, 0, 150)
YELLOW = (255, 255, 0)
LIGHT_BLUE = (100, 100, 255)
DARK_GRAY = (50, 50, 50)

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Roguelike Game")
clock = pygame.time.Clock()


# Функция безопасной загрузки изображения
def load_image(path, size=None):
    try:
        image = pygame.image.load(path).convert_alpha()
        if size:
            image = pygame.transform.scale(image, size)
        return image
    except Exception:
        print(f"Warning: could not load image {path}")
        return None


# Загрузка изображений
heart_img = load_image("heart.png")
half_heart_img = load_image("half_heart.png")
floor_img = load_image("floor.png")
door_img = load_image("door.png")
coin_img = load_image("coin.png", (TILE_SIZE // 2, TILE_SIZE // 2))
bullet_img = load_image("bullet.png", (8, 8))

# Загрузка изображений персонажей (если есть)
player_img = load_image("player.png", (TILE_SIZE // 2, TILE_SIZE // 2))
enemy_img = load_image("enemy.png", (TILE_SIZE // 2, TILE_SIZE // 2))
boss_img = load_image("boss.png", (TILE_SIZE, TILE_SIZE))

# Группы спрайтов
all_sprites = pygame.sprite.Group()
walls = pygame.sprite.Group()
bullets = pygame.sprite.Group()
enemies = pygame.sprite.Group()
coins = pygame.sprite.Group()


# Состояние улучшений игрока (сохраняется между уровнями)
class PlayerUpgrades:
    def __init__(self):
        self.multishot_level = 0
        self.has_homing = False
        self.health_level = 0


player_upgrades = PlayerUpgrades()


# Класс игрока
class Player(pygame.sprite.Sprite):
    def __init__(self, pos, upgrades):
        super().__init__(all_sprites)
        if player_img:
            self.image = player_img
        else:
            self.image = pygame.Surface((TILE_SIZE // 2, TILE_SIZE // 2))
            self.image.fill(BLUE)
        self.rect = self.image.get_rect(center=pos)
        self.speed = 4

        # Здоровье (базовое 3 сердца + бонусы)
        self.base_health = 6  # 6 половинок = 3 сердца
        self.health_bonus = upgrades.health_level  # каждая покупка +1 половинка
        self.max_health = self.base_health + self.health_bonus
        self.health = self.max_health

        # Применяем улучшения
        self.multishot_level = upgrades.multishot_level
        self.has_homing = upgrades.has_homing
        self.coins = 0
        # Время последнего выстрела
        self.last_shot = 0
        self.shot_delay = 300  # задержка между выстрелами в мс

    def update(self):
        keys = pygame.key.get_pressed()
        dx = dy = 0
        # Движение на WASD
        if keys[pygame.K_a]:
            dx = -self.speed
        if keys[pygame.K_d]:
            dx = self.speed
        if keys[pygame.K_w]:
            dy = -self.speed
        if keys[pygame.K_s]:
            dy = self.speed
        # Нормализуем диагональное движение
        if dx != 0 and dy != 0:
            dx *= 0.7071;
            dy *= 0.7071
        # Попытка перемещения с проверкой столкновений
        self.move(dx, dy)

        # Сбор монет
        coins_collected = pygame.sprite.spritecollide(self, coins, True)
        for coin in coins_collected:
            self.coins += 1

        # Удерживаем игрока в границах окна
        if self.rect.left < 0:   self.rect.left = 0
        if self.rect.right > SCREEN_WIDTH: self.rect.right = SCREEN_WIDTH
        # Верхняя граница на 40px опущена (т.к. HUD занимает верх)
        if self.rect.top < 40:   self.rect.top = 40
        if self.rect.bottom > SCREEN_HEIGHT: self.rect.bottom = SCREEN_HEIGHT

    def move(self, dx, dy):
        if dx != 0:
            self.rect.x += int(dx)
            if pygame.sprite.spritecollideany(self, walls):
                self.rect.x -= int(dx)
        if dy != 0:
            self.rect.y += int(dy)
            if pygame.sprite.spritecollideany(self, walls):
                self.rect.y -= int(dy)

    def shoot(self, direction):
        # Если нет направления стрельбы (0-вектор), не стреляем
        if direction.length_squared() == 0:
            return

        # Проверяем задержку между выстрелами
        now = pygame.time.get_ticks()
        if now - self.last_shot < self.shot_delay:
            return
        self.last_shot = now

        # Основной снаряд
        Bullet(self.rect.center, direction, self.has_homing)

        # Мультивыстрел
        if self.multishot_level > 0:
            # Угол между пулями (в градусах)
            angle_step = 10
            # Количество дополнительных пуль с каждой стороны
            bullets_per_side = self.multishot_level

            # Создаем пули справа и слева от основного направления
            for i in range(1, bullets_per_side + 1):
                # Пули справа
                angle = i * angle_step
                dir_right = direction.rotate(angle)
                Bullet(self.rect.center, dir_right, self.has_homing)

                # Пули слева
                dir_left = direction.rotate(-angle)
                Bullet(self.rect.center, dir_left, self.has_homing)

    def add_health(self):
        """Добавляет половинку сердца к максимальному здоровью"""
        self.health_bonus += 1
        self.max_health = self.base_health + self.health_bonus
        self.health = min(self.health + 1, self.max_health)


# Класс снаряда
class Bullet(pygame.sprite.Sprite):
    def __init__(self, pos, direction, homing=False):
        super().__init__(all_sprites, bullets)
        if bullet_img:
            self.image = bullet_img
        else:
            self.image = pygame.Surface((8, 8))
            self.image.fill(RED)
        self.rect = self.image.get_rect(center=pos)
        self.velocity = pygame.math.Vector2(direction) * 10
        self.homing = homing
        self.target = None

    def update(self):
        if self.homing:
            # Находим ближайшего живого врага
            if not self.target or not self.target.alive():
                if enemies:
                    self.target = min(enemies, key=lambda e:
                    (self.rect.centerx - e.rect.centerx) ** 2 + (self.rect.centery - e.rect.centery) ** 2
                                      )
            # Наводимся на цель
            if self.target and self.target.alive():
                to_enemy = pygame.math.Vector2(self.target.rect.center) - pygame.math.Vector2(self.rect.center)
                if to_enemy.length() != 0:
                    self.velocity = to_enemy.normalize() * 10
        # Движение снаряда
        self.rect.x += int(self.velocity.x)
        self.rect.y += int(self.velocity.y)
        # Если вышел за пределы, уничтожаем снаряд
        if (self.rect.right < 0 or self.rect.left > SCREEN_WIDTH or
                self.rect.bottom < 40 or self.rect.top > SCREEN_HEIGHT):
            self.kill()
            return
        # Столкновение со стеной
        if pygame.sprite.spritecollideany(self, walls):
            self.kill()
            return
        # Попадание по врагу
        hit = pygame.sprite.spritecollideany(self, enemies)
        if hit:
            hit.health -= 1
            if hit.health <= 0:
                # Создаем монетку на месте врага
                Coin(hit.rect.center)
                hit.kill()
                player.coins += 1
            self.kill()


# Класс монетки
class Coin(pygame.sprite.Sprite):
    def __init__(self, pos):
        super().__init__(all_sprites, coins)
        if coin_img:
            self.image = coin_img
        else:
            self.image = pygame.Surface((TILE_SIZE // 2, TILE_SIZE // 2))
            self.image.fill(YELLOW)
        self.rect = self.image.get_rect(center=pos)


# Класс врага
class Enemy(pygame.sprite.Sprite):
    def __init__(self, pos, is_boss=False):
        super().__init__(all_sprites, enemies)
        self.is_boss = is_boss

        if is_boss and boss_img:
            self.image = boss_img
            self.rect = self.image.get_rect(center=pos)
            self.health = 10
            self.speed = 2
        elif enemy_img:
            self.image = enemy_img
            self.rect = self.image.get_rect(center=pos)
            self.health = 1
            self.speed = 2
        else:
            size = (TILE_SIZE, TILE_SIZE) if is_boss else (TILE_SIZE // 2, TILE_SIZE // 2)
            color = PURPLE if is_boss else GREEN
            self.image = pygame.Surface(size)
            self.image.fill(color)
            self.rect = self.image.get_rect(center=pos)
            self.health = 10 if is_boss else 1
            self.speed = 2

        # Для ИИ
        self.stuck_timer = 0
        self.stuck_direction = None
        self.last_position = pygame.math.Vector2(pos)
        self.activation_time = pygame.time.get_ticks() + 500  # активируются через 0,5 секунды

    def update(self):
        # Проверяем, активирован ли враг
        if pygame.time.get_ticks() < self.activation_time:
            return

        # Проверяем, не застрял ли враг
        current_pos = pygame.math.Vector2(self.rect.center)
        if (current_pos - self.last_position).length() < 1:
            self.stuck_timer += 1
            if self.stuck_timer > 5:  # Застрял на 30 кадров
                # Пытаемся сменить направление
                self.stuck_direction = pygame.math.Vector2(random.uniform(-1, 1), random.uniform(-1, 1)).normalize()
        else:
            self.stuck_timer = 0
            self.stuck_direction = None

        self.last_position = current_pos

        # Если застряли, двигаемся в случайном направлении
        if self.stuck_direction:
            self.rect.x += int(self.stuck_direction.x * self.speed)
            self.rect.y += int(self.stuck_direction.y * self.speed)

            # Проверяем столкновение со стенами
            if pygame.sprite.spritecollideany(self, walls):
                self.rect.x -= int(self.stuck_direction.x * self.speed)
                self.rect.y -= int(self.stuck_direction.y * self.speed)
                # Создаем новое направление
                self.stuck_direction = pygame.math.Vector2(random.uniform(-1, 1), random.uniform(-1, 1)).normalize()
        # Иначе преследуем игрока
        elif player.alive():
            # Рассчитываем направление к игроку
            dx = player.rect.centerx - self.rect.centerx
            dy = player.rect.centery - self.rect.centery
            distance = max(1, (dx ** 2 + dy ** 2) ** 0.5)  # избегаем деления на ноль

            # Нормализуем вектор направления
            dx /= distance
            dy /= distance

            # Двигаем врага к игроку
            self.rect.x += int(dx * self.speed)
            self.rect.y += int(dy * self.speed)

            # Проверяем столкновение со стенами
            if pygame.sprite.spritecollideany(self, walls):
                self.rect.x -= int(dx * self.speed)
                self.rect.y -= int(dy * self.speed)
                # Помечаем, что застряли
                self.stuck_timer = 30

        # Столкновение с игроком
        if pygame.sprite.collide_rect(self, player):
            player.health -= 2 if self.is_boss else 1
            if not self.is_boss:
                # Создаем монетку на месте врага
                Coin(self.rect.center)
                self.kill()


# Класс прямоугольной комнаты
class Room:
    def __init__(self, x, y, w, h):
        self.x1 = x;
        self.y1 = y
        self.x2 = x + w;
        self.y2 = y + h

    @property
    def center(self):
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    def intersect(self, other):
        return self.x1 < other.x2 and self.x2 > other.x1 and self.y1 < other.y2 and self.y2 > other.y1


# Функции для создания коридоров
def create_h_corridor(x1, x2, y, dungeon_map):
    for x in range(min(x1, x2), max(x1, x2) + 1):
        for dy in range(3):  # ширина коридора 3 клетки
            if 0 <= y + dy < MAP_HEIGHT:
                dungeon_map[x][y + dy] = 0


def create_v_corridor(y1, y2, x, dungeon_map):
    for y in range(min(y1, y2), max(y1, y2) + 1):
        for dx in range(3):
            if 0 <= x + dx < MAP_WIDTH:
                dungeon_map[x + dx][y] = 0


# Генерация случайного уровня (список комнат + соединения)
def generate_dungeon():
    # Изначально вся карта заполнена стенами (1)
    dungeon_map = [[1] * MAP_HEIGHT for _ in range(MAP_WIDTH)]
    rooms = []
    for _ in range(5):
        w, h = random.randint(4, 8), random.randint(4, 8)
        x = random.randint(1, MAP_WIDTH - w - 1)
        y = random.randint(1, MAP_HEIGHT - h - 1)
        new_room = Room(x, y, w, h)
        # Пропускаем пересекающиеся комнаты
        if any(new_room.intersect(o) for o in rooms):
            continue
        # Вырезаем комнату (пол = 0)
        for i in range(new_room.x1, new_room.x2):
            for j in range(new_room.y1, new_room.y2):
                dungeon_map[i][j] = 0
        # Если есть предыдущая комната, соединяем ее с новой
        if rooms:
            prev_center = rooms[-1].center
            new_center = new_room.center
            # Случайный порядок: сначала горизонталь, потом вертикаль, или наоборот
            if random.choice([True, False]):
                create_h_corridor(prev_center[0], new_center[0], prev_center[1], dungeon_map)
                create_v_corridor(prev_center[1], new_center[1], new_center[0], dungeon_map)
            else:
                create_v_corridor(prev_center[1], new_center[1], prev_center[0], dungeon_map)
                create_h_corridor(prev_center[0], new_center[0], new_center[1], dungeon_map)
        rooms.append(new_room)
    return dungeon_map, rooms


# Отрисовка пола и стен, возвращает список координат всех «полых» клетокdef draw_floor_and_walls(dungeon_map):
    walls.empty()
    floor_positions = []
    for x in range(MAP_WIDTH):
        for y in range(MAP_HEIGHT):
            tile = dungeon_map[x][y]
            screen_pos = (x * TILE_SIZE, y * TILE_SIZE + 40)  # +40px для HUD сверху
            if tile == 0:
                floor_positions.append((x, y))
                if floor_img:
                    screen.blit(floor_img, screen_pos)
                else:
                    pygame.draw.rect(screen, GRAY, (*screen_pos, TILE_SIZE, TILE_SIZE))
            else:
                pygame.draw.rect(screen, BLACK, (*screen_pos, TILE_SIZE, TILE_SIZE))
                wall_sprite = pygame.sprite.Sprite()
                wall_sprite.image = pygame.Surface((TILE_SIZE, TILE_SIZE))
                wall_sprite.image.fill(BLACK)
                wall_sprite.rect = wall_sprite.image.get_rect(topleft=screen_pos)
                walls.add(wall_sprite)
    return floor_positions


# Создание мини-карты (каждая клетка рисуется белым, если пол)
def create_minimap(dungeon_map):
    scale = 3
    mini = pygame.Surface((MAP_WIDTH * scale, MAP_HEIGHT * scale))
    mini.fill(BLACK)
    for x in range(MAP_WIDTH):
        for y in range(MAP_HEIGHT):
            if dungeon_map[x][y] == 0:
                pygame.draw.rect(mini, WHITE, (x * scale, y * scale, scale, scale))
    return mini


# Спавн врагов: случайно по количеству в случайных комнатах
def spawn_enemies(num, rooms):
    for _ in range(num):
        room = random.choice(rooms)
        x = random.randint(room.x1 + 1, room.x2 - 2)
        y = random.randint(room.y1 + 1, room.y2 - 2)
        pos = (x * TILE_SIZE + TILE_SIZE // 2, y * TILE_SIZE + TILE_SIZE // 2 + 40)
        # Последняя комната - босс
        if room == rooms[-1] and _ == num - 1:
            Enemy(pos, is_boss=True)
        else:
            Enemy(pos)


# Режим магазина: выбор улучшений
def run_shop():
    shop_open = True
    font = pygame.font.SysFont(None, 24)
    while shop_open:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit();
                sys.exit()
            if event.type == pygame.KEYDOWN:
                # Мультивыстрел (стоимость 5 + 5 * текущий уровень)
                multishot_cost = 5 + 5 * player_upgrades.multishot_level
                if event.key == pygame.K_1 and player.coins >= multishot_cost:
                    player_upgrades.multishot_level += 1
                    player.multishot_level += 1
                    player.coins -= multishot_cost

                # Самонаводящиеся пули (стоимость 30 монет)
                if event.key == pygame.K_2 and player.coins >= 30 and not player_upgrades.has_homing:
                    player_upgrades.has_homing = True
                    player.has_homing = True
                    player.coins -= 30

                # Улучшение здоровья (стоимость 10 монет)
                if event.key == pygame.K_3 and player.coins >= 10:
                    player_upgrades.health_level += 1
                    player.add_health()
                    player.coins -= 10

                # Выход из магазина
                if event.key == pygame.K_RETURN:
                    shop_open = False

        # Отображение магазина
        screen.fill(BLACK)
        texts = [
            f"Shop - Coins: {player.coins}",
            f"1: Мульти выстрел (Level {player_upgrades.multishot_level + 1}) - {5 + 5 * player_upgrades.multishot_level} coins",
            "2: Самонаводящийся пули - 30 coins" + (" [PURCHASED]" if player_upgrades.has_homing else ""),
            "3: Улучшение здоровья (+0.5 heart) - 10 coins",
            "Enter: Выйти с магазина"
        ]

        for i, t in enumerate(texts):
            color = WHITE
            if i == 1 and player.coins < (5 + 5 * player_upgrades.multishot_level):
                color = GRAY
            elif i == 2 and (player_upgrades.has_homing or player.coins < 30):
                color = GRAY
            elif i == 3 and player.coins < 10:
                color = GRAY

            img = font.render(t, True, color)
            screen.blit(img, (50, 50 + i * 30))

        pygame.display.flip()
        clock.tick(FPS)


# Отрисовка индикатора здоровья (сердечки)
def draw_health():
    hearts = player.health // 2
    half = player.health % 2
    for i in range(hearts):
        pos = (5 + i * (TILE_SIZE + 2), 5)
        if heart_img:
            screen.blit(heart_img, pos)
        else:
            pygame.draw.rect(screen, RED, (*pos, TILE_SIZE, TILE_SIZE))
    if half:
        pos = (5 + hearts * (TILE_SIZE + 2), 5)
        if half_heart_img:
            screen.blit(half_heart_img, pos)
        else:
            pygame.draw.rect(screen, DARKRED, (*pos, TILE_SIZE, TILE_SIZE))

    # Отображение монет
    font = pygame.font.SysFont(None, 24)
    coins_text = font.render(f"монеты: {player.coins}", True, WHITE)
    screen.blit(coins_text, (SCREEN_WIDTH - 150, 5))
    if coin_img:
        screen.blit(coin_img, (SCREEN_WIDTH - 180, 5))

    # Отображение уровня мультивыстрела
    if player.multishot_level > 0:
        multishot_text = font.render(f"мульти выстрел: Lvl {player.multishot_level}", True, WHITE)
        screen.blit(multishot_text, (SCREEN_WIDTH // 2 - 70, 5))

    # Отображение самонаводящихся пуль
    if player.has_homing:
        homing_text = font.render("самонаводящийся пули: ON", True, WHITE)
        screen.blit(homing_text, (SCREEN_WIDTH // 2 - 70, 30))


# Экран "Game Over"
def show_game_over():
    game_over = True
    font_large = pygame.font.SysFont(None, 72)
    font_medium = pygame.font.SysFont(None, 36)

    # Кнопки
    restart_button = pygame.Rect(SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2, 300, 50)
    quit_button = pygame.Rect(SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 + 70, 300, 50)

    while game_over:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if restart_button.collidepoint(event.pos):
                    # Очищаем все группы спрайтов перед рестартом
                    all_sprites.empty()
                    enemies.empty()
                    bullets.empty()
                    walls.empty()
                    coins.empty()
                    return "restart"
                elif quit_button.collidepoint(event.pos):
                    pygame.quit()
                    sys.exit()

        # Отрисовка
        screen.fill(BLACK)

        # Заголовок
        game_over_text = font_large.render("GAME OVER", True, RED)
        screen.blit(game_over_text, (SCREEN_WIDTH // 2 - game_over_text.get_width() // 2, SCREEN_HEIGHT // 4))

        # Статистика
        stats_text = font_medium.render(f"Level Reached: {level}", True, WHITE)
        screen.blit(stats_text, (SCREEN_WIDTH // 2 - stats_text.get_width() // 2, SCREEN_HEIGHT // 3))

        # Кнопки
        pygame.draw.rect(screen, LIGHT_BLUE, restart_button)
        pygame.draw.rect(screen, DARKRED, quit_button)

        restart_text = font_medium.render("Restart Game", True, WHITE)
        quit_text = font_medium.render("Quit", True, WHITE)

        screen.blit(restart_text, (restart_button.centerx - restart_text.get_width() // 2,
                                   restart_button.centery - restart_text.get_height() // 2))
        screen.blit(quit_text, (quit_button.centerx - quit_text.get_width() // 2,
                                quit_button.centery - quit_text.get_height() // 2))

        pygame.display.flip()
        clock.tick(FPS)

# Главный цикл игры
def main():
    global player, player_upgrades, level

    running = True

    while running:
        level = 1
        player_upgrades = PlayerUpgrades()  # Сброс улучшений

        # Основной игровой цикл (уровни)
        while running:
            dungeon_map, rooms = generate_dungeon()

            # Создаем фон для отрисовки
            background = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            background.fill(BLACK)

            # Отрисовка фона и стен один раз
            floor_positions = []
            for x in range(MAP_WIDTH):
                for y in range(MAP_HEIGHT):
                    tile = dungeon_map[x][y]
                    screen_pos = (x * TILE_SIZE, y * TILE_SIZE + 40)
                    if tile == 0:
                        floor_positions.append((x, y))
                        if floor_img:
                            background.blit(floor_img, screen_pos)
                        else:
                            pygame.draw.rect(background, GRAY, (*screen_pos, TILE_SIZE, TILE_SIZE))
                    else:
                        pygame.draw.rect(background, BLACK, (*screen_pos, TILE_SIZE, TILE_SIZE))

            # Создаем стены для коллизий
            walls.empty()
            for x in range(MAP_WIDTH):
                for y in range(MAP_HEIGHT):
                    if dungeon_map[x][y] == 1:
                        wall_sprite = pygame.sprite.Sprite()
                        wall_sprite.image = pygame.Surface((TILE_SIZE, TILE_SIZE))
                        wall_sprite.image.fill(BLACK)
                        wall_sprite.rect = wall_sprite.image.get_rect(topleft=(x * TILE_SIZE, y * TILE_SIZE + 40))
                        walls.add(wall_sprite)

            # Создаем игрока в центре первой комнаты
            start = rooms[0].center
            player = Player((start[0] * TILE_SIZE + TILE_SIZE // 2,
                             start[1] * TILE_SIZE + TILE_SIZE // 2 + 40), player_upgrades)

            # Создаем выход (дверь) в центре последней комнаты
            last = rooms[-1].center
            door = pygame.sprite.Sprite()
            door.image = door_img if door_img else pygame.Surface((TILE_SIZE, TILE_SIZE))
            if not door_img: door.image.fill(DARKRED)
            door.rect = door.image.get_rect()
            door.rect.topleft = (last[0] * TILE_SIZE, last[1] * TILE_SIZE + 40)
            all_sprites.add(door)

            # Генерируем миникарту
            minimap = create_minimap(dungeon_map)

            # Спавн врагов в количестве level+2
            spawn_enemies(level + 2, rooms)

            # Спавн монет в комнатах
            for room in rooms:
                if room != rooms[0] and room != rooms[-1]:  # не в первой и не в последней
                    for _ in range(random.randint(1, 3)):
                        x = random.randint(room.x1 + 1, room.x2 - 2)
                        y = random.randint(room.y1 + 1, room.y2 - 2)
                        pos = (x * TILE_SIZE + TILE_SIZE // 2, y * TILE_SIZE + TILE_SIZE // 2 + 40)
                        Coin(pos)

            level_complete = False
            while not level_complete and player.health > 0:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False;
                        level_complete = True
                    if event.type == pygame.KEYDOWN:
                        # Стрельба по стрелкам
                        if event.key == pygame.K_UP:
                            player.shoot(pygame.math.Vector2(0, -1))
                        if event.key == pygame.K_DOWN:
                            player.shoot(pygame.math.Vector2(0, 1))
                        if event.key == pygame.K_LEFT:
                            player.shoot(pygame.math.Vector2(-1, 0))
                        if event.key == pygame.K_RIGHT:
                            player.shoot(pygame.math.Vector2(1, 0))

                # Обновление всех спрайтов
                all_sprites.update()

                # Отрисовка
                screen.blit(background, (0, 0))  # Рисуем заранее подготовленный фон
                all_sprites.draw(screen)  # Рисуем все спрайты поверх фона
                screen.blit(minimap, (SCREEN_WIDTH - minimap.get_width() - 5, 5))
                draw_health()
                pygame.display.flip()
                clock.tick(FPS)

                # Проверка выхода (столкновения игрока с дверью)
                if pygame.sprite.collide_rect(player, door):
                    level_complete = True

            # Если игрок погиб, показываем экран "Game Over"
            if player.health <= 0:
                choice = show_game_over()
                if choice == "restart":
                    break  # Выходим из цикла уровней, начнем новую игру
                else:
                    running = False
                    break
            else:
                # После каждого второго уровня – магазин
                if level % 2 == 0:
                    run_shop()
                level += 1

            # Очищаем группы для следующего уровня
            all_sprites.empty()
            enemies.empty()
            bullets.empty()
            walls.empty()
            coins.empty()


    pygame.quit()


if __name__ == "__main__":
    main()