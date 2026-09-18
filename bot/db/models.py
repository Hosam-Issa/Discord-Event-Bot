CREATE_TEAMS_TABLE = """
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        role_id INTEGER UNIQUE
    )
"""

CREATE_PLAYERS_TABLE = """
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discord_id INTEGER NOT NULL UNIQUE,
        discord_username TEXT NOT NULL,
        osrs_name TEXT NOT NULL,
        team_id INTEGER REFERENCES teams(id)
    )
"""

CREATE_TILES_TABLE = """
    CREATE TABLE IF NOT EXISTS tiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        position INTEGER NOT NULL UNIQUE,
        point_value INTEGER NOT NULL,
        is_free INTEGER NOT NULL DEFAULT 0,
        description TEXT
    )
"""

CREATE_TEAM_TILE_STATUS_TABLE = """
    CREATE TABLE IF NOT EXISTS team_tile_status (
        team_id INTEGER REFERENCES teams(id),
        tile_id INTEGER REFERENCES tiles(id),
        completed INTEGER NOT NULL DEFAULT 0,
        completed_at TEXT,
        PRIMARY KEY (team_id, tile_id)
    )
"""

CREATE_SUBMISSIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tile_id INTEGER REFERENCES tiles(id),
        team_id INTEGER REFERENCES teams(id),
        player_id INTEGER REFERENCES players(id),
        drop_name TEXT NOT NULL,
        image_path TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        submitted_at TEXT NOT NULL,
        reviewed_by INTEGER,
        reviewed_at TEXT
    )
"""