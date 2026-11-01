-- title:  BlasTIC
-- author: Melancholy
-- desc:   4-player arena blast game (P1+P2 human, P3+P4 bots)
-- script: lua
-- input:  gamepad

W,H=30,17
TILE=8
MAX_BOMBS=2
BOMB_TIMER=120
BLAST_LEN=2
BLAST_TIME=30
SPEED=1
MATCH_WINS=3
MATCH_TIME=210

T_EMPTY,T_WALL,T_BLOCK=0,1,2

STARTS={{1,1},{W-2,1},{1,H-2},{W-2,H-2}}
local COLORS={12,11,9,14}

local B_UP,B_DOWN,B_LEFT,B_RIGHT,B_BOMB=0,1,2,3,4

map,bombs,blasts,players={},{},{},{}
frame=0
state="title"
winner=nil
score={0,0,0,0}
restartTimer=0
titleTimer=0

-- ── helpers ──────────────────────────────────────────────────────────────────

function mget(c,r) return map[r] and map[r][c] or T_WALL end
local function mset(c,r,v) if map[r] then map[r][c]=v end end
function gpx(c) return c*TILE end
function gpy(r) return r*TILE end
local function gcell(x) return math.floor(x/TILE) end

-- ── init ─────────────────────────────────────────────────────────────────────

local function initMap()
  map={}
  for r=0,H-1 do
    map[r]={}
    for c=0,W-1 do
      if r==0 or r==H-1 or c==0 or c==W-1 then
        map[r][c]=T_WALL
      elseif r%2==0 and c%2==0 then
        map[r][c]=T_WALL
      elseif math.random()<0.4 then
        local corner=false
        for _,s in ipairs(STARTS) do
          local sc,sr=s[1],s[2]
          if (c==sc   and r==sr  ) or
             (c==sc+1 and r==sr  ) or (c==sc-1 and r==sr  ) or
             (c==sc   and r==sr+1) or (c==sc   and r==sr-1) then
            corner=true
          end
        end
        map[r][c]=corner and T_EMPTY or T_BLOCK
      else
        map[r][c]=T_EMPTY
      end
    end
  end
end

local function initPlayers()
  players={}
  for i,s in ipairs(STARTS) do
    players[i]={
      c=s[1], r=s[2],
      x=gpx(s[1]), y=gpy(s[2]),
      alive=true,
      bombs=0,
      stats={bombs=MAX_BOMBS,len=BLAST_LEN},
      color=COLORS[i],
      id=i,
      dir={0,1},
      walkAnim=0,
      botDir={0,0},
      botDirTimer=0,
      botBombTimer=0,
      botEscape=0,
    }
  end
end

-- ── muzyka ───────────────────────────────────────────────────────────────────
-- Spokojny ambientowy podkład: niskie tony, dużo ciszy, c-moll
-- API: sfx(id, note, duration, channel, volume, speed)
-- note: 0..95 (0=C-0, 12=C-1, 24=C-2, 36=C-3, 48=C-4)
-- -1 = pauza (cisza)

-- Bas (oktawa 2): C2, Eb2, G2, Bb2 — wolne, miękkie
local BASS={24,-1,-1,-1, 27,-1,-1,-1, 31,-1,-1,-1, 22,-1,-1,-1,
            24,-1,-1,-1, 27,-1,-1,-1, 29,-1,-1,-1, 27,-1,-1,-1}

-- Pad (oktawa 3): C3, Eb3, G3, F3, Bb3 — z dużymi pauzami
local PAD ={-1,-1,36,-1, -1,-1,39,-1, -1,-1,43,-1, -1,-1,41,-1,
            -1,-1,36,-1, -1,-1,39,-1, -1,-1,41,-1, -1,-1,39,-1}

-- Ozdobnik (oktawa 3): cichy ton od czasu do czasu
local DECO={-1,-1,-1,-1, -1,-1,-1,-1, -1,-1,-1,-1, -1,-1,-1,38,
            -1,-1,-1,-1, -1,-1,-1,-1, -1,-1,-1,-1, -1,-1,-1,36}

local PATTERN_LEN=32
local STEP_FRAMES=24  -- ~0.4 sek per krok przy 60fps
local musicStep=0
local musicTimer=0
local musicOn=false

local function updateMusic()
  if not musicOn then return end

  musicTimer = musicTimer + 1
  if musicTimer < STEP_FRAMES then return end
  musicTimer = 0

  local i = (musicStep % PATTERN_LEN) + 1
  local bn = BASS[i]
  local pn = PAD[i]
  local dn = DECO[i]

  if bn and bn >= 0 then
    sfx(3, bn, 80, 0, 6, 0)  -- bas: triangle, wolny, cichy, długie wybrzmienie
  end
  if pn and pn >= 0 then
    sfx(2, pn, 60, 1, 4, 1)  -- pad: triangle, średnia długość, cichy
  end
  if dn and dn >= 0 then
    sfx(2, dn, 40, 2, 3, 1)  -- ozdobnik: bardzo cichy
  end

  musicStep = musicStep + 1
end

local function startMusic()
  musicOn = true
  musicStep = 0
  musicTimer = 0
end

local audioReady=false
local function initAudio()
  if audioReady then return end
  audioReady=true

  -- Wave 0: noise (explosion) — wysokoentropyjna, chaotyczna
  local w0={15,3,11,7,1,13,5,9,14,2,10,6,0,12,4,8,
             8,4,12,0,6,10,2,14,9,5,13,1,7,11,3,15}
  for i=0,15 do poke(0x14000+i, w0[i*2+1]|(w0[i*2+2]<<4)) end

  -- Wave 1: opadająca piła (yell śmierci) — 15,14,13,...,0,15,14,...
  for i=0,15 do
    poke(0x14010+i, (15-i*2%16)|((15-(i*2+1)%16)<<4))
  end

  -- SFX 0: wybuch — szum, oct 5→4→3, gwałtowny zanik głośności
  -- format na tick: byte0=(oct<<4)|note, byte1=(vol<<4)|wave
  local exp={
    {9,5,15},{9,5,13},{7,5,11},{7,4,9},{5,4,7},
    {5,4,5}, {2,4,3}, {2,3,2}, {0,3,1}, {0,3,0},
  }
  local b=0x14100
  for i,t in ipairs(exp) do
    poke(b+(i-1)*2,   (t[2]<<4)|t[1])
    poke(b+(i-1)*2+1, (t[3]<<4)|0)   -- wave 0 (noise)
  end
  for i=#exp,29 do poke(b+i*2,0); poke(b+i*2+1,0) end
  poke(b+60,0); poke(b+61,2)          -- no loop, speed 2

  -- SFX 1: śmierć — "aaah!" opadający yell A5→G5→E4→C4→A3
  local die={
    {9,5,13},{7,5,12},{4,4,10},{0,4,7},{9,3,4},{9,3,1},
  }
  local b2=0x14100+66
  for i,t in ipairs(die) do
    poke(b2+(i-1)*2,   (t[2]<<4)|t[1])
    poke(b2+(i-1)*2+1, (t[3]<<4)|1)  -- wave 1 (piła)
  end
  for i=#die,29 do poke(b2+i*2,0); poke(b2+i*2+1,0) end
  poke(b2+60,0); poke(b2+61,2)        -- no loop, speed 2

  -- Wave 2: prostokąt
  for i=0,7  do poke(0x14020+i,0x00) end
  for i=8,15 do poke(0x14020+i,0xFF) end

  -- Wave 3: trójkąt (melodia i bas)
  local tri={0x10,0x32,0x54,0x76,0x98,0xBA,0xDC,0xFE,
             0xEF,0xCD,0xAB,0x89,0x67,0x45,0x23,0x01}
  for i=0,15 do poke(0x14030+i,tri[i+1]) end

  -- SFX 2: melodia — trójkąt, bardzo cichy, krótki
  local bm=0x14184
  local me={6,6,5,4,3,2,1,0}
  for i=0,#me-1 do poke(bm+i*2,0); poke(bm+i*2+1,(me[i+1]<<4)|3) end
  for i=#me,29 do poke(bm+i*2,0); poke(bm+i*2+1,0) end
  poke(bm+60,0); poke(bm+61,1)

  -- SFX 3: bas — trójkąt, szeptem
  local bb=0x141C6
  local be={4,4,3,2,1,0}
  for i=0,#be-1 do poke(bb+i*2,0); poke(bb+i*2+1,(be[i+1]<<4)|3) end
  for i=#be,29 do poke(bb+i*2,0); poke(bb+i*2+1,0) end
  poke(bb+60,0); poke(bb+61,1)

  -- SFX 4: hi-hat/percussion — noise, szybki decay
  local bp=0x14208
  local pe={7,6,5,4,3,2,1,0}
  for i=0,#pe-1 do
    poke(bp+i*2,0)
    poke(bp+i*2+1,(pe[i+1]<<4)|0)  -- noise wave
  end
  for i=#pe,29 do poke(bp+i*2,0); poke(bp+i*2+1,0) end
  poke(bp+60,0); poke(bp+61,2)  -- speed 2, szybki attack
end

function init()
  math.randomseed(time())
  bombs={}
  blasts={}
  initMap()
  initPlayers()
  initAudio()
  frame=0
  state="game"
  winner=nil
  restartTimer=0
end

-- ── blast ─────────────────────────────────────────────────────────────────────

local function addBlast(c,r)
  blasts[#blasts+1]={c=c,r=r,t=BLAST_TIME}
end

local function explode(b)
  sfx(0,-1,25,0,15)
  local bc,br=b.c,b.r
  addBlast(bc,br)
  local dirs={{0,-1},{0,1},{-1,0},{1,0}}
  for _,d in ipairs(dirs) do
    for i=1,BLAST_LEN do
      local nc,nr=bc+d[1]*i,br+d[2]*i
      local t=mget(nc,nr)
      if t==T_WALL then break end
      addBlast(nc,nr)
      if t==T_BLOCK then mset(nc,nr,T_EMPTY) break end
    end
  end
  if b.owner then b.owner.bombs=math.max(0,b.owner.bombs-1) end
end

-- ── physics ───────────────────────────────────────────────────────────────────

local function updateBombs()
  local keep={}
  for _,b in ipairs(bombs) do
    b.t=b.t-1
    if b.t<=0 then explode(b) else keep[#keep+1]=b end
  end
  bombs=keep
end

local function updateBlasts()
  local keep={}
  for _,bl in ipairs(blasts) do
    bl.t=bl.t-1
    if bl.t>0 then keep[#keep+1]=bl end
  end
  blasts=keep
end

local function isBlast(c,r)
  for _,bl in ipairs(blasts) do
    if bl.c==c and bl.r==r then return true end
  end
  return false
end

local function isBomb(c,r)
  for _,b in ipairs(bombs) do
    if b.c==c and b.r==r then return true end
  end
  return false
end

local function isDanger(c,r)
  return isBlast(c,r) or isBomb(c,r)
end

local function movePlayer(p,dc,dr)
  local nx=p.x+dc*SPEED
  local ny=p.y+dr*SPEED
  local margin=1
  -- cells where player's hitbox currently overlaps own bomb → passable this frame
  local passable={}
  for _,b in ipairs(bombs) do
    if b.owner==p then
      local ox0=gcell(p.x+margin); local ox1=gcell(p.x+TILE-margin-1)
      local oy0=gcell(p.y+margin); local oy1=gcell(p.y+TILE-margin-1)
      if b.c>=ox0 and b.c<=ox1 and b.r>=oy0 and b.r<=oy1 then
        passable[b.c*100+b.r]=true
      end
    end
  end
  local function blocked(x,y)
    local cs={
      {gcell(x+margin),          gcell(y+margin)},
      {gcell(x+TILE-margin-1),   gcell(y+margin)},
      {gcell(x+margin),          gcell(y+TILE-margin-1)},
      {gcell(x+TILE-margin-1),   gcell(y+TILE-margin-1)},
    }
    for _,co in ipairs(cs) do
      local t=mget(co[1],co[2])
      if t==T_WALL or t==T_BLOCK then return true end
      if isBomb(co[1],co[2]) and not passable[co[1]*100+co[2]] then return true end
    end
    return false
  end
  local hx = not blocked(nx,p.y)
  local hy = not blocked(p.x,ny)
  if hx then p.x=nx end
  if hy then p.y=ny end

  -- corridor snap: nudge 1px perpendicularly to ease entry into passages
  local SNAP=3
  if dc~=0 and not hx then
    local oy=p.y%TILE
    if oy>0 and oy<=SNAP then
      if not blocked(p.x,p.y-1) then p.y=p.y-1 end
    elseif oy>=TILE-SNAP and oy<TILE then
      if not blocked(p.x,p.y+1) then p.y=p.y+1 end
    end
  end
  if dr~=0 and not hy then
    local ox=p.x%TILE
    if ox>0 and ox<=SNAP then
      if not blocked(p.x-1,p.y) then p.x=p.x-1 end
    elseif ox>=TILE-SNAP and ox<TILE then
      if not blocked(p.x+1,p.y) then p.x=p.x+1 end
    end
  end

  p.c=gcell(p.x+TILE//2)
  p.r=gcell(p.y+TILE//2)
end

local function placeBomb(p)
  if p.bombs<MAX_BOMBS then
    local bc=gcell(p.x+TILE//2)
    local br=gcell(p.y+TILE//2)
    if not isBomb(bc,br) then
      bombs[#bombs+1]={c=bc,r=br,t=BOMB_TIMER,owner=p}
      p.bombs=p.bombs+1
      return true
    end
  end
  return false
end

-- ── human player ─────────────────────────────────────────────────────────────

local function updatePlayer(p)
  if not p.alive then return end
  local off=(p.id-1)*8
  local ox,oy=p.x,p.y
  if btn(off+B_UP)    then movePlayer(p, 0,-1); p.dir={0,-1} end
  if btn(off+B_DOWN)  then movePlayer(p, 0, 1); p.dir={0, 1} end
  if btn(off+B_LEFT)  then movePlayer(p,-1, 0); p.dir={-1,0} end
  if btn(off+B_RIGHT) then movePlayer(p, 1, 0); p.dir={ 1,0} end
  if p.x~=ox or p.y~=oy then p.walkAnim=p.walkAnim+1 end
  if btnp(off+B_BOMB) then placeBomb(p) end
  if isBlast(p.c,p.r) then p.alive=false; sfx(1,-1,15,1,12) end
end

-- ── bot AI ────────────────────────────────────────────────────────────────────

local BOT_DIRS={{0,-1},{0,1},{-1,0},{1,0}}

local function botAdjacentTarget(p)
  for _,d in ipairs(BOT_DIRS) do
    local nc,nr=p.c+d[1],p.r+d[2]
    if mget(nc,nr)==T_BLOCK then return true end
    for _,op in ipairs(players) do
      if op.alive and op.id~=p.id and op.c==nc and op.r==nr then return true end
    end
  end
  return false
end

local function botSafeDir(p)
  for _=1,8 do
    local d=BOT_DIRS[math.random(4)]
    local nc,nr=p.c+d[1],p.r+d[2]
    if not isDanger(nc,nr) and mget(nc,nr)==T_EMPTY then return d end
  end
  return BOT_DIRS[math.random(4)]
end

local function updateBot(p)
  if not p.alive then return end

  p.botDirTimer=p.botDirTimer-1
  if p.botBombTimer>0 then p.botBombTimer=p.botBombTimer-1 end
  if p.botEscape>0 then p.botEscape=p.botEscape-1 end

  -- react to immediate danger
  if isDanger(p.c,p.r) then
    p.botDir=botSafeDir(p)
    p.botDirTimer=15
    p.botEscape=40
  end

  -- pick new direction periodically
  if p.botDirTimer<=0 then
    if p.botEscape>0 then
      p.botDir=botSafeDir(p)
    else
      p.botDir=BOT_DIRS[math.random(4)]
    end
    p.botDirTimer=15+math.random(25)
  end

  -- attempt move; if stuck pick new dir next frame
  local dc,dr=p.botDir[1],p.botDir[2]
  local ox,oy=p.x,p.y
  if dc~=0 or dr~=0 then p.dir={dc,dr} end
  movePlayer(p,dc,dr)
  if p.x==ox and p.y==oy then
    p.botDirTimer=0
  else
    p.walkAnim=p.walkAnim+1
  end

  -- place bomb when adjacent to block/player and not escaping
  if p.botBombTimer==0 and p.botEscape==0 and botAdjacentTarget(p) then
    if placeBomb(p) then
      p.botBombTimer=BOMB_TIMER+30
      p.botEscape=50
      p.botDir=botSafeDir(p)
      p.botDirTimer=45
    end
  end

  if isBlast(p.c,p.r) then p.alive=false; sfx(1,-1,15,1,12) end
end

-- ── draw ─────────────────────────────────────────────────────────────────────

local WALL_COL=13
local BLOCK_COL=6
local FLOOR_COL=0
local BLAST_COL=4
local BOMB_COL=2

local function drawMap()
  for r=0,H-1 do
    for c=0,W-1 do
      local t=mget(c,r)
      local col=FLOOR_COL
      if t==T_WALL  then col=WALL_COL
      elseif t==T_BLOCK then col=BLOCK_COL end
      rect(gpx(c),gpy(r),TILE,TILE,col)
      if t==T_WALL then
        rectb(gpx(c),gpy(r),TILE,TILE,15)
      elseif t==T_BLOCK then
        rectb(gpx(c),gpy(r),TILE,TILE,5)
      end
    end
  end
end

local function drawBlasts()
  for _,bl in ipairs(blasts) do
    rect(gpx(bl.c)+1,gpy(bl.r)+1,TILE-2,TILE-2,BLAST_COL)
  end
end

local function drawBombs()
  for _,b in ipairs(bombs) do
    local blink=(b.t<40 and frame%6<3)
    local col=blink and 7 or BOMB_COL
    circ(gpx(b.c)+TILE//2,gpy(b.r)+TILE//2,3,col)
    line(gpx(b.c)+TILE//2,gpy(b.r)+1,gpx(b.c)+TILE//2+2,gpy(b.r)-1,7)
  end
end

-- Sprite pixel data: 0=transparent 1=skin(light blue) 2=body(player col) 3=dark(outline/eyes)
-- 8×8 pixels per frame, 6 frames: down0,down1,up0,up1,right0,right1
-- left = right flipped horizontally
local SPR={
  -- [1] facing down, walk-0 (arms spread)
  {0,0,2,2,2,2,0,0,
   0,2,1,1,1,1,2,0,
   0,2,1,3,3,1,2,0,
   0,2,1,1,1,1,2,0,
   2,0,2,2,2,2,0,2,
   0,0,2,2,2,2,0,0,
   0,0,2,0,0,2,0,0,
   0,0,3,0,0,3,0,0},
  -- [2] facing down, walk-1 (arms in, legs cross)
  {0,0,2,2,2,2,0,0,
   0,2,1,1,1,1,2,0,
   0,2,1,3,3,1,2,0,
   0,2,1,1,1,1,2,0,
   0,2,2,2,2,2,2,0,
   2,0,2,2,2,2,0,2,
   0,0,0,2,2,0,0,0,
   0,0,2,0,0,2,0,0},
  -- [3] facing up, walk-0 (back of head, no eyes)
  {0,0,2,2,2,2,0,0,
   0,2,1,1,1,1,2,0,
   0,2,1,1,1,1,2,0,
   0,2,2,2,2,2,2,0,
   2,0,2,2,2,2,0,2,
   0,0,2,2,2,2,0,0,
   0,0,2,0,0,2,0,0,
   0,0,3,0,0,3,0,0},
  -- [4] facing up, walk-1
  {0,0,2,2,2,2,0,0,
   0,2,1,1,1,1,2,0,
   0,2,1,1,1,1,2,0,
   0,2,2,2,2,2,2,0,
   0,2,2,2,2,2,2,0,
   2,0,2,2,2,2,0,2,
   0,0,0,2,2,0,0,0,
   0,0,2,0,0,2,0,0},
  -- [5] facing right, walk-0 (one eye, arm forward)
  {0,0,0,2,2,2,0,0,
   0,0,2,1,1,1,2,0,
   0,0,2,1,3,1,2,0,
   0,0,2,1,1,1,2,0,
   0,0,2,2,2,2,2,2,
   0,0,2,2,2,2,0,0,
   0,0,2,0,2,0,0,0,
   0,0,3,0,3,0,0,0},
  -- [6] facing right, walk-1 (arm back)
  {0,0,0,2,2,2,0,0,
   0,0,2,1,1,1,2,0,
   0,0,2,1,3,1,2,0,
   0,0,2,1,1,1,2,0,
   2,2,2,2,2,2,0,0,
   0,0,2,2,2,2,0,0,
   0,0,0,2,0,2,0,0,
   0,0,2,0,0,3,0,0},
}

local function drawSp(id,x,y,col,flipH)
  local sp=SPR[id]
  local skin=10  -- TIC-80 color 10 = light blue
  for i=0,63 do
    local c=sp[i+1]
    if c~=0 then
      local px = flipH and (x+7-(i%8)) or (x+(i%8))
      local py = y+math.floor(i/8)
      if c==1 then pix(px,py,skin)
      elseif c==2 then pix(px,py,col)
      else pix(px,py,0) end
    end
  end
end

local function drawPlayer(p)
  local dir=p.dir or {0,1}
  local dx,dy=dir[1],dir[2]
  local step=math.floor(p.walkAnim/4)%2  -- 0 or 1
  local id,flip=1,false
  if dy>0 then id=1+step
  elseif dy<0 then id=3+step
  elseif dx>0 then id=5+step; flip=false
  else id=5+step; flip=true end
  drawSp(id,p.x,p.y,p.color,flip)
end

local function drawPlayers()
  for _,p in ipairs(players) do
    if p.alive then drawPlayer(p) end
  end
end

local function countAlive()
  local n,last=0,nil
  for _,p in ipairs(players) do
    if p.alive then n=n+1; last=p end
  end
  return n,last
end

-- ── title screen ──────────────────────────────────────────────────────────────

local function drawTitle()
  cls(0)
  titleTimer=titleTimer+1
  if titleTimer==1 then startMusic() end

  -- animated border
  local t=titleTimer
  for i=0,29 do
    local c=(t+i)%16
    rect(i*8,0,8,4,c)
    rect(i*8,132,8,4,c)
  end

  -- print returns the text width; draw off-screen first to centre the title
  local tw=print("BLASTIC",0,-40,12,false,3,true) or 0
  print("BLASTIC",(240-tw)//2,18,12,false,3,true)
  print("4 PLAYERS",62,44,11,false,2,true)

  rectb(28,62,184,52,5)
  print("P1: Arrows + Z  (bomb)",32,66,11,false,1,true)
  print("P2: WASD  + Tab (bomb)",32,74,11,false,1,true)
  print("P3 & P4: bots",32,82,9,false,1,true)
  print("Last survivor wins!",36,90,7,false,1,true)

  if titleTimer%60<40 then
    print("Press Z or Tab to start",34,120,12,false,1,true)
  end

  if btnp(4) or btnp(12) or titleTimer>300 then
    state="game"
    init()
  end
end

-- ── match score ──────────────────────────────────────────────────────────────

-- Zwraca nową tabelę wyników; remis (winnerId=nil) nie daje punktu.
function addRoundWin(sc,winnerId)
  local out={sc[1],sc[2],sc[3],sc[4]}
  if winnerId then out[winnerId]=out[winnerId]+1 end
  return out
end

function matchWinner(sc)
  for i=1,4 do
    if sc[i]>=MATCH_WINS then return i end
  end
  return nil
end

-- ── game HUD ──────────────────────────────────────────────────────────────────

-- Pasek nad ścianą górnego rzędu (r=0): nie zasłania pola gry.
local function drawHUD()
  rect(0,0,W*TILE,7,0)
  for i,p in ipairs(players) do
    local x=(i-1)*60+2
    rect(x,1,4,5,p.alive and p.color or 13)
    local text=("W%d B%d R%d"):format(score[i], p.stats.bombs-p.bombs, p.stats.len)
    print(text,x+6,1,12,false,1,true)
  end
end

-- ── main loop ────────────────────────────────────────────────────────────────

function TIC()
  frame=frame+1
  updateMusic()

  if state=="title" then
    drawTitle()
    return
  end

  cls(FLOOR_COL)

  if state=="game" then
    updateBombs()
    updateBlasts()
    updatePlayer(players[1])
    updatePlayer(players[2])
    updateBot(players[3])
    updateBot(players[4])

    local alive,last=countAlive()
    if alive<=1 then
      state="over"
      winner=last
      score=addRoundWin(score, winner and winner.id)
      restartTimer=210
    end

    drawMap()
    drawBlasts()
    drawBombs()
    drawPlayers()
    drawHUD()

  elseif state=="over" then
    updateBombs()
    updateBlasts()
    drawMap()
    drawBlasts()
    drawBombs()
    drawPlayers()
    drawHUD()

    local msg=winner and ("P"..winner.id.." WINS!") or "DRAW!"
    local col=winner and winner.color or 7
    local mx=120-#msg*3
    print(msg,mx,50,col,false,2,true)

    if winner then
      local sub=winner.id<=2 and "YOU WIN!" or "BOT WINS"
      local sc=winner.id<=2 and 12 or 9
      print(sub,120-#sub*2,72,sc,false,1,true)
    end

    local pct=math.ceil(restartTimer/210*100)
    print("restarting "..pct.."%",88,90,13,false,1,true)

    restartTimer=restartTimer-1
    if restartTimer<=0 then
      if matchWinner(score) then
        state="match"
        restartTimer=MATCH_TIME
      else
        init()
      end
    end

  elseif state=="match" then
    drawMap()
    drawHUD()
    local w=matchWinner(score)
    local msg="P"..w.." WINS THE MATCH!"
    print(msg,120-#msg*3,50,players[w].color,false,1,true)
    print("new match in "..math.ceil(restartTimer/60).."s",88,90,13,false,1,true)

    restartTimer=restartTimer-1
    if restartTimer<=0 then
      score={0,0,0,0}
      init()
    end
  end
end

-- entry point
titleTimer=0
