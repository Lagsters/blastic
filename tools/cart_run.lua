-- Smoke test of a built cart: loads its chunks into RAM the way TIC-80 does, runs its code with
-- the drawing API mocked, plays the intro, every story scene and a battle.
-- Usage: lua tools/cart_run.lua <cart.tic>   (exit code 1 on failure)
local RAM_OF={[1]=0x04000,[2]=0x06000,[4]=0x08000,[9]=0x100E4,[15]=0x11164}
local f=assert(io.open(arg[1],"rb"))
local cart=f:read("a") f:close()
local mem,code,banks={},nil,{}
local p=1
while p<=#cart do
  local b0,b1,b2=cart:byte(p,p+2)
  local kind,bank,size=b0&0x1f,b0>>5,b1|(b2<<8)
  local body=cart:sub(p+4,p+3+size)
  if kind==5 then code=body
  elseif RAM_OF[kind] then
    banks[bank]=banks[bank] or {}
    banks[bank][kind]=body
    if bank==0 then for i=1,#body do mem[RAM_OF[kind]+i-1]=body:byte(i) end end
  end
  p=p+4+size
end
local MAP_SIZE=32640
assert(code,"no code chunk")

local env={}
for _,n in ipairs{"cls","rect","rectb","circ","circb","line","pix","tri","sfx"} do env[n]=function() end end
env.print=function(t) return #tostring(t)*4 end
env.peek=function(a) return mem[a] or 0 end
env.poke=function(a,v) mem[a]=v end
env.memcpy=function(d,s,n) for i=0,n-1 do mem[d+i]=mem[s+i] end end
env.memset=function(d,v,n) for i=0,n-1 do mem[d+i]=v end end
env.sync=function(mask,bank)  -- as TIC-80 does: the whole MAP of that cart bank, zeros where none
  if mask&4==0 then return end
  local body=banks[bank] and banks[bank][4] or ""
  for i=0,MAP_SIZE-1 do mem[0x08000+i]=i<#body and body:byte(i+1) or 0 end
end
env.btn=function() return false end
local z=false
env.btnp=function(b) return b==4 and z end
env.pmem=function() return 0 end
env.time=function() return 42 end
env.load=function(s,n,m,e) return load(s,n,m,e or env) end  -- TIC-80 runs the cart in one global table
-- only the libraries TIC-80 gives a cart: no io, os, utf8, require
local TIC_LUA={}
for _,n in ipairs{"assert","error","ipairs","pairs","next","pcall","select","tonumber","tostring",
  "type","setmetatable","getmetatable","rawget","rawset","rawequal","rawlen","unpack","xpcall",
  "math","string","table","coroutine"} do TIC_LUA[n]=_G[n] end
setmetatable(env,{__index=TIC_LUA})
assert(load(code,"cart","t",env))()

local function run(n,cond) for _=1,n do if cond and cond() then return true end env.TIC() end return not cond end
assert(run(1000,function() return env.state=="title" end),"the intro never reaches the title")
for _,lang in ipairs{"en","pl"} do
  env.LANG=lang
  for _,name in ipairs{"wroclaw","sleza","krakow","cellars","ending"} do
    local done=false
    env.playScene(name,function() done=true end)
    z=true
    assert(run(5000,function() return done end),"scene "..name.." never ends ("..lang..")")
    z=false
  end
end
env.state="title" env.titleTimer=2 env.menuSel=1
env.init()
assert(run(600),"battle")
print("cart runs: intro, 5 scenes in English and Polish, battle")
