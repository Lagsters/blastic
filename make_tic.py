#!/usr/bin/env python3
"""Convert .lua source to binary .tic cartridge for TIC-80.

The code is minified on the way (see DEVIATIONS.md): comments, indentation and blank lines
go, strings stay byte for byte. `python make_tic.py --min <src.lua> <out.lua>` writes only the
minified code, which check.py runs the tests against. `python make_tic.py --films` builds
films.tic, a developer cart that plays every story scene in a loop (never released).
"""
import re, struct, sys, os

CHUNK_DEFAULT = 17
CHUNK_CODE    = 5
CODE_LIMIT    = 65535
MUSIC_BLOB    = 'music.bin'
# The music samples land in RAM from 0x04000 (TILES, then SPRITES), where blastic.lua reads them.
MUSIC_CHUNKS  = [(1, 8192), (2, 8192)]
# The scene backdrops land in MAP RAM (0x08000).
SCENES_BLOB   = 'scenes.bin'
CHUNK_MAP     = 4
MAP_SIZE      = 32640
FILM_REEL     = os.path.join('tools', 'film_reel.lua')
# TIC-80 reads the cart's metadata from these header comments, so they stay.
METADATA = re.compile(r'--\s*(title|author|desc|script|input|saveid|site|license|version):')
LONG_OPEN = re.compile(r'\[(=*)\[')


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


def long_string_end(code: str, i: int):
    """End index of the long string or comment body opening with [=*[ at i, or None."""
    m = LONG_OPEN.match(code, i)
    if not m:
        return None
    closer = ']' + m.group(1) + ']'
    return code.index(closer, m.end()) + len(closer)


def minify(code: str) -> str:
    """Drop comments, indentation and blank lines; keep strings and line breaks intact."""
    out, i, n = [], 0, len(code)
    while i < n:
        ch = code[i]
        if ch in '"\'':
            j = i + 1
            while j < n and code[j] != ch:
                j += 2 if code[j] == '\\' else 1
            out.append(code[i:j + 1])
            i = j + 1
        elif ch == '[' and LONG_OPEN.match(code, i):
            j = long_string_end(code, i)
            out.append(code[i:j])
            i = j
        elif code.startswith('--', i):
            at_line_start = code[code.rfind('\n', 0, i) + 1:i].strip() == ''
            if at_line_start and METADATA.match(code, i):
                j = code.find('\n', i)
                j = n if j < 0 else j
                out.append(code[i:j])
                i = j
            elif LONG_OPEN.match(code, i + 2):
                i = long_string_end(code, i + 2)
            else:
                j = code.find('\n', i)
                i = n if j < 0 else j
        else:
            out.append(ch)
            i += 1
    lines = (line.strip() for line in ''.join(out).split('\n'))
    return '\n'.join(line for line in lines if line) + '\n'


def lua_to_tic(lua_path: str, tic_path: str, extra: str = ''):
    code = minify(open(lua_path, 'r', encoding='utf-8').read() + extra)
    code_bytes = code.encode('utf-8')
    if len(code_bytes) > CODE_LIMIT:
        raise ValueError(f"Code too large: {len(code_bytes)} bytes (max {CODE_LIMIT})")
    data = make_chunk(CHUNK_DEFAULT, 0, b'')
    music = os.path.join(os.path.dirname(lua_path), MUSIC_BLOB)
    if os.path.exists(music):
        data += music_chunks(open(music, 'rb').read())
    scenes = os.path.join(os.path.dirname(lua_path), SCENES_BLOB)
    if os.path.exists(scenes):
        blob = open(scenes, 'rb').read()
        if len(blob) > MAP_SIZE:
            raise ValueError(f"Scenes too large: {len(blob)} bytes (max {MAP_SIZE})")
        data += make_chunk(CHUNK_MAP, 0, blob)
    data += make_chunk(CHUNK_CODE, 0, code_bytes)
    with open(tic_path, 'wb') as f:
        f.write(data)
    print(f"Written {len(data)} bytes to {tic_path} (code {len(code_bytes)}/{CODE_LIMIT} B)")


if __name__ == '__main__':
    if sys.argv[1:2] == ['--min']:
        with open(sys.argv[3], 'w', encoding='utf-8', newline='\n') as f:
            f.write(minify(open(sys.argv[2], encoding='utf-8').read()))
        sys.exit(0)
    if sys.argv[1:2] == ['--films']:
        lua_to_tic('blastic.lua', 'films.tic', chr(10) + open(FILM_REEL, encoding='utf-8').read())
        sys.exit(0)
    src = sys.argv[1] if len(sys.argv) > 1 else 'blastic.lua'
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + '.tic'
    lua_to_tic(src, dst)
