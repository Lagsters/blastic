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

-- ── TEST: power-ups ───────────────────────────────────────────────────────────

io.write("\n=== power-ups ===\n")

-- P1 walks one cell right onto a power-up at (2,1); bots are removed
local function walk_onto_right(kind, setup)
  new_game()
  env.players[3].alive=false; env.players[4].alive=false
  env.map[1][2]=env.T_EMPTY
  env.powerups={{c=2,r=1,kind=kind}}
  if setup then setup(env.players[1]) end
  for _=1,6 do _held[3]=true; env.TIC() end
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

-- ── Summary ───────────────────────────────────────────────────────────────────

io.write(string.format("\n══════════════════════════════\n"))
io.write(string.format("  %d passed, %d failed\n", pass, fail))
io.write(string.format("══════════════════════════════\n"))
if fail > 0 then os.exit(1) end
