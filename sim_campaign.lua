-- Campaign simulator: bots play the heroes through stages and report how often each is
-- cleared, how long it takes and why tries fail.
-- Usage: lua sim_campaign.lua [first=1] [last=100] [tries=3] [frame cap=7200]

local first=tonumber(arg[1]) or 1
local last=tonumber(arg[2]) or 100
local tries=tonumber(arg[3]) or 3
local cap=tonumber(arg[4]) or 7200

local env={}
for _,n in ipairs{"cls","rect","rectb","circ","circb","line","pix","print","poke","sfx","tri"} do
  env[n]=function() return 0 end
end
env.btn=function() return false end
env.btnp=function() return false end
env.time=function() return 42 end
env.peek=function() return 0 end
env.pmem=function() return 0 end
setmetatable(env,{__index=_G})
assert(load(io.open("blastic.lua"):read("a"),"blastic","t",env))()

env.startCampaign(false)
local total,cleared_stages=0,0
causes={}
print("stage  goal     clears  avg_s  dead  timeout  deaths")
for n=first,last do
  local clears,frames,dead,timeout=0,0,0,0
  causes={}
  for t=1,tries do
    env.camp.tries,env.camp.lives,env.camp.friend=t,99,false
    env.startStage(n)
    for _,p in ipairs(env.players) do p.human=false end
    local f=0
    while env.state=="game" and f<cap do
      local alive={}
      for i,p in ipairs(env.players) do alive[i]=p.alive end
      local ok,err=pcall(env.TIC)
      if not ok then print(("stage %d crash: %s"):format(n,err)) env.state="crash" end
      for i,p in ipairs(env.players) do
        if alive[i] and not p.alive and p.team==1 then
          local cause="blast"
          if env.mget(p.c,p.r)==env.T_WALL then cause="zone" end
          for _,m in ipairs(env.monsters) do if m.c==p.c and m.r==p.r then cause="monster" end end
          local b=env.boss
          if b and p.c>=b.c and p.c<=b.c+1 and p.r>=b.r and p.r<=b.r+1 then cause="boss" end
          causes[cause]=(causes[cause] or 0)+1
        end
      end
      f=f+1
    end
    if env.state=="clear" then clears,frames=clears+1,frames+f
    elseif env.state=="game" then timeout=timeout+1
    else dead=dead+1 end
  end
  total=total+clears
  if clears>0 then cleared_stages=cleared_stages+1 end
  local st=env.STAGES[n]
  local why={}
  for k,v in pairs(causes) do why[#why+1]=k.."="..v end
  table.sort(why)
  print(("%5d  %-7s  %d/%d    %5.1f  %4d  %7d  %s"):format(n,st[7] or st[2],clears,tries,
    clears>0 and frames/clears/60 or 0,dead,timeout,table.concat(why," ")))
end
print(("cleared %d/%d stages at least once, %d/%d tries"):format(cleared_stages,last-first+1,
  total,(last-first+1)*tries))
