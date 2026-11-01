-- Renders frames of blastic.lua headless: lua tools/shot.lua <out-dir>
-- Writes title.pgm and game.pgm (P2 graymap holding palette indices) plus *.txt with print() calls.
local out=arg and arg[1] or "."
local FW,FH=240,136
local fb,texts={},{}
local function clear(c) for i=0,FW*FH-1 do fb[i]=c end texts={} end
local function px(x,y,c)
  x,y=math.floor(x),math.floor(y)
  if x>=0 and x<FW and y>=0 and y<FH then fb[y*FW+x]=c end
end
local env={}
env.cls=function(c) clear(c or 0) end
env.pix=px
env.rect=function(x,y,w,h,c) for j=0,h-1 do for i=0,w-1 do px(x+i,y+j,c) end end end
env.rectb=function(x,y,w,h,c)
  for i=0,w-1 do px(x+i,y,c); px(x+i,y+h-1,c) end
  for j=0,h-1 do px(x,y+j,c); px(x+w-1,y+j,c) end
end
env.circ=function(x,y,r,c)
  for j=-r,r do for i=-r,r do if i*i+j*j<=r*r then px(x+i,y+j,c) end end end
end
env.line=function(x0,y0,x1,y1,c)
  local dx,dy=math.abs(x1-x0),-math.abs(y1-y0)
  local sx,sy=x0<x1 and 1 or -1,y0<y1 and 1 or -1
  local e=dx+dy
  while true do
    px(x0,y0,c)
    if x0==x1 and y0==y1 then break end
    local e2=2*e
    if e2>=dy then e=e+dy; x0=x0+sx end
    if e2<=dx then e=e+dx; y0=y0+sy end
  end
end
env.print=function(t,x,y,c,fixed,scale,small)
  scale=scale or 1
  local w=#tostring(t)*(small and 4 or 6)*scale
  texts[#texts+1]={tostring(t),x,y,c or 15,scale}
  return w
end
env.btn=function() return false end
env.btnp=function() return false end
env.poke=function() end
env.peek=function() return 0 end
env.sfx=function() end
local tm=0
env.time=function() tm=tm+1; return 4242+tm end
setmetatable(env,{__index=_G})

local f=assert(io.open("blastic.lua")); local src=f:read("*a"); f:close()
assert(load(src,"blastic","t",env))()

local function dump(name)
  local o=assert(io.open(out.."/"..name..".pgm","w"))
  o:write(("P2\n%d %d\n15\n"):format(FW,FH))
  for y=0,FH-1 do
    local row={}
    for x=0,FW-1 do row[#row+1]=fb[y*FW+x] or 0 end
    o:write(table.concat(row," "),"\n")
  end
  o:close()
  local t=assert(io.open(out.."/"..name..".txt","w"))
  for _,e in ipairs(texts) do t:write(("%s\t%d\t%d\t%d\t%d\n"):format(e[1],e[2],e[3],e[4],e[5])) end
  t:close()
end

for _=1,40 do env.TIC() end
dump("title")

env.init()
env.humans={false,false,false,false}
local picked=false
for _=1,2400 do
  env.TIC()
  local alive=0
  for _,p in ipairs(env.players) do if p.alive then alive=alive+1 end end
  local fresh=0
  for _,b in ipairs(env.blasts) do if b.t<=env.BLAST_TIME-6 and b.t>=env.BLAST_TIME-9 then fresh=fresh+1 end end
  if alive>=3 and fresh>=7 and #env.bombs>=1 and #env.powerups>=1 then picked=true; break end
  if env.state~="game" then env.init(); env.humans={false,false,false,false} end
end
assert(picked,"no interesting frame found")
dump("game")
