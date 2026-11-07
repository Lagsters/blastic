-- Records the game intro, two seconds of the title screen, every story scene and the map
-- between stages, frame by frame, for tools/film.py to turn into a video: lua tools/film.lua <out-dir> [every=2]
-- Writes frames.bin (per kept frame: 16320 B of 4-bit pixels, 48 B palette, 136x3 B colour 11
-- per row as BDR left it), texts.txt (frame, x, y, colour, scale, text) for the print calls and
-- audio.raw, the PCM channel of every frame (unsigned 8-bit, 7680 Hz; sfx() is not heard).
local out=arg[1] or "."
local every=tonumber(arg[2]) or 2
local mem={}
local function blob(path,at)
  local f=assert(io.open(path,"rb"))
  local s=f:read("a") f:close()
  for i=1,#s do mem[at+i-1]=s:byte(i) end
end
blob("music.bin",0x04000)
do  -- scenes.bin: pieces of RAM, u24 address, u16 length, bytes
  local f=assert(io.open("scenes.bin","rb"))
  local s=f:read("a") f:close()
  local i=1
  while i<=#s do
    local at,n=s:byte(i)|s:byte(i+1)<<8|s:byte(i+2)<<16,s:byte(i+3)|s:byte(i+4)<<8
    for k=1,n do mem[at+k-1]=s:byte(i+4+k) end
    i=i+5+n
  end
end
local SW="1a1c2c5d275db13e53ef7d57ffcd75a7f07038b764257179"..
  "29366f3b5dc941a6f673eff7f4f4f494b0c2566c86333c57"
for i=0,47 do mem[0x03FC0+i]=tonumber(SW:sub(i*2+1,i*2+2),16) end

local function px(x,y,c)
  x,y=math.floor(x),math.floor(y)
  if x<0 or x>239 or y<0 or y>135 then return end
  local a=y*120+x//2
  local b=mem[a] or 0
  if x%2==0 then mem[a]=(b&0xF0)|c else mem[a]=(b&0x0F)|(c<<4) end
end
local texts,frame={},0
local env={}
env.cls=function(c) c=c or 0 for a=0,16319 do mem[a]=c|(c<<4) end end
env.pix=px
env.rect=function(x,y,w,h,c)
  x,y,w,h=math.floor(x),math.floor(y),math.floor(w),math.floor(h)
  for j=0,h-1 do for i=0,w-1 do px(x+i,y+j,c) end end
end
env.rectb=function(x,y,w,h,c)
  for i=0,w-1 do px(x+i,y,c) px(x+i,y+h-1,c) end
  for j=0,h-1 do px(x,y+j,c) px(x+w-1,y+j,c) end
end
env.circ=function(x,y,r,c)
  x,y,r=math.floor(x),math.floor(y),math.floor(r)
  for j=-r,r do for i=-r,r do if i*i+j*j<=r*r+r then px(x+i,y+j,c) end end end
end
env.circb=env.circ
env.line=function(x0,y0,x1,y1,c)
  local n=math.max(math.abs(x1-x0),math.abs(y1-y0),1)
  for k=0,n do px(x0+(x1-x0)*k/n,y0+(y1-y0)*k/n,c) end
end
env.tri=function(x1,y1,x2,y2,x3,y3,c)
  local function e(ax,ay,bx,by,x,y) return (bx-ax)*(y-ay)-(by-ay)*(x-ax) end
  for y=math.floor(math.min(y1,y2,y3)),math.ceil(math.max(y1,y2,y3)) do
    for x=math.floor(math.min(x1,x2,x3)),math.ceil(math.max(x1,x2,x3)) do
      local a,b,d=e(x1,y1,x2,y2,x+.5,y+.5),e(x2,y2,x3,y3,x+.5,y+.5),e(x3,y3,x1,y1,x+.5,y+.5)
      if (a>=0 and b>=0 and d>=0) or (a<=0 and b<=0 and d<=0) then px(x,y,c) end
    end
  end
end
env.print=function(t,x,y,c,fixed,scale,small)
  t,scale=tostring(t),scale or 1
  if y>-10 then texts[#texts+1]=("%d\t%d\t%d\t%d\t%d\t%s"):format(frame,x,y,c or 15,scale,t) end
  return #t*(small and 4 or 6)*scale
end
env.peek=function(a) return mem[a] or 0 end
env.poke=function(a,v) mem[a]=math.floor(v) end
env.memcpy=function(d,s,n) for i=0,n-1 do mem[d+i]=mem[s+i] end end
env.memset=function(d,v,n) for i=0,n-1 do mem[d+i]=v end end
env.btn=function() return false end
env.btnp=function() return false end
env.sfx=function() end
env.pmem=function() return 0 end
env.time=function() return 42 end
setmetatable(env,{__index=_G})
local f=assert(io.open("blastic.lua")) local src=f:read("a") f:close()
assert(load(src,"blastic","t",env))()

local fb=assert(io.open(out.."/frames.bin","wb"))
local ab=assert(io.open(out.."/audio.raw","wb"))
local PCM=0x14E24
local kept=0
local function tick()
  frame=frame+1
  texts={}
  for k=0,127 do mem[PCM+k]=128 end
  env.TIC()
  local pcm={}
  for k=0,127 do pcm[k+1]=string.char(mem[PCM+k]) end
  ab:write(table.concat(pcm))
  if frame%every~=0 then return end
  local row={}
  for y=0,135 do
    if env.BDR then env.BDR(y+4) end
    row[#row+1]=string.char(mem[0x03FC0+33] or 0,mem[0x03FC0+34] or 0,mem[0x03FC0+35] or 0)
  end
  local px={}
  for a=0,16319 do px[#px+1]=string.char(mem[a] or 0) end
  local pal={}
  for i=0,47 do pal[#pal+1]=string.char(mem[0x03FC0+i] or 0) end
  fb:write(table.concat(px),table.concat(pal),table.concat(row))
  kept=kept+1
  local tf=assert(io.open(out.."/texts.txt",kept==1 and "w" or "a"))
  for _,t in ipairs(texts) do tf:write(t:gsub("^%d+",tostring(kept)),"\n") end
  tf:close()
end

while env.state=="intro" do tick() end
for _=1,120 do tick() end  -- the title screen
for _,name in ipairs{"wroclaw","sleza","krakow","cellars","ending"} do
  local done=false
  env.playScene(name,function() done=true end)
  while not done do tick() end
end
env.showMap(28)  -- the map between stages, in chapter 2
for _=1,150 do tick() end
fb:close()
ab:close()
print(("%d frames"):format(kept))
