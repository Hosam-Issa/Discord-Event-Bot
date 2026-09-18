import sqlite3
import os
from models import (
    CREATE_TEAMS_TABLE,
    CREATE_PLAYERS_TABLE,
    CREATE_TILES_TABLE,
    CREATE_TEAM_TILE_STATUS_TABLE,
    CREATE_SUBMISSIONS_TABLE,
)

DB_PATH = os.path.join(os.path.dirname(__file__), "bingo.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(CREATE_TEAMS_TABLE)
    cur.execute(CREATE_PLAYERS_TABLE)
    cur.execute(CREATE_TILES_TABLE)
    cur.execute(CREATE_TEAM_TILE_STATUS_TABLE)
    cur.execute(CREATE_SUBMISSIONS_TABLE)

    conn.commit()
    conn.close()

def get_team_score(team_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT SUM(tiles.point_value) AS total
        FROM team_tile_status
        JOIN tiles ON team_tile_status.tile_id = tiles.id
        WHERE team_tile_status.team_id = ?
            AND team_tile_status.completed = 1
    """, (team_id,))
                
    row = cur.fetchone()
    conn.close()

    return row["total"] if row["total"] is not None else 0

def get_board_state(team_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT tile_id FROM team_tile_status
        WHERE team_id = ?
            AND completed = 1
    """, (team_id,))

    rows = cur.fetchall()
    conn.close()

    return [row["tile_id"] for row in rows]