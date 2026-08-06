"""🏰 Dungeon Crawler - A tiny text adventure game.
   Run it with: python3 game.py
"""

import random


def new_game():
    """Return the initial game state."""
    return {
        "hp": 100,
        "attack": 25,
        "defense": 10,
        "gold": 0,
        "exp": 0,
        "level": 1,
        "floor": 1,
        "max_hp": 100,
        "inventory": [],
    }


def choose_character(player):
    """Pick a starting character class."""
    print("\n🎭 Choose your hero:")
    print("  [1] 🗡️ Knight     — High HP and defense")
    print("  [2] ⚔️ Rogue      — Balanced offense & gold finders")
    print("  [3] 🔮 Mage       — Weak but deadly magic")

    roles = {
        "1": {"hp": 120, "attack": 15, "defense": 25},
        "2": {"hp": 90, "attack": 30, "defense": 12},
        "3": {"hp": 70, "attack": 45, "defense": 8},
    }

    while True:
        choice = input("\n> ").strip()
        if choice in roles:
            for key in ("hp", "attack", "defense"):
                player[key] += roles[choice][key] - 10
            break
        else:
            print("Unknown choice. Starting as a balanced character.")


def encounter(floor):
    """Generate an enemy based on the floor."""
    floors = {
        "👹 Goblin": {"attack_range": 8, "gold": 5, "exp": 3},
        "💀 Skeleton": {"attack_range": 12, "gold": 3, "exp": 4},
        "🐉 Troll": {"attack_range": 15, "gold": 10, "exp": 8},
        "🦇 Vampire": {"attack_range": 18, "gold": 15, "exp": 12},
        "👹 Goblin King": {"attack_range": 25, "gold": 30, "exp": 25},
    }

    enemies = list(floors.keys())[:min(len(floors), floor + 2)]
    if not enemies:
        enemies = ["👹 Goblin"]

    enemy_name = random.choice(enemies)
    stats = floors[enemy_name]
    dmg_range = stats["attack_range"] + (floor - 1) * 3
    hp = 30 + floor * 15

    return {
        "name": enemy_name,
        "hp": hp,
        "max_hp": hp,
        "attack_range": dmg_range,
        "gold": stats["gold"],
        "exp": stats["exp"],
    }


def player_attack(attacker, defender):
    """Calculate damage after defense."""
    variance = random.randint(-3, 3)
    raw_dmg = attacker["attack_range"] + variance
    return max(0, raw_dmg - defender["defense"])


def heal(healer, target):
    """Heal a fixed amount based on the healer's attack stat."""
    healed = min(healer["attack_range"], target["max_hp"] - target["hp"])
    return min(target["max_hp"], target["hp"] + healed)


def level_up(player):
    """Level up when exp reaches the threshold."""
    next_exp = player["level"] * 30
    if player["exp"] >= next_exp:
        player["level"] += 1
        player["exp"] -= next_exp
        player["max_hp"] += 20
        player["hp"] = player["max_hp"]
        player["attack_range"] += random.randint(5, 10)
        player["defense"] += random.randint(3, 7)


def print_screen(player):
    """Show the current status screen."""
    sep = "═" * 40
    print(f"\n{sep}")
    print(f"🏰 Dungeon Crawler | Floor {player['floor']}")
    print(sep)
    print(f"❤️ HP:      {player['hp']}/{player['max_hp']}")
    print(f"⚔️ Attack:  {player['attack_range']}")
    print(f"🛡 Defense: {player['defense']}")
    print(f"💰 Gold:    {player['gold']} | ⭐ Exp: {player['exp']}/{player['level']*30}")
    if player["inventory"]:
        items = " → ".join(player["inventory"])
        print(f"🎒 Items:  {items}")


def main():
    player = new_game()
    choose_character(player)

    while player["alive"]:
        print_screen(player)

        # ── Player's turn ─────────────────────────────────
        action = input("\n[1]⚔️ Attack  [2]💊 Heal  [3]🗝️ Use Item "
                        "[4]🪩 Go Deeper  [5]📋 Info\n> ").strip()

        if action == "5":
            print(f"\nYou are a level {player['level']} adventurer.")
            continue

        # ── Heal (no enemy, no combat) ────────────────────
        if action == "2":
            healed = heal(player, player)
            player["hp"] = healed
            print(f"\n💊 You rest and heal to {player['hp']} / {player['max_hp']} HP.")
            continue

        # ── Encounter an enemy (unless going deeper) ────────────
        if action == "1":
            enemy = encounter(player["floor"])
        elif action == "3":
            item_name = random.choice(["🧪 Health Potion", "🔥 Fire Bomb", "💎 Gem"])
            player["inventory"].append(item_name)
            print(f"\n🎒 Picked up {item_name}!")
            continue

        if action != "1":
            print("Unknown action. Try 1, 2, 3, 4 or 5.")
            continue

        # ── Fight! ────────────────────────────────────
        while enemy["hp"] > 0 and player["alive"]:
            print(f"\n⚔️ You fight the {enemy['name']}!")

            dmg = player_attack(player, enemy)
            enemy["hp"] -= dmg
            print(f"   Your attack dealt {dmg} damage → {enemy['name']}: {enemy['hp']} HP")

            if enemy["hp"] <= 0:
                break

            dmg = player_attack(enemy, player)
            player["hp"] -= dmg
            print(f"   The {enemy['name']}'s attack dealt {dmg} damage → You: {player['hp']} / {player['max_hp']}")

        if enemy["hp"] <= 0:
            gold = enemy["gold"] + random.randint(0, 3)
            exp = enemy["exp"] + player["floor"] * 2
            print(f"\n🎉 Defeated the {enemy['name']}! +{gold} gold, +{exp} exp")

            if gold > 0:
                player["gold"] += gold
            player["exp"] += exp
            level_up(player)
        else:
            dmg = enemy["attack_range"] // 2
            print(f"\n😵 You escaped the {enemy['name']}...")
            player["hp"] -= dmg

        # ── Player died? ────────────────────────────────────
        if player["hp"] <= 0:
            print("\n💀 YOU DIED in the dungeon. Better luck next time!")
            break

        # ── Inventory use ─────────────────────────────────
        if action == "3" and player["inventory"]:
            item = player["inventory"].pop(0)
            if "Health Potion" in item:
                healed = heal(player, player)
                player["hp"] = healed
                print(f"   🧪 Health potion heals you by {healed} HP → {player['hp']}/{player['max_hp']}")

        # ── Go deeper? ────────────────────────────────────
        go_deeper = input("\n🪩 Descend to the next floor? (y/n): ").strip().lower()
        if go_deeper in ("y", "yes"):
            player["floor"] += 1

    # ── Final score ───────────────────────────────────────────
    print(f"\n{'═' * 40}")
    print("🏆 Game Over — Final Score")
    print(f"   Floors reached: {player['level']}")
    print(f"   Gold collected: {player['gold']}")
    print(f"   Total exp:      {player['exp']} (Level {player['level']})")
    print(f"{'═' * 40}\n👋 Play again with python3 game.py!")


if __name__ == "__main__":
    main()
