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
env.line  = function() end
env.pix   = function() end
env.print = function() end  -- TIC-80 screen draw, shadows Lua's print inside game
env.time  = function() return 42 end  -- fixed seed → deterministic map & bot RNG
env.poke  = function() end
env.peek  = function() return 0 end
env.sfx   = function() end
setmetatable(env, {__index = _G})

-- ── Load game ────────────────────────────────────────────────────────────────

local f = io.open("blastic.lua")
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

io.write("\n=== title screen ===\n")
check("initial state is title", env.state=="title", "got: "..tostring(env.state))
run_frames(5)
check("stays title first 5 frames", env.state=="title")
check("titleTimer increments", env.titleTimer==5, "got: "..tostring(env.titleTimer))

-- ── TEST: title auto-start ────────────────────────────────────────────────────

io.write("\n=== auto-start ===\n")
run_frames(296)  -- total titleTimer becomes 301
check("auto-starts at titleTimer>300", env.state=="game", "state="..tostring(env.state))

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
local real_sfx=env.sfx
env.sfx=function(id) if id==0 then explosions=explosions+1 end end
local ca=add_bomb(env.players[1],5,5,1)
add_bomb(env.players[2],6,5,env.BOMB_TIMER)   -- covered by A (BLAST_LEN reach)
add_bomb(env.players[1],8,5,env.BOMB_TIMER)   -- covered by B only
run_frames(1)
env.sfx=real_sfx
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
env.map[3][4]=env.T_EMPTY
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
check("both side columns close at once", col_open(1)==0 and col_open(env.W-2)==0 and col_open(2)>0,
      ("col1=%d col2=%d"):format(col_open(1), col_open(2)))
check("top and bottom rows stay while the arena is wider than tall",
      row_open(1)>0 and row_open(env.H-2)>0)

close_steps(6)
check("sides keep closing until the arena is nearly square",
      col_open(6)==0 and col_open(7)>0 and row_open(1)>0)
close_steps(7)
check("then the whole outline closes evenly", row_open(1)==0 and row_open(env.H-2)==0
      and col_open(7)==0 and col_open(8)>0 and row_open(2)>0)

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

new_game()
for _=1,env.SHRINK_DELAY+env.SHRINK_CYCLE*(env.W//2+2) do env.updateShrink() end
check("shrink eventually walls every tile", open_count()==0, "open="..open_count())

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

for _,st in ipairs({"title","game","over"}) do
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
  env.pix=function(x,y,col) seen[#seen+1]=x..","..y..","..col end
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
env.roundFrames=env.shrinkAt-env.SHRINK_WARN
local warn_rects=0
local real_rect=env.rect
env.rect=function(_,_,_,_,col) if col==9 then warn_rects=warn_rects+1 end end
env.TIC()
env.rect=real_rect
check("shrink warns about the next tiles", warn_rects>=1, "rects="..warn_rects)

-- initAudio / updateMusic need a fresh game instance: initAudio runs once per instance
local function fresh_game(poke_fn,sfx_fn)
  local e={}
  for _,n in ipairs({"cls","rect","rectb","circ","line","pix","print"}) do e[n]=function() end end
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
check("initAudio writes the bomb-placed sound slot", pokes[0x14100+66*5]~=nil)
check("initAudio writes the shield-break sound slot", pokes[0x14100+66*7]~=nil)

-- Muzyka: blob z wav2tic.py w pamięci, jak go układa make_tic.py; zbieramy bajty kanału PCM.
local PCM=0x14E24
local function music_stream(blob,frames)
  local mem={}
  for i=1,#blob do
    local off=i-1
    local addr=off<0xBF80 and 0x04000+off or 0x11164+off-0xBF80
    mem[addr]=blob:byte(i)
  end
  local stream={}
  local e=fresh_game(function(addr,v)
    if addr>=PCM and addr<PCM+128 then stream[#stream+1]=v end
  end,function() end)
  e.peek=function(addr) return mem[addr] or 0 end
  for _=1,frames do e.TIC() end
  return stream
end

-- len 4, 2 plastry, kolejność {1,0,1}; plaster 0: pred 0, indeks 88, kody 7,15,0,8;
-- plaster 1: pred 2560, indeks 0, kody 0 (krok 7>>3=0, stoi na 2560 -> 138).
local tiny=string.char(4,0, 2,3, 1,0,1, 0,0,88, 0,10,0, 0xF7,0x80, 0,0)
local s=music_stream(tiny,2)
local cycle={138,138,138,138, 255,16,32,17, 138,138,138,138}
local same=#s==128
for i=1,#s do same=same and s[i]==cycle[(i-1)%12+1] end
check("music decodes IMA ADPCM slices in order and loops", same,
      "got "..table.concat(s,",",1,math.min(#s,16)))

local f=io.open("music.bin","rb")
local blob=f:read("a"); f:close()
local len=blob:byte(1)|blob:byte(2)<<8
local loop=len*blob:byte(4)
local frames=(loop*2)//128+2
local st=music_stream(blob,frames)
local repeats,varies=#st>=loop*2,false
for i=1,loop do
  if st[i]~=st[i+loop] then repeats=false break end
  if st[i]~=st[1] then varies=true end
end
check("music.bin uses the patterns region", #blob>0xBF80, "size "..#blob)
check("music.bin loop repeats byte for byte", repeats and varies)

-- ── Summary ───────────────────────────────────────────────────────────────────

io.write(string.format("\n══════════════════════════════\n"))
io.write(string.format("  %d passed, %d failed\n", pass, fail))
io.write(string.format("══════════════════════════════\n"))
if fail > 0 then os.exit(1) end
