-- Test harness for blastic.lua
-- Mocks TIC-80 API via env table, keeps Lua print() intact

local _held, _pressed = {}, {}

-- ── TIC-80 mock environment ───────────────────────────────────────────────────

local env = {}
env.btn   = function(i) return _held[i] or false end
env.btnp  = function(i) return _pressed[i] or false end
env.cls   = function() end
env.rect  = function() end
env.rectb = function() end
env.circ  = function() end
env.circb = function() end
env.tri   = function() end
local _pmem={}
env.pmem  = function(i,v) if v then _pmem[i]=v end return _pmem[i] or 0 end
env.line  = function() end
env.pix   = function() end
env.print = function() end  -- TIC-80 screen draw, shadows Lua's print inside game
env.time  = function() return 42 end  -- fixed seed → deterministic map & bot RNG
env.poke  = function() end
env.peek  = function() return 0 end
env.sfx   = function() end
setmetatable(env, {__index = _G})

-- ── Load game ────────────────────────────────────────────────────────────────

-- the source by default; check.py also passes the minified code that goes into the cart
local f = io.open(arg and arg[1] or "blastic.lua")
if not f then error("run from the repository root") end
local src = f:read("*a"); f:close()
local chunk, err = load(src, "blastic", "t", env)
if not chunk then error("load error: " .. err) end
chunk()

-- ── Helpers ───────────────────────────────────────────────────────────────────

local pass, fail = 0, 0

local function check(name, cond, msg)
  if cond then
    io.write(string.format("  PASS  %s\n", name))
    pass = pass + 1
  else
    io.write(string.format("  FAIL  %s%s\n", name, msg and (": "..msg) or ""))
    fail = fail + 1
  end
  io.flush()
end

local function clear_inputs() _held={}; _pressed={} end

local function run_frames(n)
  for _=1,n do
    clear_inputs()
    env.TIC()
  end
  clear_inputs()
end

local function press_frame(btn_id)
  clear_inputs()
  _pressed[btn_id]=true
  env.TIC()
  clear_inputs()
end

-- Fresh game state (bypasses title screen)
local function new_game()
  env.init()
end

-- ── TEST: title screen ────────────────────────────────────────────────────────

io.write("\n=== intro and title screen ===\n")
check("the game opens with the intro", env.state=="intro", "got: "..tostring(env.state))
run_frames(400)
check("the intro hands over to the title", env.state=="title", "got: "..tostring(env.state))
local t0=env.titleTimer
run_frames(5)
check("titleTimer increments", env.titleTimer==t0+5, "got: "..tostring(env.titleTimer))

io.write("\n=== auto-start ===\n")
run_frames(env.TITLE_IDLE-env.titleTimer)
check("stays on the title until idle", env.state=="title", "state="..tostring(env.state))
run_frames(1)
check("auto-starts the battle demo when idle", env.state=="game", "state="..tostring(env.state))

-- ── TEST: initial game state ──────────────────────────────────────────────────

io.write("\n=== initial game state ===\n")
new_game()
check("4 players", #env.players==4, "got "..#env.players)
local alive=0
for _,p in ipairs(env.players) do if p.alive then alive=alive+1 end end
check("all 4 alive", alive==4, "alive="..alive)
check("no bombs", #env.bombs==0)
check("no blasts", #env.blasts==0)
check("P1 at (1,1)", env.players[1].c==1 and env.players[1].r==1,
      ("c=%d r=%d"):format(env.players[1].c, env.players[1].r))
check("P2 at top-right", env.players[2].c==env.W-2 and env.players[2].r==1)
check("P3 at bottom-left", env.players[3].c==1 and env.players[3].r==env.H-2)
check("P4 at bottom-right", env.players[4].c==env.W-2 and env.players[4].r==env.H-2)

-- ── TEST: P1 movement ─────────────────────────────────────────────────────────

io.write("\n=== P1 movement ===\n")
new_game()
local ox = env.players[1].x
for _=1,10 do _held[3]=true; env.TIC() end  -- B_RIGHT=3
clear_inputs()
check("P1 moved right", env.players[1].x > ox,
      ("x %d->%d"):format(ox, env.players[1].x))
check("P1 moved at least 1 step right",
      env.players[1].x >= ox + env.SPEED,
      ("expected >=%d got %d"):format(ox+env.SPEED, env.players[1].x))

-- ── TEST: bomb placement ──────────────────────────────────────────────────────

io.write("\n=== bomb placement ===\n")
new_game()
-- P1 is at (1,1); no bot interference since we just init'd
press_frame(4)  -- B_BOMB=4
check("bomb placed", #env.bombs==1, "bombs="..#env.bombs)
if #env.bombs==1 then
  local b=env.bombs[1]
  check("bomb at P1 cell (1,1)", b.c==1 and b.r==1,
        ("at (%d,%d)"):format(b.c, b.r))
  check("bomb timer = BOMB_TIMER", b.t==env.BOMB_TIMER, "t="..b.t)
  check("bomb owner = P1", b.owner==env.players[1])
  check("P1 bomb counter incremented", env.players[1].bombs==1)
end

-- duplicate press should not exceed MAX_BOMBS
press_frame(4)
press_frame(4)
press_frame(4)
check("can't exceed MAX_BOMBS", env.players[1].bombs<=env.MAX_BOMBS,
      "bombs="..env.players[1].bombs)

-- ── TEST: bomb explosion ──────────────────────────────────────────────────────

io.write("\n=== bomb explosion ===\n")
new_game()
press_frame(4)  -- place bomb at (1,1)
run_frames(env.BOMB_TIMER + 2)
-- bots may have placed their own bombs; check P1's bomb is gone specifically
local p1_bomb_present=false
for _,b in ipairs(env.bombs) do if b.owner==env.players[1] then p1_bomb_present=true end end
check("P1 bomb exploded after BOMB_TIMER", not p1_bomb_present)
check("blast cells created", #env.blasts > 0, "blasts="..#env.blasts)
-- center blast must exist at (1,1)
local center_blast=false
for _,bl in ipairs(env.blasts) do
  if bl.c==1 and bl.r==1 then center_blast=true; break end
end
check("center blast at bomb origin (1,1)", center_blast)
-- P1 bomb counter restored after explosion
check("P1 bomb counter restored", env.players[1].bombs==0,
      "bombs="..env.players[1].bombs)

-- ── TEST: blast timeout ───────────────────────────────────────────────────────

io.write("\n=== blast timeout ===\n")
new_game()
-- disable bots so only P1's bomb affects blasts
env.players[3].alive=false
env.players[4].alive=false
press_frame(4)  -- P1 bomb at (1,1)
run_frames(env.BOMB_TIMER + 2)
local blasts_after_boom = #env.blasts
check("blasts exist after explosion", blasts_after_boom > 0, "blasts="..blasts_after_boom)
run_frames(env.BLAST_TIME + 2)
check("all blasts cleared after BLAST_TIME", #env.blasts==0, "still="..#env.blasts)

-- ── TEST: player death ────────────────────────────────────────────────────────

io.write("\n=== player death ===\n")
new_game()
env.players[3].alive=false; env.players[4].alive=false  -- no bot bombs
-- Place bomb at (1,1) then move P1 away
env.players[1].c, env.players[1].r = 1, 1
env.players[1].x, env.players[1].y = env.gpx(1), env.gpy(1)
press_frame(4)   -- bomb at (1,1)
for _=1,30 do _held[3]=true; env.TIC() end  -- P1 moves right
clear_inputs()
-- Run until bomb explodes but stop before blast expires (BLAST_TIME=30 frames)
-- After 30 movement frames: bomb.t = BOMB_TIMER-30; need 10+ blast frames remaining
run_frames(env.BOMB_TIMER - 10)
-- Move P1 BACK onto blast cell
env.players[1].c, env.players[1].r = 1, 1
env.players[1].x, env.players[1].y = env.gpx(1), env.gpy(1)
run_frames(1)  -- isBlast check triggers
check("P1 dies when on blast cell", not env.players[1].alive)

-- ── TEST: bot AI ──────────────────────────────────────────────────────────────

io.write("\n=== bot AI ===\n")
new_game()
check("P3 botDir initialized", env.players[3].botDir ~= nil)
check("P4 botDir initialized", env.players[4].botDir ~= nil)
check("P3 botBombTimer=0", env.players[3].botBombTimer == 0)
check("P3 botEscape=0",    env.players[3].botEscape == 0)

local p3x0, p3y0 = env.players[3].x, env.players[3].y
local p4x0, p4y0 = env.players[4].x, env.players[4].y
run_frames(120)
local p3_moved = (env.players[3].x ~= p3x0 or env.players[3].y ~= p3y0)
local p4_moved = (env.players[4].x ~= p4x0 or env.players[4].y ~= p4y0)
check("P3 moved or died", p3_moved or not env.players[3].alive)
check("P4 moved or died", p4_moved or not env.players[4].alive)

-- ── TEST: game over ───────────────────────────────────────────────────────────

io.write("\n=== game over ===\n")
new_game()
env.players[2].alive=false
env.players[3].alive=false
env.players[4].alive=false
run_frames(2)
check("state='over' with 1 survivor", env.state=="over", "state="..tostring(env.state))
check("winner=P1", env.winner and env.winner.id==1,
      "winner="..(env.winner and env.winner.id or "nil"))

-- draw: all dead
new_game()
for _,p in ipairs(env.players) do p.alive=false end
run_frames(2)
check("state='over' on draw", env.state=="over", "state="..tostring(env.state))
check("winner=nil on draw", env.winner==nil,
      "winner="..(env.winner and env.winner.id or "nil"))

-- ── TEST: auto-restart ────────────────────────────────────────────────────────

io.write("\n=== auto-restart ===\n")
new_game()
env.players[2].alive=false; env.players[3].alive=false; env.players[4].alive=false
run_frames(2)  -- enter "over" state
env.restartTimer = 3
run_frames(5)  -- timer hits 0, init() is called
check("restarts after timer", env.state=="game", "state="..tostring(env.state))
check("players reset on restart", #env.players==4)

-- ── TEST: map generation ──────────────────────────────────────────────────────

io.write("\n=== map generation ===\n")
new_game()
local border_ok=true
for c=0,env.W-1 do
  if env.mget(c,0)~=env.T_WALL or env.mget(c,env.H-1)~=env.T_WALL then
    border_ok=false
  end
end
for r=0,env.H-1 do
  if env.mget(0,r)~=env.T_WALL or env.mget(env.W-1,r)~=env.T_WALL then
    border_ok=false
  end
end
check("borders all walls", border_ok)
check("grid pillar at (2,2)", env.mget(2,2)==env.T_WALL)
check("grid pillar at (4,4)", env.mget(4,4)==env.T_WALL)
check("grid pillar at (2,4)", env.mget(2,4)==env.T_WALL)
local spawns_ok=true
for _,s in ipairs(env.STARTS) do
  if env.mget(s[1],s[2])~=env.T_EMPTY then spawns_ok=false end
end
check("spawn corners clear", spawns_ok)

-- ── TEST: chain reaction ──────────────────────────────────────────────────────

io.write("\n=== chain reaction ===\n")

-- open arena, no bots, no bombs; bombs are placed directly with a chosen timer
local function open_arena(owner_ids)
  new_game()
  for r=1,env.H-2 do
    for c=1,env.W-2 do env.map[r][c]=env.T_EMPTY end
  end
  for _,id in ipairs(owner_ids or {}) do
    env.players[id].alive=false
  end
  env.bombs={}
end

local function add_bomb(owner,c,r,t)
  local b={c=c,r=r,t=t,owner=owner}
  env.bombs[#env.bombs+1]=b
  owner.bombs=owner.bombs+1
  return b
end

local function bomb_at(c,r)
  for _,b in ipairs(env.bombs) do
    if b.c==c and b.r==r then return true end
  end
  return false
end

-- adjacent bomb chains in the same tick
open_arena({3,4})
add_bomb(env.players[1],5,5,1)        -- explodes this tick
add_bomb(env.players[2],6,5,env.BOMB_TIMER)
run_frames(1)
check("adjacent bomb chains in the same tick", not bomb_at(6,5),
      "bomb at (6,5) still pending")

-- three-bomb chain A->B->C resolves in one tick, each bomb explodes once
open_arena({3,4})
local explosions=0
local real_boom=env.sndExplosion
env.sndExplosion=function() explosions=explosions+1 end
local ca=add_bomb(env.players[1],5,5,1)
add_bomb(env.players[2],6,5,env.BOMB_TIMER)   -- covered by A (BLAST_LEN reach)
add_bomb(env.players[1],8,5,env.BOMB_TIMER)   -- covered by B only
run_frames(1)
env.sndExplosion=real_boom
check("three-bomb chain resolves in one tick", #env.bombs==0,
      "pending="..#env.bombs)
check("each chained bomb explodes exactly once", explosions==3,
      "explosions="..explosions)
check("owner bomb counts back to 0",
      env.players[1].bombs==0 and env.players[2].bombs==0,
      ("P1=%d P2=%d"):format(env.players[1].bombs, env.players[2].bombs))

-- wall between bombs shields the second one
open_arena({3,4})
env.map[5][6]=env.T_WALL
add_bomb(env.players[1],5,5,1)
add_bomb(env.players[2],7,5,env.BOMB_TIMER)
run_frames(1)
check("bomb behind wall does not chain", bomb_at(7,5))
-- ── TEST: power-ups ───────────────────────────────────────────────────────────

io.write("\n=== power-ups ===\n")

-- P1 walks one cell right onto a power-up at (2,1); bots are removed
local function walk_onto_right(kind, setup)
  new_game()
  env.players[3].alive=false; env.players[4].alive=false
  env.map[1][2]=env.T_EMPTY
  env.powerups={{c=2,r=1,kind=kind}}
  if setup then setup(env.players[1]) end
  for _=1,20 do _held[3]=true; env.TIC() end
  clear_inputs()
end

walk_onto_right("B")
check("P1 reached power-up cell", env.players[1].c==2, "c="..env.players[1].c)
check("bomb power-up adds one bomb", env.players[1].stats.bombs==env.MAX_BOMBS+1,
      "bombs="..env.players[1].stats.bombs)
check("collected power-up removed from map", #env.powerups==0, "left="..#env.powerups)

walk_onto_right("R")
check("range power-up adds one range", env.players[1].stats.len==env.BLAST_LEN+1,
      "len="..env.players[1].stats.len)

walk_onto_right("S")
check("shield power-up grants shield", env.players[1].shield==true)
check("shield power-up removed from map", #env.powerups==0)

walk_onto_right("B", function(p) p.stats.bombs=env.BOMB_CAP end)
check("bomb cap holds", env.players[1].stats.bombs==env.BOMB_CAP,
      "bombs="..env.players[1].stats.bombs)

walk_onto_right("R", function(p) p.stats.len=env.LEN_CAP end)
check("range cap holds", env.players[1].stats.len==env.LEN_CAP,
      "len="..env.players[1].stats.len)

-- shield absorbs exactly one hit and protects for the rest of that blast
new_game()
env.players[3].alive=false; env.players[4].alive=false
local sp=env.players[1]
sp.shield=true
local function blast_on_p1() env.blasts={{c=1,r=1,t=env.BLAST_TIME}} end
blast_on_p1(); env.TIC()
check("shield absorbs first hit", sp.alive and not sp.shield,
      ("alive=%s shield=%s"):format(tostring(sp.alive), tostring(sp.shield)))
for _=1,env.BLAST_TIME-1 do blast_on_p1(); env.TIC() end
check("invulnerable for the rest of the blast", sp.alive)
for _=1,env.SHIELD_INVUL do blast_on_p1(); env.TIC() end
check("no second shield: hit after invulnerability kills", not sp.alive)

-- a blast destroys power-ups on its tiles
new_game()
env.players[3].alive=false; env.players[4].alive=false
env.powerups={{c=3,r=3,kind="B"},{c=4,r=3,kind="R"}}
env.map[3][4]=env.T_EMPTY; env.map[3][5]=env.T_EMPTY  -- a block in reach would drop a new item
env.bombs={{c=3,r=3,t=1,len=2}}
env.TIC()
local left={}
for _,pu in ipairs(env.powerups) do left[#left+1]=pu.c..","..pu.r end
check("blast destroys power-ups on its tiles", #env.powerups==0,
      "left="..table.concat(left, " "))

-- bomb range follows the owner's stats.len at placement
new_game()
env.players[3].alive=false; env.players[4].alive=false
env.players[1].stats.len=4
for c=1,env.W-2 do env.map[1][c]=env.T_EMPTY end
press_frame(4)
run_frames(env.BOMB_TIMER)
local function blast_at(c,r)
  for _,bl in ipairs(env.blasts) do if bl.c==c and bl.r==r then return true end end
  return false
end
check("range 4 bomb reaches 4 tiles", blast_at(5,1))
check("range 4 bomb stops at 4 tiles", not blast_at(6,1))
-- ── TEST: arena shrink ────────────────────────────────────────────────────────

io.write("\n=== arena shrink ===\n")

local function open_count()
  local n=0
  for r=0,env.H-1 do
    for c=0,env.W-1 do
      if env.mget(c,r)~=env.T_WALL then n=n+1 end
    end
  end
  return n
end

local function line_open(is_member)
  local n=0
  for r=0,env.H-1 do
    for c=0,env.W-1 do
      if is_member(c,r) and env.mget(c,r)~=env.T_WALL then n=n+1 end
    end
  end
  return n
end
local function col_open(x) return line_open(function(c) return c==x end) end
local function row_open(y) return line_open(function(_,r) return r==y end) end

local function close_steps(n)
  new_game()
  env.players[3].alive=false; env.players[4].alive=false
  env.players[1].alive=false; env.players[2].alive=false
  for _=1,n do
    env.roundFrames=env.shrinkAt-1
    env.updateShrink()
  end
end

local function tinted_tiles()
  local n=0
  local real_rect=env.rect
  env.rect=function(_,_,_,_,col) if col==9 then n=n+1 end end
  env.TIC()
  env.rect=real_rect
  return n
end

new_game()
env.players[3].alive=false; env.players[4].alive=false
local open_before=open_count()
run_frames(env.SHRINK_DELAY+env.SHRINK_CYCLE-2)
check("no tile shrinks before the cycle ends", open_count()==open_before,
      ("open %d->%d"):format(open_before, open_count()))
run_frames(1)
check("the whole outline closes at once",
      col_open(1)==0 and col_open(env.W-2)==0 and row_open(1)==0 and row_open(env.H-2)==0
      and col_open(2)>0 and row_open(2)>0,
      ("col1=%d row1=%d col2=%d"):format(col_open(1), row_open(1), col_open(2)))

close_steps(3)
check("each step closes the next ring, keeping a rectangle",
      col_open(3)==0 and row_open(3)==0 and col_open(env.W-4)==0 and row_open(env.H-4)==0
      and col_open(4)>0 and row_open(4)>0)

-- the arena fills the screen under the HUD; its edge is one thin line on all four sides
new_game()
local ring_walls,frame_line=0,false
do
  local real_rect,real_rectb=env.rect,env.rectb
  env.rect=function(x,y,w,h,col)
    local ring=x<0 or x>=240 or y<env.TILE or y>=136
    if w==env.TILE and col==13 and ring then ring_walls=ring_walls+1 end
  end
  env.rectb=function(x,y,w,h,col)
    if x==0 and y==env.TILE and w==240 and h==136-env.TILE then  -- on the edge tiles, like the other sides
      frame_line=true
    end
  end
  env.state="game"
  env.TIC()
  env.rect,env.rectb=real_rect,real_rectb
end
check("the outer wall ring is not drawn as wall tiles", ring_walls==0, "ring wall tiles="..ring_walls)
check("one even line frames the arena on all four sides", frame_line)
check("the arena fills the screen below the HUD",
      env.gpx(1)==0 and env.gpx(env.W-2)==240-env.TILE and env.gpy(1)==env.TILE
      and env.gpy(env.H-2)==136-env.TILE)

-- the ring blinks faster as it nears closing
new_game()
env.players[3].alive=false; env.players[4].alive=false
local function toggles(from_frame,n)
  env.roundFrames=from_frame
  local count,last=0,nil
  for _=1,n do
    local on=tinted_tiles()>0
    if last~=nil and on~=last then count=count+1 end
    last=on
  end
  return count
end
local warn_start=env.shrinkAt-env.SHRINK_WARN
local early=toggles(warn_start,40)
local late=toggles(warn_start+env.SHRINK_WARN-41,40)
check("ring blinks faster near closing", late>early, ("early=%d late=%d"):format(early, late))
env.roundFrames=env.shrinkAt-env.SHRINK_WARN-10
check("nothing blinks during the pause", tinted_tiles()==0)

-- the zone stops at a small strip in the middle, so it never kills everyone at once
new_game()
for _=1,env.SHRINK_DELAY+env.SHRINK_CYCLE*(env.W+env.H) do env.updateShrink() end
local left_open,minc,maxc,minr,maxr=0,99,0,99,0
for r=1,env.H-2 do for c=1,env.W-2 do
  if env.mget(c,r)~=env.T_WALL then
    left_open=left_open+1
    minc,maxc=math.min(minc,c),math.max(maxc,c); minr,maxr=math.min(minr,r),math.max(maxr,r)
  end
end end
check("the zone stops at a small strip in the middle",
      left_open>0 and maxc-minc+1<=4 and maxr-minr+1<=2
      and minc+maxc==env.W-1 and minr+maxr==env.H-1,
      ("open=%d cols %d-%d rows %d-%d"):format(left_open,minc,maxc,minr,maxr))

new_game()
env.roundFrames=env.shrinkAt-1
local victim=env.players[1]
victim.c,victim.r=1,1
victim.x,victim.y=env.gpx(1),env.gpy(1)
env.updateShrink()
check("player in the closing step dies", not victim.alive)
check("closed tile becomes wall", env.mget(1,1)==env.T_WALL)

new_game()
env.roundFrames=env.shrinkAt-1
local owner=env.players[2]
owner.bombs=1
env.bombs={{c=1,r=1,t=env.BOMB_TIMER,owner=owner}}
env.updateShrink()
check("bomb in the closing step removed", #env.bombs==0, "bombs="..#env.bombs)
check("bomb owner slot freed", owner.bombs==0, "bombs="..owner.bombs)

-- a bot standing in the blinking side column walks inward and survives the closing
new_game()
for _,id in ipairs({1,4}) do env.players[id].alive=false end
env.bombs={}; env.powerups={}
for r=1,env.H-2 do for c=1,env.W-2 do env.map[r][c]=env.T_WALL end end
for r=1,7 do env.map[r][1]=env.T_EMPTY end
for c=1,4 do env.map[7][c]=env.T_EMPTY end
local shrink_bot=env.players[3]
shrink_bot.c,shrink_bot.r=1,1
shrink_bot.x,shrink_bot.y=env.gpx(1),env.gpy(1)
env.roundFrames=env.shrinkAt-env.SHRINK_WARN
for _=1,env.SHRINK_WARN do env.TIC() end
check("bot leaves the closing step and survives", shrink_bot.alive and shrink_bot.c>1,
      ("alive=%s c=%d"):format(tostring(shrink_bot.alive), shrink_bot.c))

new_game()
local frames=0
while env.state=="game" and frames<6000 do
  run_frames(1)
  frames=frames+1
end
check("round ends within 6000 frames", env.state=="over", "frames="..frames)
-- ── TEST: bot AI (flee, escape, BFS) ──────────────────────────────────────────

local function open_arena()
  for r=1,env.H-2 do
    for c=1,env.W-2 do env.map[r][c]=env.T_EMPTY end
  end
end

local function only_bot_alive(keep)
  for _,p in ipairs(env.players) do
    if p.id~=keep then p.alive=false end
  end
end

io.write("\n=== bot flees ticking bomb ===\n")
new_game()
for r=1,env.H-2 do
  for c=1,env.W-2 do env.map[r][c]=env.T_WALL end
end
for c=1,5 do env.map[15][c]=env.T_EMPTY end   -- 1-wide corridor, bot at its end
only_bot_alive(3)
env.players[2].alive=true   -- far human, keeps the game running
env.bombs={}; env.blasts={}
local flee_bot=env.players[3]
flee_bot.c, flee_bot.r = 1, 15
flee_bot.x, flee_bot.y = env.gpx(1), env.gpy(15)
env.bombs[1]={c=1, r=15, t=60, owner=flee_bot}
run_frames(65)  -- bomb explodes at frame 60, blast lasts BLAST_TIME
check("bot flees ticking bomb and survives blast", flee_bot.alive,
      ("c=%d r=%d"):format(flee_bot.c, flee_bot.r))

io.write("\n=== bot wanders clear of a ticking bomb's blast line ===\n")
new_game()
for r=1,env.H-2 do
  for c=1,env.W-2 do env.map[r][c]=env.T_WALL end
end
for c=1,10 do env.map[15][c]=env.T_EMPTY end
only_bot_alive(3)
env.players[2].alive=true
env.bombs={}; env.blasts={}
local wander_bot=env.players[3]
wander_bot.c, wander_bot.r = 9, 15
wander_bot.x, wander_bot.y = env.gpx(9), env.gpy(15)
wander_bot.botDir={-1,0}
wander_bot.botDirTimer=60
env.bombs[1]={c=6, r=15, t=100, owner=env.players[2], len=2}
local entered_blast_line=false
for _=1,95 do
  env.TIC()
  if wander_bot.c>=4 and wander_bot.c<=8 then entered_blast_line=true end
end
check("wandering bot stays out of the blast line", not entered_blast_line and wander_bot.alive,
      "c="..wander_bot.c)

io.write("\n=== bot picks up items and bombs enemies in line ===\n")
local function bot_arena()
  new_game()
  open_arena()
  only_bot_alive(3)
  env.players[2].alive=true
  env.bombs={}; env.blasts={}; env.powerups={}
  local b=env.players[3]
  b.c, b.r = 10, 5
  b.x, b.y = env.gpx(10), env.gpy(5)
  return b
end

local pick_bot=bot_arena()
env.players[2].c, env.players[2].r = 25, 12
env.players[2].x, env.players[2].y = env.gpx(25), env.gpy(12)
env.powerups={{c=14,r=5,kind="S"}}
run_frames(120)
check("bot walks to a nearby item and takes it", pick_bot.shield==true and #env.powerups==0,
      "shield="..tostring(pick_bot.shield))

local hunt_bot=bot_arena()
env.players[2].c, env.players[2].r = 12, 5
env.players[2].x, env.players[2].y = env.gpx(12), env.gpy(5)
run_frames(5)
local hunt_bombs=0
for _,b in ipairs(env.bombs) do if b.owner==hunt_bot then hunt_bombs=hunt_bombs+1 end end
check("bot lays a bomb when an enemy stands in its blast line", hunt_bombs==1, "bombs="..hunt_bombs)

io.write("\n=== bot route tie-break order ===\n")
new_game()
local orders_ok,distinct={}
orders_ok=true
local seen_orders={}
local real_time=env.time
local tick=0
env.time=function() tick=tick+1; return tick end
for _=1,20 do
  env.init()
  local p=env.players[3]
  local keys={}
  for _,d in ipairs(p.botOrder) do keys[#keys+1]=d[1]..","..d[2] end
  local sorted={table.unpack(keys)}
  table.sort(sorted)
  if #p.botOrder~=4 or table.concat(sorted,";")~="-1,0;0,-1;0,1;1,0" then orders_ok=false end
  seen_orders[table.concat(keys,";")]=true
end
env.time=real_time
local n_orders=0
for _ in pairs(seen_orders) do n_orders=n_orders+1 end
check("each bot gets all four directions in some order", orders_ok)
check("the order differs between rounds", n_orders>1, "distinct="..n_orders)

io.write("\n=== bot heads for the nearest enemy ===\n")
local chase_bot=bot_arena()
env.map[9][5]=env.T_BLOCK
env.players[2].c, env.players[2].r = 20, 5
env.players[2].x, env.players[2].y = env.gpx(20), env.gpy(5)
run_frames(80)
check("bot walks towards the enemy instead of the block", chase_bot.c>=8 and chase_bot.r==5,
      ("c=%d r=%d"):format(chase_bot.c, chase_bot.r))

io.write("\n=== bot traps an enemy in a dead end ===\n")
new_game()
for r=1,env.H-2 do
  for c=1,env.W-2 do env.map[r][c]=env.T_WALL end
end
for c=1,8 do env.map[15][c]=env.T_EMPTY end
env.players[1].alive=false; env.players[2].alive=false
env.bombs={}; env.blasts={}; env.powerups={}
local hunter,prey=env.players[3],env.players[4]
hunter.c, hunter.r = 5, 15
hunter.x, hunter.y = env.gpx(5), env.gpy(15)
prey.c, prey.r = 1, 15
prey.x, prey.y = env.gpx(1), env.gpy(15)
run_frames(400)
check("bot kills an enemy it has trapped and survives", not prey.alive and hunter.alive,
      "prey="..tostring(prey.alive).." hunter="..tostring(hunter.alive))

io.write("\n=== bot does not suicide in dead-end ===\n")
new_game()
for r=1,env.H-2 do
  for c=1,env.W-2 do env.map[r][c]=env.T_WALL end
end
env.map[15][1]=env.T_EMPTY   -- P3 cell
env.map[15][2]=env.T_BLOCK   -- only target, bomb would blast the bot itself
only_bot_alive(3)
env.players[2].alive=true
env.bombs={}; env.blasts={}
local dead_bot=env.players[3]
dead_bot.c, dead_bot.r = 1, 15
dead_bot.x, dead_bot.y = env.gpx(1), env.gpy(15)
run_frames(3)
local own_bombs=0
for _,b in ipairs(env.bombs) do if b.owner==dead_bot then own_bombs=own_bombs+1 end end
check("bot does not place bomb without escape", own_bombs==0, "own="..own_bombs)

io.write("\n=== bot BFS path helper ===\n")
local function build_map(rows)
  env.map={}
  for r,row in ipairs(rows) do
    env.map[r-1]={}
    for c=1,#row do
      env.map[r-1][c-1]= row:sub(c,c)=="#" and env.T_WALL or env.T_EMPTY
    end
  end
end
build_map({
  "#####",
  "#...#",
  "#.#.#",
  "#...#",
  "#####",
})
local function open_cell(c,r) return env.mget(c,r)==env.T_EMPTY end
local path = env.botPath and env.botPath(1,1,open_cell,function(c,r) return c==3 and r==3 end)
check("BFS finds path around wall", path~=nil)
check("BFS path is shortest (4 steps)", path and #path==4, "len="..(path and #path or -1))
check("BFS path ends at goal", path and path[#path] and path[#path].c==3 and path[#path].r==3)
local adjacent_ok=true
local last_c, last_r = 1, 1
for _,cell in ipairs(path or {}) do
  if math.abs(cell.c-last_c)+math.abs(cell.r-last_r)~=1 then adjacent_ok=false end
  last_c, last_r = cell.c, cell.r
end
check("BFS path steps are adjacent", path~=nil and adjacent_ok)
local unreachable = env.botPath and env.botPath(1,1,open_cell,function(c,r) return c==2 and r==2 end)
check("BFS returns nil for unreachable goal", unreachable==nil)
new_game()
-- ── TEST: match score ─────────────────────────────────────────────────────────

io.write("\n=== match score ===\n")
env.score={0,0,0,0}
local won=env.addRoundWin({0,0,0,0},2)
check("addRoundWin adds one win to the winner", won[2]==1 and won[1]==0)
local src_score={0,0,0,0}
env.addRoundWin(src_score,3)
check("addRoundWin does not mutate its input", src_score[3]==0)
local drawn=env.addRoundWin({1,1,0,0},nil)
check("draw adds no point", drawn[1]==1 and drawn[2]==1 and drawn[3]==0 and drawn[4]==0)
check("no match winner below MATCH_WINS", env.matchWinner({2,2,2,0})==nil)
check("matchWinner returns player at MATCH_WINS", env.matchWinner({0,3,0,0})==2)

new_game()
env.score={0,0,0,0}
env.players[2].alive=false; env.players[3].alive=false; env.players[4].alive=false
run_frames(2)
check("round win scored for P1", env.score[1]==1, "score1="..env.score[1])
env.restartTimer=1
run_frames(1)
check("next round starts after one win", env.state=="game", "state="..tostring(env.state))

new_game()
env.score={1,0,0,0}
for _,p in ipairs(env.players) do p.alive=false end
run_frames(2)
check("draw gives no point", env.score[1]==1 and env.score[2]==0 and env.score[3]==0 and env.score[4]==0)

new_game()
env.score={2,0,0,0}
env.players[2].alive=false; env.players[3].alive=false; env.players[4].alive=false
run_frames(2)
check("third round win gives P1 the match", env.matchWinner(env.score)==1)
env.restartTimer=1
run_frames(1)
check("match-over screen after third win", env.state=="match", "state="..tostring(env.state))

run_frames(env.MATCH_TIME+1)
check("scores reset after match", env.score[1]==0 and env.score[2]==0 and env.score[3]==0 and env.score[4]==0)
check("new match starts after match-over", env.state=="game", "state="..tostring(env.state))
-- ── TEST: sound and animation ─────────────────────────────────────────────────

io.write("\n=== sound and animation ===\n")
local realSfx=env.sfx
local sfx_log={}
env.sfx=function(id) sfx_log[#sfx_log+1]=id end

new_game()
env.players[3].alive=false; env.players[4].alive=false
sfx_log={}
press_frame(4)  -- P1 places bomb
local slot5=0
for _,id in ipairs(sfx_log) do if id==5 then slot5=slot5+1 end end
check("bomb placement plays slot 5 once", slot5==1,
      "log="..table.concat(sfx_log,","))

sfx_log={}
local ok_pick=pcall(env.sndPickup)
check("sndPickup plays slot 6", ok_pick and #sfx_log==1 and sfx_log[1]==6,
      "log="..table.concat(sfx_log,","))

sfx_log={}
local ok_shield=pcall(env.sndShield)
check("sndShield plays slot 7", ok_shield and #sfx_log==1 and sfx_log[1]==7,
      "log="..table.concat(sfx_log,","))

new_game()
env.players[3].alive=false; env.players[4].alive=false
env.blasts[#env.blasts+1]={c=env.players[1].c, r=env.players[1].r, t=env.BLAST_TIME}
run_frames(1)
check("P1 dies on blast", not env.players[1].alive)
check("death animation starts", env.players[1].deathT==env.DEATH_TIME,
      "deathT="..tostring(env.players[1].deathT))
run_frames(env.DEATH_TIME)
check("death animation timer decays to 0", env.players[1].deathT==0,
      "deathT="..tostring(env.players[1].deathT))
check("death keeps alive=false", not env.players[1].alive)

for _,st in ipairs({"intro","title","game","over"}) do
  new_game()
  env.titleTimer=0; env.restartTimer=100
  env.bombs[#env.bombs+1]={c=3,r=3,t=10}
  env.blasts[#env.blasts+1]={c=5,r=5,t=env.BLAST_TIME}
  env.players[2].alive=false; env.players[2].deathT=env.DEATH_TIME
  env.state=st
  local ok,err=pcall(env.TIC)
  check("drawing does not crash in state "..st, ok, tostring(err))
end

env.sfx=realSfx

-- ── TEST: flame colours ───────────────────────────────────────────────────────

io.write("\n=== flame colours ===\n")

-- Sweetie-16: 4 yellow, 3 orange, 2 red. A fresh blast must start yellow and end red.
local function blast_colour(t)
  new_game()
  env.blasts={{c=3,r=1,t=t}}
  env.bombs={}
  local seen
  local real_circ=env.circ
  env.circ=function(_,_,_,col) seen=col end
  env.TIC()
  env.circ=real_circ
  return seen
end
check("fresh blast is yellow", blast_colour(env.BLAST_TIME)==4, "colour="..tostring(blast_colour(env.BLAST_TIME)))
check("dying blast is red", blast_colour(2)==2, "colour="..tostring(blast_colour(2)))

-- ── TEST: map fairness ────────────────────────────────────────────────────────

io.write("\n=== map fairness ===\n")

-- Walls must mirror left-right, or the right-hand corners get easier corridors.
new_game()
local asym=nil
for r=0,env.H-1 do
  for c=0,env.W-1 do
    local a=env.mget(c,r)==env.T_WALL
    local b=env.mget(env.W-1-c,r)==env.T_WALL
    if a~=b and not asym then asym=c..","..r end
  end
end
check("walls mirror left-right", asym==nil, asym and ("first mismatch at "..asym))
asym=nil
for r=0,env.H-1 do
  for c=0,env.W-1 do
    local a=env.mget(c,r)==env.T_WALL
    local b=env.mget(c,env.H-1-r)==env.T_WALL
    if a~=b and not asym then asym=c..","..r end
  end
end
check("walls mirror top-bottom", asym==nil, asym and ("first mismatch at "..asym))
local mid_pillars=0
for c=1,env.W-2 do
  for _,r in ipairs({env.H//2-1,env.H//2}) do
    if env.mget(c,r)==env.T_WALL then mid_pillars=mid_pillars+1 end
  end
end
check("no pillars in the two middle rows", mid_pillars==0, "pillars="..mid_pillars)

-- ── TEST: tuning (one starting bomb, half walking speed) ──────────────────────

io.write("\n=== tuning ===\n")

new_game()
local all_one=true
for _,p in ipairs(env.players) do
  if p.stats.bombs~=1 then all_one=false end
end
check("every player starts with one bomb", all_one)

-- a second bomb in another cell is refused while the first one is ticking
for r=1,env.H-2 do for c=1,env.W-2 do env.map[r][c]=env.T_EMPTY end end
env.players[2].alive=false; env.players[3].alive=false
env.bombs={}
press_frame(4)
local p1=env.players[1]
p1.x=env.gpx(3); p1.y=env.gpy(1); p1.c=3; p1.r=1
press_frame(4)
check("second bomb refused with one bomb", #env.bombs==1, "bombs="..#env.bombs)

-- holding right for 16 frames moves 8 px: one pixel per two frames
new_game()
for r=1,env.H-2 do for c=1,env.W-2 do env.map[r][c]=env.T_EMPTY end end
env.players[2].alive=false; env.players[3].alive=false
local start_x=env.players[1].x
for _=1,16 do
  _held[3]=true
  env.TIC()
end
clear_inputs()
check("walking is one pixel per two frames", env.players[1].x-start_x==8,
      "moved "..(env.players[1].x-start_x).." px in 16 frames")

-- ── TEST: power-up icons ──────────────────────────────────────────────────────

io.write("\n=== power-up icons ===\n")

local function icon_pixels(kind)
  new_game()
  env.powerups={{c=5,r=5,kind=kind}}
  local seen={}
  local real_pix,real_rect,real_print=env.pix,env.rect,env.print
  local x0,y0=env.gpx(5),env.gpy(5)-1  -- the item's tile, bobbing one pixel up
  env.pix=function(x,y,col)
    if x>=x0 and x<x0+8 and y>=y0 and y<y0+9 then seen[#seen+1]=x..","..y..","..col end
  end
  env.rect=function() end
  env.print=function() end
  env.TIC()
  env.pix,env.rect,env.print=real_pix,real_rect,real_print
  table.sort(seen)
  return seen
end

local a,b,c=icon_pixels("B"),icon_pixels("R"),icon_pixels("S")
check("icons are drawn with pixels", #a>10 and #b>10 and #c>10)
check("the three icons differ", table.concat(a,";")~=table.concat(b,";")
      and table.concat(b,";")~=table.concat(c,";") and table.concat(a,";")~=table.concat(c,";"))

local function uses_colour(px,col)
  for _,s in ipairs(px) do
    if tonumber(s:match(",(%d+)$"))==col then return true end
  end
  return false
end
check("no icon uses the lit bomb red", not uses_colour(a,env.BOMB_COL or 2)
      and not uses_colour(b,env.BOMB_COL or 2) and not uses_colour(c,env.BOMB_COL or 2))

-- ── TEST: shield bubble and HUD items ─────────────────────────────────────────

io.write("\n=== shield and HUD ===\n")

-- Draws one game frame; returns pix() calls in the HUD bar and the drawing calls by name.
local function draw_frame(setup)
  new_game()
  env.state="game"
  setup(env.players[1])
  local hud,calls={},{circb={},rectb={}}
  local saved={env.pix,env.circb,env.rectb}
  env.pix=function(x,y,col) if y<7 then hud[#hud+1]={x=x,y=y,col=col} end end
  env.circb=function(...) calls.circb[#calls.circb+1]={...} end
  env.rectb=function(...) calls.rectb[#calls.rectb+1]={...} end
  env.TIC()
  env.pix,env.circb,env.rectb=saved[1],saved[2],saved[3]
  return hud,calls
end

local function hud_colour_in(hud,col,x0,x1)
  for _,p in ipairs(hud) do
    if p.col==col and p.x>=x0 and p.x<x1 then return true end
  end
  return false
end

local hud_plain,plain=draw_frame(function(p) p.shield=false end)
local hud_shield,shielded=draw_frame(function(p) p.shield=true; p.invul=0 end)
local p1=env.players[1]
local round=false
for _,c in ipairs(shielded.circb) do
  if math.abs(c[1]-(p1.x+3))<=1 and math.abs(c[2]-(p1.y+3))<=1 and c[3]>=5 then round=true end
end
check("an active shield is a round bubble around the player", round)
check("an active shield draws no square frame", #shielded.rectb==#plain.rectb,
      "rectb "..#plain.rectb.." -> "..#shielded.rectb)
check("HUD shows bomb and range icons for every player",
      hud_colour_in(hud_plain,13,2,62) and hud_colour_in(hud_plain,3,2,62)
      and hud_colour_in(hud_plain,13,182,240) and hud_colour_in(hud_plain,3,182,240))
local hud_text,hud_heads={},{}
do
  new_game()
  env.state="game"
  local saved_print,saved_pix=env.print,env.pix
  env.print=function(t,x,y) if y and y<7 then hud_text[#hud_text+1]={t=tostring(t),x=x} end return 0 end
  env.pix=function(x,y,col) if y<7 then hud_heads[col]=(hud_heads[col] or 0)+1 end end
  env.TIC()
  env.print,env.pix=saved_print,saved_pix
end
local function label_in(t,x0,x1)
  for _,h in ipairs(hud_text) do if h.t==t and h.x>=x0 and h.x<x1 then return true end end
  return false
end
check("HUD marks humans P and bots C",
      label_in("P",0,60) and label_in("P",60,120) and label_in("C",120,180) and label_in("C",180,240))
local heads=true
for _,pl in ipairs(env.players) do if (hud_heads[pl.color] or 0)<4 then heads=false end end
check("HUD shows a little head in each player's colour", heads)
-- HUD: wins as dots, the zone countdown in the middle, maximum bombs, a crossed-out dead head
local hud_rects,hud_prints,hud_lines={}, {}, {}
do
  new_game()
  env.state="game"
  env.score={2,0,0,0}
  env.players[1].stats.bombs=3; env.players[1].bombs=1
  env.players[4].alive=false
  env.roundFrames=0
  local sr,sp,sl,spix=env.rect,env.print,env.line,env.pix
  env.rect=function(x,y,w,h,col) if y<7 then hud_rects[#hud_rects+1]={x=x,w=w,col=col} end end
  env.print=function(t,x,y,col) if y and y<7 then hud_prints[#hud_prints+1]={t=tostring(t),x=x,col=col} end return 0 end
  env.line=function(x0,y0,x1,y1,col) if y0<7 then hud_lines[#hud_lines+1]={x=x0,col=col} end end
  env.pix=function() end
  env.TIC()
  env.rect,env.print,env.line,env.pix=sr,sp,sl,spix
  env.score={0,0,0,0}
end
local won=0
for _,r in ipairs(hud_rects) do if r.w==3 and r.col==4 and r.x<56 then won=won+1 end end
check("HUD shows wins as filled dots", won==2, "filled="..won)
local timer=nil
for _,p in ipairs(hud_prints) do if p.x>=112 and p.x<128 and p.t:match("^%d+$") then timer=tonumber(p.t) end end
check("HUD counts down to the next zone step", timer and timer>=30 and timer<=40, "timer="..tostring(timer))
local max_shown=false
for _,p in ipairs(hud_prints) do if p.t=="3" and p.x<56 then max_shown=true end end
check("HUD shows how many bombs a player can hold", max_shown)
local crossed=false
for _,l in ipairs(hud_lines) do if l.x>=184 and l.col==2 then crossed=true end end
check("HUD crosses out a dead player's head", crossed)
check("HUD shows the shield icon only while the player has one",
      hud_colour_in(hud_shield,11,2,62) and not hud_colour_in(hud_plain,11,2,62))

-- ── TEST: corner assist and zone items ───────────────────────────────────────

io.write("\n=== corner assist ===\n")

-- 1-wide corridor going right from (3,5); the player stands half a tile below its axis
new_game()
env.state="game"
for id=2,3 do env.players[id].alive=false end  -- P4 stays, or the round would end at once
env.bombs={}; env.powerups={}
for r=1,env.H-2 do for c=1,env.W-2 do env.map[r][c]=env.T_WALL end end
env.map[env.H-2][env.W-2]=env.T_EMPTY
for c=3,8 do env.map[5][c]=env.T_EMPTY end
env.map[6][3]=env.T_EMPTY
local walker=env.players[1]
walker.x,walker.y=env.gpx(3),env.gpy(5)+4
walker.c,walker.r=3,5
for _=1,40 do _held={[3]=true}; env.TIC() end
clear_inputs()
check("a player off the corridor axis slides into it", walker.c>=5 and walker.y==env.gpy(5),
      ("c=%d y-off=%d"):format(walker.c, walker.y-env.gpy(5)))

-- the closing zone takes the items lying on it
new_game()
env.powerups={{c=1,r=1,kind="B"},{c=5,r=5,kind="R"}}
env.roundFrames=env.shrinkAt-1
env.updateShrink()
check("items in the closing zone disappear", #env.powerups==1 and env.powerups[1].c==5,
      "items="..#env.powerups)

-- a block is plain light brown with a dark brown outline
new_game()
env.state="game"
env.map[3][5]=env.T_BLOCK
local fill,edge=false,false
do
  local sr,sb=env.rect,env.rectb
  env.rect=function(x,y,w,h,col) if x==env.gpx(5) and y==env.gpy(3) and col==1 then fill=true end end
  env.rectb=function(x,y,w,h,col) if x==env.gpx(5) and y==env.gpy(3) and col==8 then edge=true end end
  env.TIC()
  env.rect,env.rectb=sr,sb
end
check("blocks are plain light brown with an outline", fill and edge)

-- ── TEST: player sprite ───────────────────────────────────────────────────────

io.write("\n=== player sprite ===\n")

-- pixels of P1 facing down, relative to its tile
local function player_pixels()
  new_game()
  env.state="game"
  local p=env.players[1]
  p.dir={0,1}; p.walkAnim=0
  local px={}
  local saved=env.pix
  env.pix=function(x,y,col)
    local dx,dy=x-p.x,y-p.y
    if dx>=0 and dx<8 and dy>=0 and dy<8 then px[#px+1]={x=dx,y=dy,col=col} end
  end
  env.TIC()
  env.pix=saved
  return px
end

local sprite=player_pixels()
local eye_cols,face,body={},0,0
for _,q in ipairs(sprite) do
  if q.col==10 then face=face+1 end
  if q.y>=6 then body=body+1 end
  if q.col==0 and q.y<6 then eye_cols[q.x]=true end
end
local eyes={}
for x in pairs(eye_cols) do eyes[#eyes+1]=x end
table.sort(eyes)
check("the face has two separate eyes", #eyes==2 and eyes[2]-eyes[1]>=2,
      "eye columns "..table.concat(eyes,","))
local colour=0
for _,q in ipairs(sprite) do if q.col==env.players[1].color then colour=colour+1 end end
check("a small face in a lot of player colour", face>=6 and face<=12 and colour>=30,
      ("face=%d colour=%d"):format(face,colour))
local legs=0
for _,q in ipairs(sprite) do if q.y==7 and q.col~=0 then legs=legs+1 end end
check("the legs show on the dark floor", legs>=2, "visible leg pixels="..legs)

-- player colours chosen by the owner: white, green, blue, red; faces stay skin-toned
local want={12,5,9,2}
local wrong=nil
for i,p in ipairs(env.players) do if p.color~=want[i] then wrong=i end end
check("players are white, green, blue and red", wrong==nil, wrong and ("player "..wrong))

-- ── TEST: helpers covered directly ────────────────────────────────────────────

io.write("\n=== helpers ===\n")

-- placeBomb: one bomb on the player's cell, owner count rises, a bomb cell refuses a second one
new_game()
open_arena()
for _,id in ipairs({2,3}) do env.players[id].alive=false end
env.bombs={}
local hp=env.players[1]
env.players[1].stats.bombs=3
press_frame(4)
check("placeBomb lays the bomb on the player's cell",
      #env.bombs==1 and env.bombs[1].c==hp.c and env.bombs[1].r==hp.r and env.bombs[1].owner==hp)
check("placeBomb counts the bomb for its owner", hp.bombs==1, "bombs="..hp.bombs)
press_frame(4)
check("placeBomb refuses a cell that already has a bomb", #env.bombs==1, "bombs="..#env.bombs)

-- dropPowerup: a destroyed block leaves an item when the roll succeeds, nothing otherwise
local real_random=math.random
local function drop_with(roll)
  new_game()
  open_arena()
  for _,id in ipairs({2,3}) do env.players[id].alive=false end
  env.powerups={}
  env.map[1][4]=env.T_BLOCK
  env.bombs={{c=3,r=1,t=1,owner=env.players[1],len=2}}
  env.players[1].bombs=1
  math.random=function(n) if n then return 1 end return roll end
  env.TIC()
  math.random=real_random
  return #env.powerups
end
check("destroyed block drops an item on a successful roll", drop_with(0)==1)
check("destroyed block drops nothing on a failed roll", drop_with(0.99)==0)

-- updateInvul: invulnerability after a shield break lasts SHIELD_INVUL frames
new_game()
open_arena()
for _,id in ipairs({2,3}) do env.players[id].alive=false end
local ip=env.players[1]
ip.shield=true
env.blasts={{c=ip.c,r=ip.r,t=env.BLAST_TIME}}
env.TIC()
check("shield break grants invulnerability", ip.invul>0 and ip.invul<=env.SHIELD_INVUL, "invul="..ip.invul)
env.blasts={}
run_frames(env.SHIELD_INVUL)
check("invulnerability runs out", ip.invul==0, "invul="..ip.invul)

-- botTryBomb / botIsTargetSpot: a bot next to a block with room to escape lays a bomb
new_game()
open_arena()
for _,id in ipairs({1,4}) do env.players[id].alive=false end
env.bombs={}
local bb=env.players[3]
env.map[bb.r][bb.c+1]=env.T_BLOCK
run_frames(10)
local bot_bombs=0
for _,b in ipairs(env.bombs) do if b.owner==bb then bot_bombs=bot_bombs+1 end end
check("bot lays a bomb next to a block when it can escape", bot_bombs>=1,
      "bombs="..bot_bombs.." owned="..bb.bombs)

-- shrinkWarnTiles: the next tiles to shrink are tinted once the delay has passed
new_game()
env.state="game"
env.roundFrames=env.shrinkAt-env.SHRINK_WARN
local warn_rects=0
local real_rect=env.rect
env.rect=function(_,_,_,_,col) if col==9 then warn_rects=warn_rects+1 end end
for _=1,30 do env.TIC() end  -- a full blink period, the ring is lit in half of it
env.rect=real_rect
check("shrink warns about the next tiles", warn_rects>=1, "rects="..warn_rects)

-- initAudio / updateMusic need a fresh game instance: initAudio runs once per instance
local function fresh_game(poke_fn,sfx_fn)
  local e={}
  for _,n in ipairs({"cls","rect","rectb","circ","circb","line","pix","print","tri"}) do e[n]=function() end end
  e.pmem=function() return 0 end
  e.btn=function() return false end
  e.btnp=function() return false end
  e.time=function() return 42 end
  e.peek=function() return 0 end
  e.poke=poke_fn
  e.sfx=sfx_fn
  setmetatable(e,{__index=_G})
  assert(load(src,"blastic","t",e))()
  return e
end

local pokes={}
local audio_game=fresh_game(function(addr,v) pokes[addr]=v end,function() end)
audio_game.init()
-- TIC-80 1.x RAM: WAVEFORMS at 0x0FFE4, SFX at 0x100E4 (66 bytes per slot); 0x14000.. is
-- stereo volume and persistent memory, which audio must never touch.
check("initAudio writes the bomb-placed sound slot", pokes[0x100E4+66*5]~=nil)
check("initAudio writes the shield-break sound slot", pokes[0x100E4+66*7]~=nil)
check("initAudio writes the death slot", pokes[0x100E4+66]~=nil)
check("initAudio writes the waveforms", pokes[0x0FFE4]~=nil and pokes[0x0FFE4+16*3]~=nil)
local stray=false
for addr in pairs(pokes) do if addr>=0x14000 and addr<0x14404 then stray=true end end
check("faces are skin-toned: palette colour 10 is set warm",
      pokes[0x03FC0+30] and pokes[0x03FC0+30]>pokes[0x03FC0+32])
local function brown(i)
  local r,g,b=pokes[0x03FC0+i*3],pokes[0x03FC0+i*3+1],pokes[0x03FC0+i*3+2]
  return r and r>g and g>b
end
check("blocks are wood brown", brown(1) and brown(8))
check("initAudio leaves stereo volume and persistent memory alone", not stray)
-- SFX slot format: per tick byte0 = attenuation (0 loudest) | wave<<4, byte1 = chord | pitch<<4
local blip=0x100E4+66*5
check("SFX ticks after the sound are silent", pokes[blip+20] and pokes[blip+20]&15==15,
      "tick 10 byte0="..tostring(pokes[blip+20]))
local arp=0
for t=0,3 do arp=arp|((pokes[blip+t*2+1] or 0)&15) end
check("the bomb-placed blip has no arpeggio", arp==0)
local flat=true
for i=0,15 do if pokes[0x0FFE4+i]~=0 then flat=false end end
check("wave 0 is TIC-80 noise (a flat zero wave)", flat)

-- Muzyka: próbki z tools/music/instruments.py w pamięci od 0x04000; zbieramy bajty kanału PCM.
local PCM=0x14E24
local function music_game(blob)
  local mem={}
  for i=1,#blob do mem[0x04000+i-1]=blob:byte(i) end
  local stream={}
  local e=fresh_game(function(addr,v)
    if addr>=PCM and addr<PCM+128 then stream[#stream+1]=v end
  end,function() end)
  e.peek=function(addr) return mem[addr] or 0 end
  return e,stream
end

-- 8 próbek po 4 kody 7,15,0,8 z pred 0 i indeksem 88: 32767, -28669, -24574, -28298 (krok
-- spada do 87 po kodzie 0), czyli po //256: 127, -112, -96, -111
local tiny={8}
for k=1,8 do local o=33+(k-1)*5 tiny[#tiny+1]=o&255 tiny[#tiny+1]=o>>8 tiny[#tiny+1]=4 tiny[#tiny+1]=0 end
for _=1,8 do for _,v in ipairs({0,0,88,0xF7,0x80}) do tiny[#tiny+1]=v end end
local te=music_game(string.char(table.unpack(tiny)))
te.startMusic()
check("samples decode from IMA ADPCM", te.SMP.kick and table.concat(te.SMP.kick,",")=="127,-112,-96,-111",
      te.SMP.kick and table.concat(te.SMP.kick,","))

local f=io.open("music.bin","rb")
local blob=f:read("a"); f:close()
local me,stream=music_game(blob)
me.sndExplosion=function() end  -- bots' bombs would mix into the stream
me.startMusic()
local all=true
for _,name in ipairs({"bass","slap","ghost","kick","snare","hat","ohat","boom"}) do
  if not me.SMP[name] or #me.SMP[name]<100 then all=false end
end
check("music.bin holds every instrument sample", all)
for _=1,60 do me.TIC() end
local varies=false
for i=2,#stream do if stream[i]~=stream[1] then varies=true break end end
check("the tracker plays", #stream==60*128 and varies)

-- short songs: the next one starts two bars before the end and they cross-fade
me.SONG_BARS=4
me.musicSeqs={}
me.startSong(1,false)
for _=1,300 do me.TIC() end
local s1,s2=me.musicSeqs[1],me.musicSeqs[2]
check("the next song cross-fades in", #me.musicSeqs==2 and s1.n==1 and s2.n==2
      and s1.gain<1 and s2.gain>0 and math.abs(s1.gain+s2.gain-1)<0.05,
      ("seqs=%d"):format(#me.musicSeqs))
for _=1,900 do me.TIC() end
local old=false
for _,s in ipairs(me.musicSeqs) do if s.n==1 then old=true end end
check("songs follow one another instead of looping", not old and me.musicSeqs[1].n>=3)
me.musicSeqs={}
me.startSong(#me.SONGS,false)
for _=1,600 do me.TIC() end
local wrapped=false
for _,s in ipairs(me.musicSeqs) do if s.n==1 then wrapped=true end end
check("after the last song the first comes back", wrapped)

-- the music ducks to half under an explosion
local function frame_after(boom_it)
  local e,st=music_game(blob)
  e.startMusic()
  for _=1,30 do e.TIC() end
  local from=#st
  if boom_it then e.sndExplosion() end
  e.TIC()
  local out={}
  for i=from+1,#st do out[#out+1]=st[i]-128 end
  return out,e.SMP.boom
end
local plain=frame_after(false)
local mixed,bs=frame_after(true)
local ducked=#plain==128
for i=1,128 do
  local want=math.max(-128,math.min(127,(plain[i]/2+bs[i]*0.6)//1))
  if math.abs(mixed[i]-want)>1 then ducked=false end
end
check("the explosion plays at 0.6 over the music ducked to half", ducked)

-- ── TEST: campaign ────────────────────────────────────────────────────────────

io.write("\n=== campaign ===\n")
;(function()  -- own function: the main chunk is near Lua's 200-local limit

-- press Z every frame until the state is `want` (scenes and the world map wait for it)
local function skip_to(want,max)
  for _=1,max or 3000 do
    if env.state==want then return true end
    press_frame(4)
  end
  return env.state==want
end

-- the first stage matching pred(stage definition)
local function find_stage(pred)
  for n,st in ipairs(env.STAGES) do if pred(st,n) then return n end end
end

local function has_hidden(kind)
  for _,k in pairs(env.hidden) do if k==kind then return true end end
  for _,pu in ipairs(env.powerups) do if pu.kind==kind then return true end end
  return false
end

-- menu: up wraps to the last item, Z on BATTLE starts a battle
for k in pairs(_pmem) do _pmem[k]=nil end
env.state,env.titleTimer,env.menuSel="title",2,1
press_frame(0)
check("menu: up from the first item wraps to BATTLE", env.titleMenu()[env.menuSel][1]=="BATTLE", "sel="..env.menuSel)
press_frame(4)
check("menu: BATTLE starts a battle", env.state=="game" and env.mode=="pvp")

-- with a save the menu continues it or starts over; starting over clears the save
_pmem[env.SAVE_SLOT]=7
local labels={}
for _,it in ipairs(env.titleMenu()) do labels[#labels+1]=it[1] end
check("menu with a save: continue, continue 2P, new story, battle",
  table.concat(labels,"|")=="CONTINUE (STAGE 7)|CONTINUE 2P|NEW STORY|BATTLE", table.concat(labels,"|"))
env.state,env.titleTimer,env.menuSel="title",2,1
press_frame(4)
check("menu: CONTINUE resumes the saved stage", env.mode=="camp" and env.camp.stage==7)
_pmem[env.SAVE_SLOT]=7
env.mode,env.state,env.titleTimer,env.menuSel="pvp","title",2,3
press_frame(4)
check("menu: NEW STORY clears the save", env.pmem(env.SAVE_SLOT)==0 and env.state=="title")
check("menu: after NEW STORY the cursor is on STORY", env.titleMenu()[env.menuSel][1]=="STORY")
press_frame(4)
check("menu: STORY after NEW STORY opens the intro", env.state=="scene" and env.camp.stage==1)
env.mode="pvp"

-- a new story opens with the intro scene, then the world map, then stage 1
for k in pairs(_pmem) do _pmem[k]=nil end
env.startCampaign(false)
check("story opens with the intro scene", env.state=="scene" and env.mode=="camp")
check("story start saves the chapter", env.pmem(env.SAVE_SLOT)==1)
check("the intro ends on the world map", skip_to("map"))
check("the world map leads into stage 1", skip_to("game") and env.camp.stage==1)
check("stage 1 scrolls vertically on a taller map", env.W==32 and env.H==34, ("W=%d H=%d"):format(env.W,env.H))
check("chapter 1 has only Aldric", #env.players==1 and env.players[1].team==1)
check("stage 1 has its dwarves", #env.monsters==env.STAGES[1][4], "monsters="..#env.monsters)
check("stage 1 hides an exit", has_hidden("X"))

-- the camera follows Aldric along the stage's one axis, within the map
local hero=env.players[1]
hero.y=env.gpy(25); hero.r=25
env.TIC()
check("the camera follows the hero along one axis",
      env.camY>0 and env.camY<=(env.H-2)*env.TILE-128 and env.camX==0,
      ("camX=%d camY=%d"):format(env.camX,env.camY))

-- a crate hiding the exit drops it, and a later blast does not destroy it
env.monsters={}
hero=env.players[1]
local ec,er=10,5
for dc=-3,4 do for dr=-2,2 do env.map[er+dr][ec+dc]=env.T_EMPTY end end
env.map[er][ec+2]=env.T_BLOCK
env.hidden={[(ec+2)*100+er]="X"}
env.powerups={}
env.bombs={{c=ec+1,r=er,t=1,len=2}}
hero.c,hero.r,hero.x,hero.y=ec-3,er-2,env.gpx(ec-3),env.gpy(er-2)
env.TIC()
local exit_item=nil
for _,pu in ipairs(env.powerups) do if pu.kind=="X" then exit_item=pu end end
check("a destroyed crate reveals the hidden exit", exit_item and exit_item.c==ec+2)
env.bombs={{c=ec+1,r=er,t=1,len=2}}
for _=1,40 do env.TIC() end
check("blasts do not destroy quest items", has_hidden("X"))

-- stepping on the exit clears the stage; then the map shows stage 2
hero.c,hero.r,hero.x,hero.y=ec+2,er,env.gpx(ec+2),env.gpy(er)
env.TIC()
check("the exit clears the stage", env.state=="clear", "state="..env.state)
check("after the stage clear comes the world map", skip_to("map") and env.camp.stage==2)

-- monsters: a blast kills one, touching one kills the hero and costs a life (stage 1: its
-- goal is the exit, so an empty monster list does not end it)
env.startStage(1)
env.monsters={{kind="g",c=5,r=5,x=env.gpx(5),y=env.gpy(5),d={0,0}}}
env.blasts={{c=5,r=5,t=10}}
env.TIC()
check("a blast kills a monster", #env.monsters==0)
env.blasts={}
local lives=env.camp.lives
hero=env.players[1]
hero.shield,hero.invul=false,0
env.monsters={{kind="g",c=hero.c,r=hero.r,x=hero.x,y=hero.y,d={0,0}}}
env.TIC()
check("touching a monster kills the hero", not hero.alive)
check("a dead hero costs a life", env.camp.lives==lives-1 and env.state=="lost")
check("the stage restarts after a lost life", skip_to("game") and env.camp.stage==1 and env.camp.tries==1)

-- a bat walks towards the hero
hero=env.players[1]
for r=1,env.H-2 do for c=1,env.W-2 do
  if env.map[r][c]==env.T_BLOCK then env.map[r][c]=env.T_EMPTY end
end end
local bc,br=hero.c+4,hero.r
env.map[br][bc]=env.T_EMPTY
env.monsters={{kind="b",c=bc,r=br,x=env.gpx(bc),y=env.gpy(br),d={0,0}}}
local d0=math.abs(bc-hero.c)+math.abs(br-hero.r)
for _=1,20 do env.TIC() end
local bat=env.monsters[1]
check("a bat chases the hero", bat and math.abs(bat.c-hero.c)+math.abs(bat.r-hero.r)<d0)

-- goals: keys, all enemies, surviving the walls
env.startStage(find_stage(function(st) return st[2]=="keys" end))
for _=1,3 do
  local h=env.players[1]
  env.powerups={{c=h.c,r=h.r,kind="K"}}
  env.TIC()
end
check("three keys clear a keys stage", env.state=="clear", "keys="..env.camp.keys)
env.startStage(find_stage(function(st) return st[2]=="enemies" end))
env.monsters={}
env.TIC()
check("no monsters left clears an enemies stage", env.state=="clear")
env.startStage(find_stage(function(st) return st[2]=="survive" end))
env.monsters={}
env.zoneSteps=env.SURVIVE_STEPS-1
env.TIC()
check("a survive stage goes on until the zone has stepped in enough", env.state=="game")
env.zoneSteps=env.SURVIVE_STEPS
env.TIC()
check("surviving the zone's steps clears a survive stage", env.state=="clear")

-- chapter 2+: Elena fights along, a bot ally unless Story 2P
local ch2=find_stage(function(st) return st[1]==2 and not st[7] end)
env.camp.coop=false
env.startStage(ch2)
local elena=env.players[2]
check("Elena joins from chapter 2 as a bot ally", elena and elena.team==1 and not elena.human)
env.camp.coop=true
env.startStage(ch2)
check("in Story 2P Elena is player 2", env.players[2].human==true and env.players[2].id==2)
env.camp.coop=false

-- teams: the ally hunts monsters and skeletons, never Aldric; skeletons hunt the heroes
env.startStage(find_stage(function(st) return st[6]>0 end))
local al,el,sk=env.players[1],env.players[2],env.players[3]
env.monsters={{kind="g",c=al.c+3,r=al.r,x=0,y=0,d={0,0}}}
check("Elena does not target Aldric", not env.foeAt(el,al.c,al.r))
check("Elena targets monsters", env.foeAt(el,al.c+3,al.r))
check("skeletons target the heroes", sk and sk.team==2 and env.foeAt(sk,al.c,al.r))
env.monsters={}
env.powerups={{c=sk.c,r=sk.r,kind="K"}}
env.camp.keys=0
env.TIC()
check("skeletons leave quest items", env.camp.keys==0 and #env.powerups>=1)

-- bosses: blasts hurt them with a pause between hits; the dragon's egg wins too
env.startStage(5)
local b=env.boss
check("stage 5 is the first Utopek fight", b and b.kind=="utopek" and b.hp==env.BOSS_HP.utopek)
env.blasts={{c=b.c,r=b.r,t=30}}
env.TIC()
check("a blast hurts the boss once", b.hp==env.BOSS_HP.utopek-1 and b.inv>0)
env.TIC()
check("the boss is briefly invulnerable", b.hp==env.BOSS_HP.utopek-1)
b.hp,b.inv=1,0
env.blasts={{c=b.c,r=b.r,t=30}}
env.TIC()
check("defeating the boss clears the stage", env.state=="clear")
env.startStage(find_stage(function(st) return st[7]=="dragon" end))
check("the dragon's egg is hidden", has_hidden("E"))
local h=env.players[1]
env.powerups={{c=h.c,r=h.r,kind="E"}}
env.TIC()
check("returning the egg befriends the dragon", env.camp.friend and env.state=="clear")
env.camp.friend=false

-- running out of lives ends the story; it continues from the saved chapter
env.startStage(ch2)
env.camp.lives=1
for _,p in ipairs(env.players) do p.alive=false end
env.TIC()
check("losing the last life is game over", env.state=="gameover")
check("game over returns to the title", skip_to("title"))
_pmem[env.SAVE_SLOT]=30
env.startCampaign(false)
check("the story continues from the saved stage", env.camp.stage==30 and env.state=="map")
_pmem[env.SAVE_SLOT]=26
env.startCampaign(false)
check("a saved chapter start replays its scene", env.camp.stage==26 and env.state=="scene")

-- 100 stages in 4 chapters; every 5th a boss, the chapter's own at its end, Morgath last
local bosses,last_ok=0,true
for n,st in ipairs(env.STAGES) do
  if (n%5==0)~=(st[2]=="boss") then last_ok=false end
  if st[7] then bosses=bosses+1 end
end
check("100 stages, a boss on every 5th", #env.STAGES==100 and bosses==20 and last_ok)
check("chapter bosses end their chapters", env.STAGES[25][7]=="utopek" and env.STAGES[50][7]=="jaga"
      and env.STAGES[75][7]=="dragon" and env.STAGES[100][7]=="devil")
local m1,m99=env.STAGES[1][4]+env.STAGES[1][5]+env.STAGES[1][6],env.STAGES[99][4]+env.STAGES[99][5]+env.STAGES[99][6]
check("later stages have more monsters", m99>m1, ("%d -> %d"):format(m1,m99))

-- a hero bot digs towards the sparkling crate that hides a quest item
env.startStage(1)
local digger=env.players[1]
for r=1,env.H-2 do for c=1,env.W-2 do env.map[r][c]=env.T_EMPTY end end
for r=1,env.H-2 do env.map[r][8]=env.T_BLOCK end
env.hidden={[8*100+20]="X"}
env.monsters,env.bombs,env.powerups={},{},{}
local qd=env.botQuestDir(digger,{})
check("a hero bot heads for the sparkling crate", qd and qd[2]==1,
      qd and ("dir %d,%d"):format(qd[1],qd[2]) or "nil")

-- the closing zone crushes monsters too
env.startStage(1)
env.monsters={{kind="g",c=1,r=1,x=env.gpx(1),y=env.gpy(1),d={0,0}},{kind="b",c=5,r=5,x=0,y=0,d={0,0}}}
env.roundFrames=env.shrinkAt-1
env.shrinkAt=env.roundFrames+1
env.updateShrink()
check("the closing zone crushes monsters on it", #env.monsters==1 and env.monsters[1].c==5)

-- friendly fire: in the campaign a fellow hero's blast spares you, your own does not
env.startStage(find_stage(function(st) return st[1]==2 and st[2]=="exit" end))
env.monsters={}
local ha,he=env.players[1],env.players[2]
ha.shield,ha.invul=false,0
env.blasts={{c=ha.c,r=ha.r,t=10,owner=he}}
env.TIC()
check("a fellow hero's blast spares Aldric", ha.alive)
env.blasts={{c=ha.c,r=ha.r,t=10,owner=ha}}
env.TIC()
check("his own blast still kills him", not ha.alive)

-- bosses are not hurt by their own fire
env.startStage(find_stage(function(st) return st[7]=="jaga" end))
local wb=env.boss
env.blasts={{c=wb.c,r=wb.r,t=20,owner=env.BOSS_FIRE}}
env.TIC()
check("a boss's own blast does not hurt it", wb.hp==wb.max)

-- a hero bot keeps out of the row the dragon is about to burn
env.startStage(find_stage(function(st) return st[7]=="dragon" end))
local dk=env.players[1]
for r=1,env.H-2 do for c=1,env.W-2 do if env.map[r][c]~=env.T_WALL then env.map[r][c]=env.T_EMPTY end end end
env.monsters,env.bombs,env.powerups,env.hidden={},{},{},{}
env.boss.warn={row=true,c=dk.c,r=dk.r,t=60}
dk.human=false
for _=1,50 do env.TIC() end
check("a hero bot leaves the row the dragon warns about", dk.alive and dk.r~=env.boss.warn.r or not env.boss.warn,
      ("hero row %d"):format(dk.r))

-- a hero bot keeps away from monsters
env.camp.coop=false
env.startStage(ch2)
local ally=env.players[2]
for r=1,env.H-2 do for c=1,env.W-2 do if env.map[r][c]~=env.T_WALL then env.map[r][c]=env.T_EMPTY end end end
env.monsters={{kind="g",c=ally.c+1,r=ally.r,x=0,y=0,d={0,0}}}
env.bombs,env.powerups={},{}
for _=1,16 do env.TIC() end
local mon=env.monsters[1]
check("a hero bot steps away from a monster",
      ally.alive and math.abs(ally.c-mon.c)+math.abs(ally.r-mon.r)>=2, ("ally %d,%d"):format(ally.c,ally.r))

-- the last boss leads into the ending, which clears the save
env.startStage(#env.STAGES)
env.boss.hp=0
env.TIC()
check("beating Morgath clears the last stage", env.state=="clear")
check("the ending scene follows", skip_to("scene"))
check("the ending returns to the title", skip_to("title") and env.pmem(env.SAVE_SLOT)==0)

-- scenes animate: the dialogue types out letter by letter
env.playScene("sleza",function() env.state="title" end)
local shown={}
do
  local sp=env.print
  env.print=function(t,x,y) if y==env.SUB_Y then shown[#shown+1]=t end return 0 end
  for _=1,600 do
    if #shown>0 then break end
    env.TIC()
  end
  for _=1,3 do env.TIC() end  -- a letter every second frame
  env.print=sp
end
check("scene dialogue types out", #shown==4 and #shown[4]>#shown[1])
skip_to("title")
env.mode="pvp"

-- painted backdrops: scenes.bin in MAP RAM, unpacked into their own buffer, copied under the
-- letterbox; the sky colour follows the scanline
do
  local f=io.open("scenes.bin","rb")
  local blob=f:read("a") f:close()
  local mem={}
  for i=1,#blob do mem[0x08000+i-1]=blob:byte(i) end
  local outside=0
  local g=fresh_game(function(a,v) mem[a]=v end,function() end)
  g.peek=function(a) return mem[a] or 0 end
  g.memset=function(d,v,n)
    if d<0x11164 or d+n>0x11164+11520 then outside=outside+1 end
    for i=0,n-1 do mem[d+i]=v end
  end
  g.memcpy=function(d,src,n)
    if d>=0x11164 and d+n>0x11164+11520 then outside=outside+1 end
    for i=0,n-1 do mem[d+i]=mem[src+i] end
  end
  local done=false
  local seen={}
  for _,name in ipairs({"wroclaw","sleza","krakow","cellars","ending"}) do
    done=false
    g.playScene(name,function() done=true end)
    g.btnp=function(b) return b==4 end
    for _=1,4000 do
      if done then break end
      g.TIC()
      if g.state=="scene" and mem[20*120] then seen[mem[20*120]]=true end
    end
  end
  check("every scene plays to its end with backdrops", done)
  check("backdrops unpack inside their buffer", outside==0, "outside="..outside)
  g.btnp=function() return false end
  g.playScene("wroclaw",function() end)
  for _=1,30 do g.TIC() end
  check("the market backdrop opens with sky at the top left", mem[20*120]==0xBB, tostring(mem[20*120]))
  local function sky(row) g.BDR(row) return ("%d,%d"):format(mem[0x03FC0+33] or 0,mem[0x03FC0+34] or 0) end
  check("the sky colour changes down the screen", sky(4+20)~=sky(4+110), sky(4+20).." / "..sky(4+110))
  check("the sky starts from the backdrop's top colour",
    sky(4+20)==blob:byte(1+11+1)..","..blob:byte(1+11+2), sky(4+20))
end

end)()

-- ── Summary ───────────────────────────────────────────────────────────────────

io.write(string.format("\n══════════════════════════════\n"))
io.write(string.format("  %d passed, %d failed\n", pass, fail))
io.write(string.format("══════════════════════════════\n"))
if fail > 0 then os.exit(1) end
