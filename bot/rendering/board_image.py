import os
from PIL import Image, ImageDraw
from bot.db.database import get_board_state

BASE_IMAGE_PATH = "assets/board_base.png"

# Converts a tile's position number (0-24 for a 5x5 board) into the pixel rectangle
# it occupies on the board image, assuming an evenly divided grid.
def pixel_position(tile_pos, image_width, image_height, grid_size=5):
    row = tile_pos // grid_size   # which row this position falls in (floor division)
    col = tile_pos % grid_size    # remaining offset within that row (modulo)
    tile_width = image_width // grid_size
    tile_height = image_height // grid_size
    x0 = col * tile_width
    y0 = row * tile_height
    x1 = x0 + tile_width
    y1 = y0 + tile_height
    return x0, y0, x1, y1

# Normalizes any (roughly square) board image to a clean, grid_size-divisible square,
# so pixel_position's math lines up exactly regardless of the source image's original
# dimensions (e.g. from an imprecise manual screenshot).
def prepare_board_image(image_path, grid_size=5, target_tile_px=200, tolerance=0.05):
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size

    # Reject images that are too far from square rather than silently distorting them.
    ratio_diff = abs(width - height) / max(width, height)
    if ratio_diff > tolerance:
        raise ValueError(
            f"Board image is too far from square ({width}x{height}) - please recrop it."
        )

    # If it's close but not exact, crop the longer side down evenly from the center
    # (never stretch — that would distort the art).
    if width != height:
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        img = img.crop((left, top, left + side, top + side))

    # Resize to an exact multiple of grid_size, so every tile is exactly target_tile_px wide.
    target_size = grid_size * target_tile_px
    if img.size != (target_size, target_size):
        img = img.resize((target_size, target_size), Image.LANCZOS)

    return img

# Renders one team's board: starts fresh from the clean base image every time (so marks
# never accumulate/get "stuck"), overlays a semi-transparent tint on each completed tile,
# and saves the result.
def render_team_board(team_id, output_path, grid_size=5):
    base = prepare_board_image(BASE_IMAGE_PATH, grid_size=grid_size)

    # Draw onto a separate transparent layer so the tint blends with the base image
    # instead of just overwriting pixels outright.
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    completed_positions = get_board_state(team_id)

    for position in completed_positions:
        x0, y0, x1, y1 = pixel_position(position, base.width, base.height, grid_size)
        draw.rectangle([x0, y0, x1, y1], fill=(0, 200, 0, 120))  # semi-transparent green

    combined = Image.alpha_composite(base, overlay)
    combined.convert("RGB").save(output_path)