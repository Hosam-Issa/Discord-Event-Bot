from bot.db.database import get_connection

# Called once at bot startup. Checks whether teams/tiles already exist before
# seeding, so this is safe to call every time the bot starts, not just the first time.
def seed_if_needed():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS count FROM teams")
    teams_count = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) AS count FROM tiles")
    tiles_count = cur.fetchone()["count"]

    conn.close()

    if teams_count == 0:
        seed_teams()
        print("Seeded teams.")
    if tiles_count == 0:
        seed_tiles()
        print("Seeded tiles.")


def seed_teams():
    conn = get_connection()
    cur = conn.cursor()
    # Placeholder role ids, change to actual role ids on use
    cur.execute("""
        INSERT INTO teams (name, role_id) VALUES
        ('Team 1', 1550617977353932874),
        ('Team 2', 222222222222222222),
        ('Team 3', 333333333333333333),
        ('Team 4', 444444444444444444)
    """)
    conn.commit()
    conn.close()

def seed_tiles():
    conn = get_connection()
    cur = conn.cursor()
    # 25 tiles (0-24), all sharing the same point value except the center (12),
    # which is the free tile.
    tiles = [(i, 1, 1 if i == 12 else 0, f"Test Drop {i}") for i in range(25)]
    cur.executemany("""
        INSERT INTO tiles (position, point_value, is_free, description)
        VALUES (?, ?, ?, ?)
    """, tiles)
    conn.commit()
    conn.close()


# Lets this file also be run directly (python -m bot.db.seed) for a manual, one-off reseed.
if __name__ == "__main__":
    seed_teams()
    seed_tiles()
    print("Database seeded successfully.")