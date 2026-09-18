from database import get_connection

def seed_teams():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO teams (name, role_id) VALUES
        ('Team 1', 111111111111111111),
        ('Team 2', 222222222222222222),
        ('Team 3', 333333333333333333),
        ('Team 4', 444444444444444444)
    """)
    conn.commit()
    conn.close()

def seed_tiles():
    conn = get_connection()
    cur = conn.cursor()
    tiles = [(i, 1, 1 if i == 12 else 0, f"Test Drop {i}") for i in range(25)]
    cur.executemany("""
        INSERT INTO tiles (position, point_value, is_free, description)
        VALUES (?, ?, ?, ?)
    """, tiles)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    seed_teams()
    seed_tiles()
    print("Database seeded successfully.")