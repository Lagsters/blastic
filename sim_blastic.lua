-- Headless simulator: four bots, TIC-80 API mocked. Usage: lua sim_blastic.lua [rounds] [seed]
local rounds=tonumber(arg and arg[1]) or 200
local seed=tonumber(arg and arg[2]) or 1
local MAX_FRAMES=20000

local env={}
for _,n in ipairs{"cls","rect","rectb","circ","line","pix","print","poke","sfx"} do env[n]=function() end end
env.btn=function() return false end
env.btnp=function() return false end
env.peek=function() return 0 end
local t=0
env.time=function() t=t+1; return seed*1000+t end
setmetatable(env,{__index=_G})

local f=assert(io.open("blastic.lua")); local src=f:read("*a"); f:close()
assert(load(src,"blastic","t",env))()
env.humans={false,false,false,false}

local errors,wins,draws,timeouts,frames={}, {0,0,0,0},0,0,0
local function fail(r,f,msg) errors[#errors+1]=string.format("round %d frame %d: %s",r,f,msg) end

-- invariants checked every frame
local function check(r,fr)
  for _,p in ipairs(env.players) do
    if p.alive then
      local tl=env.mget(p.c,p.r)
      if tl==1 or tl==2 then fail(r,fr,"P"..p.id.." inside wall/block at "..p.c..","..p.r) end
      if p.bombs<0 or p.bombs>p.stats.bombs then fail(r,fr,"P"..p.id.." bomb count "..p.bombs) end
    end
  end
  for _,b in ipairs(env.bombs) do
    if env.mget(b.c,b.r)~=0 then fail(r,fr,"bomb on non-empty tile") end
  end
end

for r=1,rounds do
  env.init()
  local fr=0
  while env.state=="game" and fr<MAX_FRAMES do
    fr=fr+1
    local ok,err=pcall(env.TIC)
    if not ok then fail(r,fr,"crash: "..tostring(err)); break end
    check(r,fr)
    if #errors>20 then break end
  end
  frames=frames+fr
  if env.state=="game" then timeouts=timeouts+1; fail(r,fr,"round did not end") 
  elseif env.winner then wins[env.winner.id]=wins[env.winner.id]+1 else draws=draws+1 end
  if #errors>20 then break end
end

print(string.format("rounds=%d avgFrames=%d wins P1..P4=%d/%d/%d/%d draws=%d timeouts=%d errors=%d",
  rounds,frames//math.max(rounds,1),wins[1],wins[2],wins[3],wins[4],draws,timeouts,#errors))
for i=1,math.min(#errors,10) do print("  "..errors[i]) end
os.exit(#errors==0 and 0 or 1)
