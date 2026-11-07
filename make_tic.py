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
MUSIC_RAM     = 0x04000  # the samples, where blastic.lua reads them
# The scene art (tools/scenes/paint.py): pieces of RAM, each u24 address, u16 length, bytes.
SCENES_BLOB   = 'scenes.bin'
# chunks that load into RAM: type -> (address, size)
CHUNK_RAM     = {1: (0x04000, 8192), 2: (0x06000, 8192), 4: (0x08000, 32640), 9: (0x100E4, 4224)}
FILM_REEL     = os.path.join('tools', 'film_reel.lua')
# The story section of the code (scenes and their texts) lands LZ-packed in MUSIC PATTERNS RAM,
# which the PCM tracker never uses, and is unpacked and loaded from there: it does not count
# against CODE_LIMIT. Packing: u16 packed length, then c<128 copies the next c+1 bytes,
# c>=128 repeats c-125 bytes from u16 distance back.
CHUNK_PATTERNS = 15
STORY_RAM, STORY_SIZE = 0x11164, 11520
STORY = re.compile(r'^-- story:begin.*?^-- story:end[^\n]*\n', re.S | re.M)
STORY_LOADER = ('do local a,o,n=%d,{},0 local e=a+2+(peek(a)|peek(a+1)<<8) a=a+2 '
                'while a<e do local c=peek(a) a=a+1 if c<128 then '
                'for i=0,c do n=n+1 o[n]=string.char(peek(a+i)) end a=a+c+1 '
                'else local d=peek(a)|peek(a+1)<<8 a=a+2 for _=1,c-125 do n=n+1 o[n]=o[n-d] end end end '
                'assert(load(table.concat(o),"story"))() end\n' % STORY_RAM)
LZ_MIN, LZ_MAX, LZ_WINDOW = 3, 130, 65535


def lz_pack(data: bytes) -> bytes:
    """Greedy LZ77 in the format above, without the length header."""
    out, lit, heads, i, n = bytearray(), bytearray(), {}, 0, len(data)

    def flush():
        while lit:
            part = lit[:128]
            out.append(len(part) - 1)
            out.extend(part)
            del lit[:128]

    while i < n:
        best_len, best_dist = 0, 0
        for j in reversed(heads.get(data[i:i + LZ_MIN], [])[-64:]):
            if i - j > LZ_WINDOW:
                break
            k = 0
            while k < LZ_MAX and i + k < n and data[j + k] == data[i + k]:
                k += 1
            if k > best_len:
                best_len, best_dist = k, i - j
        if best_len >= LZ_MIN:
            flush()
            out.append(best_len + 125)
            out += best_dist.to_bytes(2, 'little')
            step = best_len
        else:
            lit.append(data[i])
            step = 1
        for k in range(i, min(i + step, n - LZ_MIN + 1)):
            heads.setdefault(data[k:k + LZ_MIN], []).append(k)
        i += step
    flush()
    return bytes(out)


def lz_unpack(packed: bytes) -> bytes:
    out, i = bytearray(), 0
    while i < len(packed):
        c = packed[i]
        if c < 128:
            out += packed[i + 1:i + 2 + c]
            i += c + 2
        else:
            d = int.from_bytes(packed[i + 1:i + 3], 'little')
            for _ in range(c - 125):
                out.append(out[-d])
            i += 3
    return bytes(out)
# TIC-80 reads the cart's metadata from these header comments, so they stay.
METADATA = re.compile(r'--\s*(title|author|desc|script|input|saveid|site|license|version):')
LONG_OPEN = re.compile(r'\[(=*)\[')


def make_chunk(ctype, bank, data: bytes) -> bytes:
    val = (ctype & 0x1f) | ((bank & 0x7) << 5) | ((len(data) & 0xffff) << 8)
    return struct.pack('<I', val) + data


def ram_chunks(pieces) -> bytes:
    """Chunks that load the pieces [(address, bytes)] into RAM; overlaps are an error."""
    ram = {}
    for addr, data in pieces:
        for i, b in enumerate(data):
            if addr + i in ram:
                raise ValueError(f"RAM {hex(addr + i)} written twice")
            ram[addr + i] = b
    out = b''
    for ctype, (base, size) in CHUNK_RAM.items():
        used = [a for a in ram if base <= a < base + size]
        if not used:
            continue
        body = bytes(ram.get(a, 0) for a in range(base, max(used) + 1))
        out += make_chunk(ctype, 0, body)
        for a in used:
            del ram[a]
    if ram:
        raise ValueError(f"no chunk loads RAM {hex(min(ram))}")
    return out


def scene_pieces(blob: bytes):
    pieces, i = [], 0
    while i < len(blob):
        addr = int.from_bytes(blob[i:i + 3], 'little')
        n = int.from_bytes(blob[i + 3:i + 5], 'little')
        pieces.append((addr, blob[i + 5:i + 5 + n]))
        i += 5 + n
    return pieces


def long_string_end(code: str, i: int):
    """End index of the long string or comment body opening with [=*[ at i, or None."""
    m = LONG_OPEN.match(code, i)
    if not m:
        return None
    closer = ']' + m.group(1) + ']'
    return code.index(closer, m.end()) + len(closer)


WORD = re.compile(r'\w')
# pairs that lex differently once joined: comments, concatenation into numbers, long brackets,
# two-character operators
GLUE = {'--', '..', '[[', '[=', '==', '<=', '>=', '~=', '<<', '>>', '//', '::'}


def needs_space(a: str, b: str) -> bool:
    if WORD.match(a) and WORD.match(b):
        return True
    return a + b in GLUE or (a == '.' and b.isdigit()) or (a.isdigit() and b == '.')


def minify(code: str) -> str:
    """Drop comments, indentation, blank lines and spaces the lexer does not need; keep strings
    and line breaks intact."""
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
        elif ch in ' \t':
            j = i
            while j < n and code[j] in ' \t':
                j += 1
            prev = out[-1][-1] if out else '\n'
            if j < n and needs_space(prev, code[j]):
                out.append(' ')
            i = j
        else:
            out.append(ch)
            i += 1
    lines = (line.strip() for line in ''.join(out).split('\n'))
    return '\n'.join(line for line in lines if line) + '\n'


def split_story(src: str):
    """The code with the story section replaced by its loader, and the story section."""
    m = STORY.search(src)
    if not m:
        return src, ''
    return src[:m.start()] + STORY_LOADER + src[m.end():], m.group(0)


def lua_to_tic(lua_path: str, tic_path: str, extra: str = ''):
    src, story = split_story(open(lua_path, 'r', encoding='utf-8').read() + extra)
    code = minify(src)
    code_bytes = code.encode('utf-8')
    story_bytes = b''
    if story:
        packed = lz_pack(minify(story).encode('utf-8'))
        story_bytes = len(packed).to_bytes(2, 'little') + packed
    if len(story_bytes) > STORY_SIZE:
        raise ValueError(f"Story too large: {len(story_bytes)} bytes packed (max {STORY_SIZE})")
    if len(code_bytes) > CODE_LIMIT:
        raise ValueError(f"Code too large: {len(code_bytes)} bytes (max {CODE_LIMIT})")
    data = make_chunk(CHUNK_DEFAULT, 0, b'')
    pieces = []
    music = os.path.join(os.path.dirname(lua_path), MUSIC_BLOB)
    if os.path.exists(music):
        pieces.append((MUSIC_RAM, open(music, 'rb').read()))
    scenes = os.path.join(os.path.dirname(lua_path), SCENES_BLOB)
    if os.path.exists(scenes):
        pieces += scene_pieces(open(scenes, 'rb').read())
    data += ram_chunks(pieces)
    if story_bytes:
        data += make_chunk(CHUNK_PATTERNS, 0, story_bytes)
    data += make_chunk(CHUNK_CODE, 0, code_bytes)
    with open(tic_path, 'wb') as f:
        f.write(data)
    print(f"Written {len(data)} bytes to {tic_path} (code {len(code_bytes)}/{CODE_LIMIT} B, "
          f"story {len(story_bytes)}/{STORY_SIZE} B packed)")


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
