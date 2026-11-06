#!/usr/bin/env python3
"""Convert .lua source to binary .tic cartridge for TIC-80."""
import struct, sys, os

CHUNK_DEFAULT = 17
CHUNK_CODE    = 5
MUSIC_BLOB    = 'music.bin'
# Where the music blob lands in RAM, in blob order: TILES, SPRITES, MAP, MUSIC PATTERNS, MUSIC TRACKS.
# blastic.lua reads it back with the same split (MUSIC_LOW_SIZE).
MUSIC_CHUNKS  = [(1, 8192), (2, 8192), (4, 32640), (15, 11520), (14, 408)]

def make_chunk(ctype, bank, data: bytes) -> bytes:
    val = (ctype & 0x1f) | ((bank & 0x7) << 5) | ((len(data) & 0xffff) << 8)
    return struct.pack('<I', val) + data

def music_chunks(blob: bytes) -> bytes:
    if len(blob) > sum(size for _, size in MUSIC_CHUNKS):
        raise ValueError(f"Music too large: {len(blob)} bytes")
    out, pos = b'', 0
    for ctype, size in MUSIC_CHUNKS:
        part = blob[pos:pos + size]
        if part:
            out += make_chunk(ctype, 0, part)
        pos += size
    return out

def lua_to_tic(lua_path: str, tic_path: str):
    code = open(lua_path, 'r', encoding='utf-8').read()
    code_bytes = code.encode('utf-8')
    if len(code_bytes) > 65535:
        raise ValueError(f"Code too large: {len(code_bytes)} bytes (max 65535)")
    data = make_chunk(CHUNK_DEFAULT, 0, b'')
    music = os.path.join(os.path.dirname(lua_path), MUSIC_BLOB)
    if os.path.exists(music):
        data += music_chunks(open(music, 'rb').read())
    data += make_chunk(CHUNK_CODE, 0, code_bytes)
    with open(tic_path, 'wb') as f:
        f.write(data)
    print(f"Written {len(data)} bytes to {tic_path}")

if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else 'blastic.lua'
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + '.tic'
    lua_to_tic(src, dst)
