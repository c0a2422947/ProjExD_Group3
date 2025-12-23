import os
import pygame as pg
import sys
import random
import subprocess

# --- 設定（数字を変えるとゲームバランスが変わります） ---
WIDTH = 600             # 画面の幅
HEIGHT = 800            # 画面の高さ
FPS = 60                # 1秒間のコマ数
GATES_PER_ROUND = 7     # 1周で出るゲートの数
GATE_SPAWN_TIME = 90    # ゲートが出る間隔（フレーム数。60で約1秒）

# 色の定義
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (0, 100, 255)
RED = (255, 50, 50)
PURPLE = (200, 0, 200)

# ゲームの状態（わかりやすいように文字列で管理）
STATE_RUNNING = "RUNNING" # 走るパート
STATE_BOSS = "BOSS"       # ボス戦パート
STATE_RESULT = "RESULT"   # 結果パート

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FIG_DIR = os.path.join(BASE_DIR, "fig")

class Koukaton(pg.sprite.Sprite):
    """自軍（こうかとん）を管理するクラス"""
    def __init__(self):
        super().__init__()
        # 画像の読み込み（失敗したら赤色の四角にする）
        self.image = pg.Surface((50, 50))
        self.image.fill(RED)
        try:
            self.image = pg.image.load("fig/3.png")
            self.image = pg.transform.scale(self.image, (50, 50))
        except:
            pass # 画像がなくてもエラーにしない

        self.rect = self.image.get_rect()
        self.reset_position() # 初期位置へ
        
        self.speed = 8
        self.count = 1  # 自軍の数
        self.swarm_offsets = [] # 群衆の座標リスト
        self.small_image = pg.transform.scale(self.image, (30, 30))

    def reset_position(self):
        """画面の下側・中央に戻す"""
        self.rect.centerx = WIDTH // 2
        self.rect.bottom = HEIGHT - 100

    def update(self, game_state):
        """毎フレームの処理"""
        # ボス戦のとき：自動で画面中央へ寄せる
        if game_state == STATE_BOSS:
            if self.rect.centerx < WIDTH // 2:
                self.rect.centerx += 2
            elif self.rect.centerx > WIDTH // 2:
                self.rect.centerx -= 2
            return

        # 通常のとき：キーボードで左右移動
        keys = pg.key.get_pressed()
        if keys[pg.K_LEFT]:
            self.rect.x -= self.speed
        if keys[pg.K_RIGHT]:
            self.rect.x += self.speed
        
        # 画面からはみ出さないようにする
        if self.rect.left < 0: self.rect.left = 0
        if self.rect.right > WIDTH: self.rect.right = WIDTH

        # 群衆の見た目を更新
        self.update_swarm_positions()

    def update_swarm_positions(self):
        """自軍の数に合わせて、わらわら表示させる座標を決める"""
        display_count = self.count
        if display_count > 200: # 処理落ち防止のため上限を設定
            display_count = 200

        # 足りない分を追加
        while len(self.swarm_offsets) < display_count:
            # 数が増えるほど広がる計算（mathを使わず簡易的に）
            spread = 20 + (display_count // 5) 
            rx = random.randint(-spread, spread)
            ry = random.randint(-spread, spread)
            self.swarm_offsets.append((rx, ry))
        
        # 多すぎる分を削除
        while len(self.swarm_offsets) > display_count:
            self.swarm_offsets.pop()

    def apply_effect(self, operator, value):
        """ゲートを通ったときの計算"""
        if operator == "+":
            self.count += value
        elif operator == "x":
            self.count *= value
        elif operator == "-":
            self.count -= value
        elif operator == "/":
            self.count //= value # 割り算（整数）
        
        if self.count < 0:
            self.count = 0

    def draw_swarm(self, screen):
        """群衆を描画する"""
        if self.count <= 0: return
        # offsetsに保存されたズレを使って描画
        for ox, oy in self.swarm_offsets:
            draw_x = self.rect.centerx + ox - 15
            draw_y = self.rect.centery + oy - 15
            screen.blit(self.small_image, (draw_x, draw_y))


class Gate(pg.sprite.Sprite):
    """通ると数が増減するゲートのクラス"""
    def __init__(self, x, y, width, height, batch_id):
        super().__init__()
        self.batch_id = batch_id # 左右ペアを識別するID
        
        # ランダムに計算の種類を決める
        self.operator = random.choice(["+", "x", "-", "+", "x"]) 
        if self.operator == "+" or self.operator == "-":
            self.value = random.randint(10, 50)
        else: 
            self.value = random.randint(1, 3)

        # 良い効果なら青、悪い効果なら赤
        is_good = (self.operator == "+" or self.operator == "x")
        color = BLUE if is_good else RED
        
        # 画像を作る
        self.image = pg.Surface((width, height))
        self.image.fill(color)
        self.image.set_alpha(150) # 半透明にする

        # 文字を描く
        font = pg.font.SysFont("arial", 40, bold=True)
        text = font.render(f"{self.operator}{self.value}", True, WHITE)
        # 真ん中に配置
        text_rect = text.get_rect(center=(width // 2, height // 2))
        self.image.blit(text, text_rect)
        
        # 白い枠線
        pg.draw.rect(self.image, WHITE, (0, 0, width, height), 5)

        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y

    def update(self, game_state):
        """下に落ちる処理"""
        self.rect.y += 5
        # 画面外に出たら消える
        if self.rect.top > HEIGHT:
            self.kill()


class Enemy(pg.sprite.Sprite):
    """ボスのクラス"""
    def __init__(self, level=1):
        super().__init__()
        self.image = pg.Surface((150, 150))
        # 画像読み込み
        try:
            img = pg.image.load("fig/21.png") # ボス画像
            self.image = pg.transform.scale(img, (150, 150))
        except:
            self.image.fill(PURPLE) # 画像がなければ紫の四角
            font = pg.font.SysFont(None, 80)
            text = font.render("BOSS", True, WHITE)
            self.image.blit(text, (10, 50))
            pg.draw.rect(self.image, WHITE, (0,0,150,150), 5)

        self.rect = self.image.get_rect()
        self.rect.centerx = WIDTH // 2
        self.rect.bottom = -50 
        
        # レベルに応じてHPを決める（周回するたびに強くなる）
        min_hp = 500 + (level-1) * 500
        max_hp = 1000 + (level-1) * 10000
        self.hp = random.randint(min_hp, max_hp)

    def update(self, screen: pg.Surface):
        """下に降りてくる処理"""
        if self.rect.top < HEIGHT: 
            self.rect.y += 4

    def draw_hp(self, screen, font):
        """HPを表示する"""
        text = font.render(f"BOSS HP: {self.hp}", True, RED)
        # 背景を黒くして見やすくする
        bg_rect = text.get_rect(center=(self.rect.centerx, self.rect.top - 20))
        pg.draw.rect(screen, BLACK, bg_rect)
        screen.blit(text, bg_rect)

class Advertisement:
    """
    Advertisement の Docstring
    """
    def __init__(self):
        self.img = pg.Surface((WIDTH//2, HEIGHT))  #広告を載せる用の背景
        self.img.fill((128, 128, 128))
        self.img.set_alpha(200)
        try:
            self.imgx = pg.image.load(os.path.join(FIG_DIR, "bb.png"))
            self.imgx = pg.transform.rotozoom(self.imgx, 0, 0.25)
        except:
            self.surx = pg.Surface((64, 64))
            self.surx.fill((255, 0, 0))

        self.imgx_rct = self.imgx.get_rect()

        self.surx = pg.Surface((64, 64))
        self.surx.fill((255, 0, 0))
        self.surx_rct = self.surx.get_rect()
        self.surx_rct.topleft = ((WIDTH/4 + WIDTH/2) - 72, 0)

    def update(self, screen: pg.Surface):
        """
        update の Docstring
        
        :param self: 説明
        :param screen: 説明
        :type screen: pg.Surface
        """
        screen.blit(self.img, [WIDTH/4, 0])
        screen.blit(self.surx, self.surx_rct)
        screen.blit(self.imgx, self.surx_rct)

def main():
    pg.init()
    screen = pg.display.set_mode((WIDTH, HEIGHT))
    pg.display.set_caption("ラストコカー・コカー")
    clock = pg.time.Clock()
    
    font = pg.font.SysFont("mspgothic", 30)
    big_font = pg.font.SysFont("arial", 60, bold=True)
    advertisement = Advertisement()

    # ゲームの状態を保持する変数群（初期値）
    def get_initial_state(current_level=1, current_count=1):
        p = Koukaton()
        p.count = current_count
        e = Enemy(current_level)
        all_spr = pg.sprite.Group()
        all_spr.add(p)
        return {
            "player": p,
            "enemy": e,
            "gates": pg.sprite.Group(),
            "all_sprites": all_spr,
            "level": current_level,
            "game_state": STATE_RUNNING,
            "spawned_gates": 0,
            "passed_gates": 0,
            "gate_timer": 0,
            "batch_counter": 0,
            "result_start_time": 0,
            "is_win": False,
        }

    # 初回スタート
    g = get_initial_state()

    while True:
        # --- イベント処理 ---
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
                sys.exit()
            if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                if advertisement.surx_rct.collidepoint(event.pos):
                    # ×ボタンでゲームリスタート
                    g = get_initial_state()

        # 変数が使いやすいように参照を抽出
        player = g["player"]
        enemy = g["enemy"]
        gates = g["gates"]
        all_sprites = g["all_sprites"]

        # --- ゲートを出す処理 ---
        if g["game_state"] == STATE_RUNNING:
            g["gate_timer"] += 1
            if g["gate_timer"] > GATE_SPAWN_TIME and g["spawned_gates"] < GATES_PER_ROUND:
                g["gate_timer"] = 0
                g["batch_counter"] += 1
                
                gl = Gate(5, -100, WIDTH//2 - 10, 80, g["batch_counter"])
                gr = Gate(WIDTH//2 + 5, -100, WIDTH//2 - 10, 80, g["batch_counter"])
                gates.add(gl, gr)
                all_sprites.add(gl, gr)
                g["spawned_gates"] += 1

        # --- ボス出現チェック ---
        if g["game_state"] == STATE_RUNNING:
            if g["passed_gates"] >= GATES_PER_ROUND or (g["spawned_gates"] >= GATES_PER_ROUND and len(gates) == 0):
                g["game_state"] = STATE_BOSS
                all_sprites.add(enemy)

        # --- 更新処理 ---
        if g["game_state"] in [STATE_RUNNING, STATE_BOSS]:
            player.update(g["game_state"])
            all_sprites.update(g["game_state"])
        
        # --- 当たり判定（ゲート） ---
        if g["game_state"] == STATE_RUNNING:
            hits = pg.sprite.spritecollide(player, gates, True)
            if hits:
                g["passed_gates"] += 1
                for gate in hits:
                    player.apply_effect(gate.operator, gate.value)
                    for other in gates:
                        if other.batch_id == gate.batch_id:
                            other.kill()

        # --- 当たり判定（ボス） ---
        if g["game_state"] == STATE_BOSS:
            if pg.sprite.collide_rect(player, enemy):
                g["game_state"] = STATE_RESULT
                g["result_start_time"] = pg.time.get_ticks()
                g["is_win"] = player.count >= enemy.hp

        # --- 全滅判定 ---
        if g["game_state"] != STATE_RESULT and player.count <= 0:
            g["game_state"] = STATE_RESULT
            g["result_start_time"] = pg.time.get_ticks()
            g["is_win"] = False

        # --- 描画処理 ---
        screen.fill(BLACK)
        pg.draw.line(screen, (50, 50, 50), (WIDTH//2, 0), (WIDTH//2, HEIGHT), 2)
        all_sprites.draw(screen)
        player.draw_swarm(screen)

        info_text = font.render(f"自軍: {player.count} (Lv.{g['level']})", True, WHITE)
        screen.blit(info_text, (player.rect.centerx + 60, player.rect.bottom))
        
        if g["game_state"] == STATE_RUNNING:
            ratio = g["passed_gates"] / GATES_PER_ROUND
            pg.draw.rect(screen, WHITE, (100, 20, 400, 20), 2)
            pg.draw.rect(screen, BLUE, (100, 20, 400 * min(ratio, 1.0), 20))

        if enemy.alive() and (g["game_state"] in [STATE_BOSS, STATE_RESULT]):
            enemy.draw_hp(screen, font)

        # --- 結果画面 ---
        if g["game_state"] == STATE_RESULT:
            overlay = pg.Surface((WIDTH, HEIGHT))
            overlay.fill(BLACK)
            overlay.set_alpha(150)
            screen.blit(overlay, (0, 0))

            if g["is_win"]:
                msg = big_font.render("YOU WIN!", True, BLUE)
                detail = font.render(f"残り: {player.count - enemy.hp}ひき", True, WHITE)
                screen.blit(msg, (WIDTH//2 - 150, HEIGHT//2 - 50))
                screen.blit(detail, (WIDTH//2 - 100, HEIGHT//2 + 20))
                
                if pg.time.get_ticks() - g["result_start_time"] > 3000:
                    # 次のレベルへ
                    new_count = max(1, player.count - enemy.hp)
                    g = get_initial_state(g["level"] + 1, new_count)
            else:
                msg = big_font.render("GAME OVER", True, RED)
                screen.blit(msg, (WIDTH//2 - 150, HEIGHT//2 - 50))
                advertisement.update(screen)
                # 負けた時は広告を表示して停止、またはクリック待ちにする
                # (ここでは元のロジック通り20秒待機か×で終了)

        pg.display.update()
        clock.tick(FPS)

if __name__ == "__main__":
    main()