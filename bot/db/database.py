import sqlite3
import os
from bot.db.models import (
    CREATE_TEAMS_TABLE,
    CREATE_PLAYERS_TABLE,
    CREATE_TILES_TABLE,
    CREATE_TEAM_TILE_STATUS_TABLE,
    CREATE_SUBMISSIONS_TABLE,
    CREATE_LEADERBOARD_MESSAGES_TABLE,
)

# Anchored to this file's own location, not the current working directory —
# ensures the bot always finds the same bingo.db regardless of how/where it's launched from.
DB_PATH = os.path.join(os.path.dirname(__file__), "bingo.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # enforce foreign key constraints
    conn.row_factory = sqlite3.Row  # lets rows be accessed like dicts, e.g. row["column_name"]
    return conn

# Safe to call on every startup — CREATE TABLE IF NOT EXISTS is a no-op if tables already exist.
def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(CREATE_TEAMS_TABLE)
    cur.execute(CREATE_PLAYERS_TABLE)
    cur.execute(CREATE_TILES_TABLE)
    cur.execute(CREATE_TEAM_TILE_STATUS_TABLE)
    cur.execute(CREATE_SUBMISSIONS_TABLE)
    cur.execute(CREATE_LEADERBOARD_MESSAGES_TABLE)

    conn.commit()
    conn.close()

# Total points for one team, from completed tiles only.
def get_team_score(team_id):
    try:
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
    finally:
        conn.close()

    # SUM() over zero matching rows returns NULL/None in SQL — default to 0 instead.
    return row["total"] if row["total"] is not None else 0

# Which tile positions a given team has completed — used for rendering their board.
def get_board_state(team_id):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT tiles.position FROM team_tile_status
            JOIN tiles ON team_tile_status.tile_id = tiles.id
            WHERE team_tile_status.team_id = ? AND team_tile_status.completed = 1
        """, (team_id,))
        rows = cur.fetchall()
    finally:
        conn.close()

    return [row["position"] for row in rows]

# Every team's current score, including teams with zero completed tiles (LEFT JOIN
# ensures they still appear, rather than being excluded by a plain JOIN).
def get_all_team_scores():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT teams.id AS team_id, teams.name AS team_name,
                COALESCE(SUM(tiles.point_value), 0) AS score
            FROM teams
            LEFT JOIN team_tile_status
                ON team_tile_status.team_id = teams.id AND team_tile_status.completed = 1
            LEFT JOIN tiles
                ON tiles.id = team_tile_status.tile_id
            GROUP BY teams.id
            ORDER BY score DESC
        """)
        rows = cur.fetchall()
    finally:
        conn.close()

    return [{"team_id": r["team_id"], "team_name": r["team_name"], "score": r["score"]} for r in rows]

# Top N scoring players on one team, based on approved submissions.
def get_top_players_for_team(team_id, limit=3):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT players.id AS player_id, players.osrs_name, players.team_id,
                COALESCE(SUM(tiles.point_value), 0) AS score
            FROM players
            -- Deduplicate by (player, tile) first: a tile can only be approved once
            -- per team, but if multiple approved submission rows exist for the same
            -- tile (e.g. leftover duplicates), this stops them being double-counted here.
            LEFT JOIN (
                SELECT DISTINCT player_id, tile_id FROM submissions WHERE status = 'approved'
            ) AS distinct_submissions
                ON distinct_submissions.player_id = players.id
            LEFT JOIN tiles
                ON tiles.id = distinct_submissions.tile_id
            WHERE players.team_id = ?
            GROUP BY players.id
            ORDER BY score DESC LIMIT ?
        """, (team_id, limit,))
        rows = cur.fetchall()
    finally:
        conn.close()

    return [{"player_id": r["player_id"], "osrs_name": r["osrs_name"], "team_id": r["team_id"], "score": r["score"]} for r in rows]