import struct
from fontTools.ttLib import TTLibError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_RENDER_IMAGE_WIDTH = 1920 # pixels
MAX_RENDER_IMAGE_HEIGHT = 1080 # pixels
MAX_PREVIEW_GLYPHS = 64

DEFAULT_FONT_SIZE = 16

FONT_READ_ERRORS = (
    ValueError,
    OSError,
    TTLibError,
    struct.error,
    KeyError,
    IndexError
)