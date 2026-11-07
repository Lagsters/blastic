-- title:  BlasTIC
-- author: Melancholy
-- desc:   4-player arena blast game (P1+P2 human, P3+P4 bots)
-- script: lua
-- input:  gamepad

-- The outer wall ring lies just off screen (left, right, bottom) and under the HUD (top):
-- the 30x16 interior fills the 240x136 screen.
W,H=32,18
TILE=8
MAX_BOMBS=1
BOMB_CAP=5
BOMB_TIMER=120
BLAST_LEN=2
LEN_CAP=6
BLAST_TIME=30
DEATH_TIME=20
SPEED=1
MOVE_PERIOD=2
POWERUP_CHANCE=0.25
POWERUP_KINDS={"B","R","S"}
SHIELD_INVUL=60
MATCH_WINS=3
MATCH_TIME=210

T_EMPTY,T_WALL,T_BLOCK=0,1,2

-- the arena and its four start corners; the campaign uses wider or taller ones
function setArena(w,h)
  W,H=w,h
  STARTS={{1,1},{W-2,1},{1,H-2},{W-2,H-2}}
end
setArena(W,H)
blockDensity=0.4
local COLORS={12,5,9,2}  -- white, green, blue, red

local B_UP,B_DOWN,B_LEFT,B_RIGHT,B_BOMB=0,1,2,3,4

humans={true,true,false,false}
map,bombs,blasts,players,powerups={},{},{},{},{}
frame=0
state="intro"
winner=nil
score={0,0,0,0}
restartTimer=0
titleTimer=0

-- ── helpers ──────────────────────────────────────────────────────────────────

function mget(c,r) return map[r] and map[r][c] or T_WALL end
local function mset(c,r,v) if map[r] then map[r][c]=v end end
function gpx(c) return (c-1)*TILE end
function gpy(r) return r*TILE end
local function gcol(x) return math.floor(x/TILE)+1 end
local function grow(y) return math.floor(y/TILE) end

-- ── init ─────────────────────────────────────────────────────────────────────

local function initMap()
  map={}
  for r=0,H-1 do
    map[r]={}
    for c=0,W-1 do
      if r==0 or r==H-1 or c==0 or c==W-1 then
        map[r][c]=T_WALL
      elseif (r<H//2-1 and r%2==0 or r>H//2 and (H-1-r)%2==0)
         and (c<W//2 and c%2==0 or c>=W//2 and (W-1-c)%2==0) then
        map[r][c]=T_WALL
      elseif math.random()<blockDensity then
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

local function shuffledDirs()
  local dirs={{0,-1},{0,1},{-1,0},{1,0}}
  for i=#dirs,2,-1 do
    local j=math.random(i)
    dirs[i],dirs[j]=dirs[j],dirs[i]
  end
  return dirs
end

function newPlayer(id,c,r)
  return {
    c=c, r=r,
    x=gpx(c), y=gpy(r),
    alive=true,
    stats={bombs=MAX_BOMBS,len=BLAST_LEN},
    bombs=0,
    shield=false,
    invul=0,
    color=COLORS[id],
    id=id,
    team=id,
    human=humans[id],
    dir={0,1},
    walkAnim=0,
    botDir={0,0},
    botOrder=shuffledDirs(),
    botDirTimer=0,
    botBombTimer=0,
    botEscape=0,
    deathT=0,
  }
end

local function initPlayers()
  players={}
  for i,s in ipairs(STARTS) do players[i]=newPlayer(i,s[1],s[2]) end
end

-- ── muzyka ───────────────────────────────────────────────────────────────────
-- Tracker jak moduł z Amigi: próbki z tools/music/instruments.py (bas z GeneralUser GS,
-- perkusja, wybuch) i oscylatory padu i melodii, miksowane w kanale PCM TIC-80 1.4, który gra
-- co klatkę 128 bajtów z 0x14E24 (7680 Hz) i sam je zeruje. 12 utworów gra po kolei; ostatnie
-- dwa takty utworu przenikają się z początkiem następnego.
-- Próbki leżą w TILES+SPRITES: tych obszarów nie wolno używać na grafikę.
local PCM,RATE,MUSIC_RAM=0x14E24,7680,0x04000
local ADPCM_STEPS={7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,55,
  60,66,73,80,88,97,107,118,130,143,157,173,190,209,230,253,279,307,337,
  371,408,449,494,544,598,658,724,796,876,963,1060,1166,1282,1411,1552,
  1707,1878,2066,2272,2499,2749,3024,3327,3660,4026,4428,4871,5358,5894,
  6484,7132,7845,8630,9493,10442,11487,12635,13899,15289,16818,18500,20350,
  22385,24623,27086,29794,32767}
local ADPCM_INDEX={-1,-1,-1,-1,2,4,6,8}
local SAMPLE_NAMES={"bass","slap","ghost","kick","snare","hat","ohat","boom"}
local BASS_NOTE=40  -- the bass samples are E2
SMP={}

local function ramWord(off)
  return peek(MUSIC_RAM+off)|peek(MUSIC_RAM+off+1)<<8
end

-- one IMA ADPCM sample from a 3-byte header (s16 predictor, u8 step index) and its nibbles
local function decodeSample(off,len)
  local pred,idx,out=ramWord(off),peek(MUSIC_RAM+off+2),{}
  if pred>32767 then pred=pred-65536 end
  for i=0,len-1 do
    local code=peek(MUSIC_RAM+off+3+(i>>1))
    if i&1==1 then code=code>>4 else code=code&15 end
    local step=ADPCM_STEPS[idx+1]
    local d=step>>3
    if code&4~=0 then d=d+step end
    if code&2~=0 then d=d+(step>>1) end
    if code&1~=0 then d=d+(step>>2) end
    if code&8~=0 then d=-d end
    pred=math.max(-32768,math.min(32767,pred+d))
    idx=math.max(0,math.min(88,idx+ADPCM_INDEX[(code&7)+1]))
    out[i+1]=pred//256
  end
  return out
end

local function loadSamples()
  if peek(MUSIC_RAM)~=#SAMPLE_NAMES then return end
  for k,name in ipairs(SAMPLE_NAMES) do
    SMP[name]=decodeSample(ramWord(1+(k-1)*4),ramWord(3+(k-1)*4))
  end
end

-- songs: bpm, bass key (MIDI), progression, bass riff, drums, melody seed
SONGS={
  {128,40,1,1,1,1},{124,43,2,2,1,2},{132,45,3,1,2,3},{120,38,1,3,3,4},
  {136,40,4,2,2,5},{126,41,2,1,1,6},{130,43,3,3,1,7},{122,45,4,1,3,8},
  {134,38,1,2,2,9},{128,36,2,3,1,10},{124,40,3,1,2,11},{132,43,4,2,1,12},
}
SONG_BARS=32
local CHORD={m={0,3,7},M={0,4,7},s={0,4,10}}
-- 8 bars each: bass root offset from the key and chord type
local PROGS={
  {{0,"m"},{0,"m"},{-4,"M"},{-2,"M"},{0,"m"},{0,"m"},{5,"m"},{-5,"s"}},
  {{0,"m"},{-2,"M"},{-4,"M"},{-5,"s"},{0,"m"},{-2,"M"},{-4,"M"},{-5,"s"}},
  {{0,"m"},{5,"m"},{-2,"M"},{3,"M"},{0,"m"},{5,"m"},{-5,"s"},{-5,"s"}},
  {{0,"m"},{-4,"M"},{5,"m"},{-2,"M"},{0,"m"},{-4,"M"},{-2,"M"},{-5,"s"}},
}
-- bass riffs, one character per 16th: n note, g ghost, p slap, b -2, f -5, d -4, u +3, w +2,
-- o slap an octave up, B/F slap -2/-1; the last bar of every 8 plays the fill
local RIFF_NOTE={n={0,"bass"},g={0,"ghost"},p={0,"slap"},b={-2,"bass"},f={-5,"bass"},d={-4,"bass"},
  u={3,"bass"},w={2,"bass"},o={12,"slap"},B={-2,"slap"},F={-1,"slap"}}
local RIFFS={"n.gp.ngb.npgf.bp","n.n.gpn.b.npg.fp","n..gn.pgn..gb.op"}
local FILL="ngpgbdfpbfpuwnBF"
-- drums: kick/snare line (K kick, S snare, X both) and hat line (H loud, h soft, O open)
local DRUMS={{"K...S.K...K.S...","HhHhHhOhHhHhHhOh"},{"K...X...K...X...","..H...H...H...H."},
  {"K.....K.S.....K.","HhHhHhHhHhHhHhHh"}}
local RHYTHMS={{{0,3},{3,3},{6,2},{8,6}},{{0,2},{2,2},{4,4},{8,8}},{{0,3},{4,2},{6,2},{8,4},{12,4}}}

local voices,duck={},0
musicSeqs={}

local function midiStep(m) return 440*2^((m-69)/12)/RATE end

local function playSample(name,rate,gain,seq)
  local s=SMP[name]
  if not s then return nil end
  local v={s=s,pos=1,rate=rate,g=gain,seq=seq}
  voices[#voices+1]=v
  return v
end

-- oscillator voice: saw (pad) or 30% pulse (melody) through a one-pole low-pass
local function playOsc(saw,midi,len,gain,seq,alpha)
  voices[#voices+1]={saw=saw,ph=0,inc=midiStep(midi),len=len,t=0,g=gain,seq=seq,lp=0,a=alpha}
end

-- the melody of one song: per bar of the progression, notes on its chord tones
local function melody(song)
  local seed,mel=song[6]*7919,{}
  local rhythm=RHYTHMS[song[6]%3+1]
  for bar=1,8 do
    local p=PROGS[song[3]][bar]
    local tones=CHORD[p[2]]
    mel[bar]={}
    for _,r in ipairs(rhythm) do
      seed=(seed*1103+12345)%65536
      local k=seed%4
      mel[bar][r[1]]={r[2],song[2]+24+p[1]+(k==3 and 12 or tones[k+1])}
    end
  end
  return mel
end

function startSong(n,fadeIn)
  local song=SONGS[n]
  local spb=RATE*60/song[1]/4
  local seq={n=n,song=song,bar=1,step=0,cnt=0,spb=spb,mel=melody(song),
    gain=fadeIn and 0 or 1,fade=fadeIn and 1/(32*spb) or 0}
  musicSeqs[#musicSeqs+1]=seq
  return seq
end

local function trigger(seq)
  local song,bar,step=seq.song,seq.bar,seq.step
  local p=PROGS[song[3]][(bar-1)%8+1]
  local root=song[2]+p[1]
  if step==0 then
    for _,i in ipairs(CHORD[p[2]]) do playOsc(true,root+12+i,16*seq.spb,0.09,seq,0.08) end
  end
  local riff=bar%8==0 and FILL or RIFFS[song[4]]
  local note=RIFF_NOTE[riff:sub(step+1,step+1)]
  if note then
    if seq.bass then seq.bass.rel=64 end
    seq.bass=playSample(note[2],2^((root+note[1]-BASS_NOTE)/12),note[2]=="ghost" and 0.4 or 0.6,seq)
  end
  local d=DRUMS[song[5]]
  local ks,hh=d[1]:sub(step+1,step+1),d[2]:sub(step+1,step+1)
  if ks=="K" or ks=="X" then playSample("kick",1,0.55,seq) end
  if ks=="S" or ks=="X" then playSample("snare",1,0.4,seq) end
  if hh~="." then playSample(hh=="O" and "ohat" or "hat",1,hh=="h" and 0.12 or 0.2,seq) end
  local pass=(bar-1)//8
  local m=pass%2==1 and seq.mel[(bar-1)%8+1][step]
  if m then playOsc(false,m[2],m[1]*seq.spb,0.14,seq,0.3) end
end

-- one sequencer sample: steps, the next song two bars before the end, the fades
local function tickSeq(seq)
  seq.cnt=seq.cnt-1
  if seq.cnt<=0 then
    seq.cnt=seq.cnt+seq.spb
    if seq.bar<=SONG_BARS then trigger(seq) end
    seq.step=seq.step+1
    if seq.step==16 then
      seq.step=0
      seq.bar=seq.bar+1
      if seq.bar==SONG_BARS-1 and not seq.next then
        seq.next=startSong(seq.n%#SONGS+1,true)
        seq.fade=-1/(32*seq.spb)
      end
    end
  end
  seq.gain=math.max(0,math.min(1,seq.gain+seq.fade))
end

function startMusic()
  loadSamples()
  voices,musicSeqs,duck={},{},0
  if SMP.bass then startSong(1,false) end
end

function sndExplosion()
  if SMP.boom then
    playSample("boom",1,0.6,nil)
    duck=#SMP.boom
  end
end

local function updateMusic()
  if #voices==0 and #musicSeqs==0 then return end
  for k=0,127 do
    for _,s in ipairs(musicSeqs) do tickSeq(s) end
    local mus,fx=0,0
    for _,v in ipairs(voices) do
      local x=0
      if v.s then
        x=v.s[v.pos//1] or 0
        v.pos=v.pos+v.rate
        if v.rel then v.rel=v.rel-1 x=x*v.rel/64 end
        if v.pos>#v.s+1 or (v.rel and v.rel<=0) then v.dead=true end
      else
        v.t=v.t+1
        v.ph=(v.ph+v.inc)%1
        local raw=v.saw and v.ph*2-1 or (v.ph<0.3 and 1 or -1)
        v.lp=v.lp+v.a*(raw-v.lp)
        x=v.lp*127*math.min(1,v.t/200,(v.len-v.t)/300)
        if v.t>=v.len then v.dead=true end
      end
      if v.seq then mus=mus+x*v.g*v.seq.gain else fx=fx+x*v.g end
    end
    -- the music ducks under an explosion so the blast stands out
    if duck>0 then duck=duck-1 mus=mus/2 end
    poke(PCM+k,math.max(-128,math.min(127,(mus+fx)//1))+128)
  end
  local live={}
  for _,v in ipairs(voices) do if not v.dead then live[#live+1]=v end end
  voices=live
  local playing={}
  for _,s in ipairs(musicSeqs) do if s.bar<=SONG_BARS or s.gain>0 then playing[#playing+1]=s end end
  musicSeqs=playing
end

local WAVES,SFX_RAM=0x0FFE4,0x100E4  -- 16 B na falę, 66 B na slot SFX
local NOISE,SAW,TRI=0,1,3

-- Jeden slot SFX w formacie TIC-80 1.x; ticks={{głośność 0-15, półtony w górę 0-15}, ...}.
-- TIC-80 zapisuje głośność jako tłumienie (0 = najgłośniej), więc ticki po dźwięku muszą być
-- zapisane jako cisza, inaczej efekt gra pełną głośnością do końca czasu z sfx().
local function putSfx(n,ticks,wave,octave,note)
  local b=SFX_RAM+66*n
  for i=0,29 do
    local t=ticks[i+1] or {0,0}
    poke(b+i*2,(15-t[1])|wave<<4)
    poke(b+i*2+1,t[2])
  end
  poke(b+60,octave)
  poke(b+61,note)
  for i=62,65 do poke(b+i,0) end
end

-- Sweetie16 has no skin or wood tones; colours drawn nowhere else become them.
SKIN,WOOD,WOOD_DARK=10,1,8
local function setColour(i,r,g,b)
  poke(0x03FC0+i*3,r); poke(0x03FC0+i*3+1,g); poke(0x03FC0+i*3+2,b)
end
function initPalette()
  setColour(SKIN,0xFF,0xCC,0xAA)
  setColour(WOOD,0xC8,0x92,0x52)
  setColour(WOOD_DARK,0x5C,0x3A,0x1A)
end

-- ── language ──────────────────────────────────────────────────────────────────
-- English by default, Polish to choose (saved in pmem). TIC-80's font has no Polish letters:
-- they are built at start into the unused control codes 1..18 of both fonts, from the plain
-- letter plus a mark, and L() turns a Polish text's UTF-8 letters into those codes.
LANG_SLOT=1
LANG=pmem and pmem(LANG_SLOT)==1 and "pl" or "en"
local FONT=0x14604
local PL_LETTERS="ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
local PL_BASE="acelnoszzACELNOSZZ"
local PL_MARK="oaosaaaadoaosaaaad"  -- o ogonek, a acute, s stroke, d dot
local plCode,plCache={},{}
-- every Polish letter is two bytes in UTF-8 (TIC-80 has no utf8 library)
for k=1,#PL_LETTERS//2 do plCode[PL_LETTERS:sub(2*k-1,2*k)]=string.char(k) end

local function markGlyph(code,base,mark)
  local rows,top,bottom,minc,maxc={},8,-1,8,-1
  for r=0,7 do
    local b=peek(FONT+base*8+r)
    rows[r]=b
    for i=0,7 do
      if (b>>i)&1==1 then top,bottom=math.min(top,r),math.max(bottom,r) minc,maxc=math.min(minc,i),math.max(maxc,i) end
    end
  end
  local function set(c,r) if r>=0 and r<8 and c>=0 and c<8 then rows[r]=rows[r]|(1<<c) end end
  local mid=(minc+maxc+1)//2
  -- a capital has no room for a mark above it: it moves down
  local drop=(mark=="a" or mark=="d") and math.min(math.max(0,2-top),7-bottom) or 0
  for r=7,0,-1 do rows[r]=r>=drop and rows[r-drop] or 0 end
  top,bottom=top+drop,bottom+drop
  if mark=="o" then set(maxc,bottom+1) set(maxc+1,bottom+2)
  elseif mark=="a" then set(mid+1,math.max(0,top-2))
  elseif mark=="d" then set(mid,math.max(0,top-2))
  else
    local r=(top+bottom)//2
    set(minc-1,r) set(minc+1+((rows[r]>>(minc+1))&1),r)
  end
  for r=0,7 do poke(FONT+code*8+r,rows[r]) end
end

function initFont()
  for k=1,#PL_BASE do
    local base,mark=PL_BASE:byte(k),PL_MARK:sub(k,k)
    markGlyph(k,base,mark)
    markGlyph(128+k,128+base,mark)
  end
end

-- the text in the chosen language; the Polish one with its letters in the font's codes
function L(en,pl)
  if LANG~="pl" or not pl then return en end
  local c=plCache[pl]
  if not c then
    c=pl:gsub("[\xC3-\xC5][\x80-\xBF]",plCode)
    plCache[pl]=c
  end
  return c
end

local audioReady=false
local function initAudio()
  if audioReady then return end
  audioReady=true

  -- Wave 0: płaska fala zerowa, którą TIC-80 gra jako szum
  for i=0,15 do poke(WAVES+i,0) end

  -- Wave 1: opadająca piła
  for i=0,15 do
    poke(WAVES+16+i, (15-i*2%16)|((15-(i*2+1)%16)<<4))
  end

  -- Wave 2: prostokąt
  for i=0,7  do poke(WAVES+32+i,0x00) end
  for i=8,15 do poke(WAVES+32+i,0xFF) end

  -- Wave 3: trójkąt
  local tri={0x10,0x32,0x54,0x76,0x98,0xBA,0xDC,0xFE,
             0xEF,0xCD,0xAB,0x89,0x67,0x45,0x23,0x01}
  for i=0,15 do poke(WAVES+48+i,tri[i+1]) end

  -- SFX 1: śmierć — "aaah!" opadające od A4 do A3
  putSfx(1,{{13,12},{13,10},{12,7},{11,5},{10,3},{8,1},{6,0},{4,0},{2,0}},SAW,3,9)
  -- SFX 5: postawienie bomby — krótki, niski, miękki stuk
  putSfx(5,{{12,0},{10,0},{7,0},{4,0}},TRI,2,0)
  -- SFX 6: podniesienie bonusu — rosnące arpeggio C-E-G-C
  putSfx(6,{{11,0},{11,0},{11,4},{11,4},{11,7},{11,7},{10,12},{7,12},{4,12}},TRI,4,0)
  -- SFX 7: pęknięcie tarczy — krótki opadający szum
  putSfx(7,{{13,0},{11,0},{8,0},{5,0},{2,0}},NOISE,4,0)
end

function sndPickup() sfx(6,-1,24,3,15) end
function sndShield() sfx(7,-1,24,3,15) end

function init()
  math.randomseed(time())
  mode,camX,camY,boss,monsters,hidden="pvp",0,0,nil,{},{}
  setArena(32,18)
  blockDensity=0.4
  bombs={}
  blasts={}
  powerups={}
  initMap()
  initPlayers()
  initAudio()
  initPalette()
  resetShrink()
  frame=0
  state="game"
  winner=nil
  restartTimer=0
end

-- ── blast ─────────────────────────────────────────────────────────────────────

-- exit, keys and the dragon's egg survive blasts: a stage could not be finished without them
local QUEST_ITEM={X=true,K=true,E=true}

local function removePowerupAt(c,r)
  for i=#powerups,1,-1 do
    local pu=powerups[i]
    if pu.c==c and pu.r==r and not QUEST_ITEM[pu.kind] then table.remove(powerups,i) end
  end
end

-- owner: the player whose bomb it was, BOSS_FIRE for a boss's bombs and breath
BOSS_FIRE={bombs=0}

local function addBlast(c,r,owner)
  blasts[#blasts+1]={c=c,r=r,t=BLAST_TIME,owner=owner}
  removePowerupAt(c,r)
end

local function dropPowerup(c,r)
  local quest=hidden[c*100+r]
  if quest then
    powerups[#powerups+1]={c=c,r=r,kind=quest}
  elseif math.random()<POWERUP_CHANCE then
    powerups[#powerups+1]={c=c,r=r,kind=POWERUP_KINDS[math.random(#POWERUP_KINDS)]}
  end
end

-- returns set of covered cells keyed c*100+r
local function explode(b)
  sndExplosion()
  local bc,br=b.c,b.r
  local len=b.len or BLAST_LEN
  local hit={}
  addBlast(bc,br,b.owner)
  hit[bc*100+br]=true
  local dirs={{0,-1},{0,1},{-1,0},{1,0}}
  for _,d in ipairs(dirs) do
    for i=1,len do
      local nc,nr=bc+d[1]*i,br+d[2]*i
      local t=mget(nc,nr)
      if t==T_WALL then break end
      addBlast(nc,nr,b.owner)
      hit[nc*100+nr]=true
      if t==T_BLOCK then mset(nc,nr,T_EMPTY) dropPowerup(nc,nr) break end
    end
  end
  if b.owner then b.owner.bombs=math.max(0,b.owner.bombs-1) end
  return hit
end

-- ── physics ───────────────────────────────────────────────────────────────────

-- bombs covered by a blast explode in the same tick, until no new ones are hit
local function updateBombs()
  local queue,keep={},{}
  for _,b in ipairs(bombs) do
    b.t=b.t-1
    if b.t<=0 then queue[#queue+1]=b else keep[#keep+1]=b end
  end
  bombs=keep
  local k=1
  while k<=#queue do
    local hit=explode(queue[k])
    k=k+1
    local rest={}
    for _,b in ipairs(bombs) do
      if hit[b.c*100+b.r] then queue[#queue+1]=b else rest[#rest+1]=b end
    end
    bombs=rest
  end
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

-- a blast on p's cell hurts p, except in the campaign one made by a fellow hero's bomb
local function blastHurts(p)
  for _,bl in ipairs(blasts) do
    local o=bl.owner
    if bl.c==p.c and bl.r==p.r and not (mode=="camp" and o and o~=p and o.team==p.team) then
      return true
    end
  end
  return false
end

local function isBomb(c,r)
  for _,b in ipairs(bombs) do
    if b.c==c and b.r==r then return true end
  end
  return false
end

local function collectPowerup(p)
  for i,pu in ipairs(powerups) do
    if pu.c==p.c and pu.r==p.r and (p.team==1 or not QUEST_ITEM[pu.kind]) then
      if pu.kind=="K" then camp.keys=camp.keys+1
      elseif pu.kind=="X" then camp.done=true
      elseif pu.kind=="E" then camp.friend=true
      elseif pu.kind=="B" then p.stats.bombs=math.min(BOMB_CAP,p.stats.bombs+1)
      elseif pu.kind=="R" then p.stats.len=math.min(LEN_CAP,p.stats.len+1)
      elseif pu.kind=="S" then p.shield=true end
      table.remove(powerups,i)
      sndPickup()
      return
    end
  end
end

local function movePlayer(p,dc,dr)
  local nx=p.x+dc*SPEED
  local ny=p.y+dr*SPEED
  local margin=1
  -- cells where player's hitbox currently overlaps own bomb → passable this frame
  local passable={}
  for _,b in ipairs(bombs) do
    if b.owner==p then
      local ox0=gcol(p.x+margin); local ox1=gcol(p.x+TILE-margin-1)
      local oy0=grow(p.y+margin); local oy1=grow(p.y+TILE-margin-1)
      if b.c>=ox0 and b.c<=ox1 and b.r>=oy0 and b.r<=oy1 then
        passable[b.c*100+b.r]=true
      end
    end
  end
  local function blocked(x,y)
    local cs={
      {gcol(x+margin),          grow(y+margin)},
      {gcol(x+TILE-margin-1),   grow(y+margin)},
      {gcol(x+margin),          grow(y+TILE-margin-1)},
      {gcol(x+TILE-margin-1),   grow(y+TILE-margin-1)},
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

  -- corner assist: off the row (column) axis, slide toward the row whose next cell in the
  -- pressed direction is open, the nearer one first; also centres the player while walking
  local function assist(pos,aheadFree,stepFree)
    local a=pos-pos%TILE
    if pos==a then return pos end
    local near,far=a,a+TILE
    if pos-a>TILE//2 then near,far=far,near end
    for _,t in ipairs({near,far}) do
      if aheadFree(t) then
        local s=t>pos and SPEED or -SPEED
        if stepFree(pos+s) then return pos+s end
        return pos
      end
    end
    return pos
  end
  if dc~=0 then
    p.y=assist(p.y,function(t) return not blocked(nx,t) end,function(v) return not blocked(p.x,v) end)
  end
  if dr~=0 then
    p.x=assist(p.x,function(t) return not blocked(t,ny) end,function(v) return not blocked(v,p.y) end)
  end

  p.c=gcol(p.x+TILE//2)
  p.r=grow(p.y+TILE//2)
  collectPowerup(p)
end

local function placeBomb(p)
  if p.bombs<p.stats.bombs then
    local bc=gcol(p.x+TILE//2)
    local br=grow(p.y+TILE//2)
    if not isBomb(bc,br) then
      bombs[#bombs+1]={c=bc,r=br,t=BOMB_TIMER,owner=p,len=p.stats.len}
      p.bombs=p.bombs+1
      sfx(5,-1,20,3,15)
      return true
    end
  end
  return false
end

local function killPlayer(p)
  p.alive=false
  p.deathT=DEATH_TIME
  sfx(1,-1,15,1,15)
end

local function updateDeaths()
  for _,p in ipairs(players) do
    if p.deathT>0 then p.deathT=p.deathT-1 end
  end
end

-- ── human player ─────────────────────────────────────────────────────────────

local function blastHit(p)
  if not p.alive or p.invul>0 then return end
  if p.shield then
    p.shield=false
    p.invul=SHIELD_INVUL
    sndShield()
  else
    killPlayer(p)
  end
end

local function updateInvul()
  for _,p in ipairs(players) do
    if p.invul>0 then p.invul=p.invul-1 end
  end
end

local function updatePlayer(p)
  if not p.alive then return end
  local off=(p.id-1)*8
  local ox,oy=p.x,p.y
  if frame%MOVE_PERIOD==0 then
    if btn(off+B_UP)    then movePlayer(p, 0,-1); p.dir={0,-1} end
    if btn(off+B_DOWN)  then movePlayer(p, 0, 1); p.dir={0, 1} end
    if btn(off+B_LEFT)  then movePlayer(p,-1, 0); p.dir={-1,0} end
    if btn(off+B_RIGHT) then movePlayer(p, 1, 0); p.dir={ 1,0} end
  end
  if p.x~=ox or p.y~=oy then p.walkAnim=p.walkAnim+1 end
  if btnp(off+B_BOMB) then placeBomb(p) end
  if blastHurts(p) then blastHit(p) end
end

-- ── bot AI ────────────────────────────────────────────────────────────────────

local BOT_DIRS={{0,-1},{0,1},{-1,0},{1,0}}
-- tie-break order of the bot being updated; a fixed order per bot and round keeps its
-- route stable between frames while no corner of the map is favoured
local botOrder=BOT_DIRS
-- bombs due within this many frames make their blast cells dangerous to the bot
local BOT_FLEE_FRAMES=BOMB_TIMER
local BOT_PICKUP_RANGE=10

local function botPassable(c,r)
  return mget(c,r)==T_EMPTY and not isBomb(c,r)
end

-- BFS from (sc,sr) over cells accepted by isOpen. Returns the cells from the
-- start (exclusive) to the nearest cell accepted by isGoal, or nil.
function botPath(sc,sr,isOpen,isGoal)
  local came={}
  local seen={[sr*W+sc]=true}
  local qc,qr={sc},{sr}
  local head=1
  while head<=#qc do
    local c,r=qc[head],qr[head]
    head=head+1
    if (c~=sc or r~=sr) and isGoal(c,r) then
      local path={}
      while came[r*W+c] do
        table.insert(path,1,{c=c,r=r})
        c,r=came[r*W+c][1],came[r*W+c][2]
      end
      return path
    end
    for _,d in ipairs(botOrder) do
      local nc,nr=c+d[1],r+d[2]
      local nk=nr*W+nc
      if not seen[nk] and isOpen(nc,nr) then
        seen[nk]=true
        came[nk]={c,r}
        qc[#qc+1]=nc; qr[#qr+1]=nr
      end
    end
  end
  return nil
end

-- cells that will burn: current blasts plus blasts of bombs due within `horizon`
-- frames, closed over chain reactions (a blast reaching a bomb sets it off)
local function botDanger(horizon,extra)
  local list={}
  for _,b in ipairs(bombs) do list[#list+1]=b end
  if extra then list[#list+1]=extra end
  local fire={}
  for _,bl in ipairs(blasts) do fire[bl.r*W+bl.c]=true end
  local closing=shrinkClosing()
  for _,cell in ipairs(closing or {}) do fire[cell[2]*W+cell[1]]=true end
  local going={}
  local changed=true
  while changed do
    changed=false
    for i,b in ipairs(list) do
      if not going[i] and (b.t<=horizon or fire[b.r*W+b.c]) then
        going[i]=true
        changed=true
        fire[b.r*W+b.c]=true
        for _,d in ipairs(BOT_DIRS) do
          for k=1,b.len or BLAST_LEN do
            local nc,nr=b.c+d[1]*k,b.r+d[2]*k
            local t=mget(nc,nr)
            if t==T_WALL then break end
            fire[nr*W+nc]=true
            if t==T_BLOCK then break end
          end
        end
      end
    end
  end
  return fire
end

local BOT_STEP=TILE*MOVE_PERIOD

-- frames until each cell starts burning and until it stops, keyed r*W+c; a bomb hit
-- by an earlier blast goes off at that moment (chain reactions)
local function botFireTimes(extra)
  local list={}
  for _,b in ipairs(bombs) do list[#list+1]={c=b.c,r=b.r,len=b.len,t=b.t} end
  if extra then list[#list+1]={c=extra.c,r=extra.r,len=extra.len,t=extra.t} end
  local from,to={},{}
  local function burn(k,s)
    if not from[k] or s<from[k] then from[k]=s end
    if not to[k] or s+BLAST_TIME>to[k] then to[k]=s+BLAST_TIME end
  end
  for _,bl in ipairs(blasts) do
    local k=bl.r*W+bl.c
    from[k]=0
    to[k]=math.max(to[k] or 0,bl.t)
  end
  local closing,left=shrinkClosing()
  for _,cell in ipairs(closing or {}) do
    local k=cell[2]*W+cell[1]
    from[k]=math.min(from[k] or left,left)
    to[k]=math.huge
  end
  for _,b in ipairs(list) do
    local s=from[b.r*W+b.c]
    if s and s<b.t then b.t=s end
  end
  local changed=true
  while changed do
    changed=false
    for _,b in ipairs(list) do
      local cells={{b.c,b.r}}
      for _,d in ipairs(BOT_DIRS) do
        for k=1,b.len or BLAST_LEN do
          local nc,nr=b.c+d[1]*k,b.r+d[2]*k
          local t=mget(nc,nr)
          if t==T_WALL then break end
          cells[#cells+1]={nc,nr}
          if t==T_BLOCK then break end
        end
      end
      for _,cell in ipairs(cells) do
        local k=cell[2]*W+cell[1]
        if not from[k] or b.t<from[k] or to[k]<b.t+BLAST_TIME then
          burn(k,b.t)
          changed=true
        end
        for _,o in ipairs(list) do
          if o.c==cell[1] and o.r==cell[2] and o.t>b.t then o.t=b.t; changed=true end
        end
      end
    end
  end
  return from,to
end

-- shortest path from (sc,sr) that never steps into a cell while it burns and ends on
-- a cell that is not burning when the bot gets there; nil when there is none
local function botEscapePath(sc,sr,from,to,blocked)
  local function burning(k,a) return from[k]~=nil and from[k]<=a+BOT_STEP//2 and to[k]>a end
  local function safeEnd(k,a) return from[k]==nil or to[k]<=a end
  local came={}
  local seen={[sr*W+sc]=true}
  local qc,qr,qd={sc},{sr},{0}
  local head=1
  while head<=#qc do
    local c,r,d=qc[head],qr[head],qd[head]
    head=head+1
    if d>0 and safeEnd(r*W+c,d*BOT_STEP) then
      local path={}
      while came[r*W+c] do
        table.insert(path,1,{c=c,r=r})
        c,r=came[r*W+c][1],came[r*W+c][2]
      end
      return path
    end
    for _,dir in ipairs(botOrder) do
      local nc,nr=c+dir[1],r+dir[2]
      local nk=nr*W+nc
      if not seen[nk] and nk~=blocked and botPassable(nc,nr) and not burning(nk,(d+1)*BOT_STEP) then
        seen[nk]=true
        came[nk]={c,r}
        qc[#qc+1]=nc; qr[#qr+1]=nr; qd[#qd+1]=d+1
      end
    end
  end
  return nil
end

-- a living enemy of p on (c,r): another team's player, or for the heroes a monster or the boss
function foeAt(p,c,r)
  for _,op in ipairs(players) do
    if op.alive and op.team~=p.team and op.c==c and op.r==r then return true end
  end
  if p.team==1 and mode=="camp" then
    for _,m in ipairs(monsters) do if m.c==c and m.r==r then return true end end
    local b=boss
    if b and b.hp>0 and c>=b.c and c<=b.c+1 and r>=b.r and r<=b.r+1 then return true end
  end
  return false
end

-- true when a living enemy stands in the blast line of a bomb laid on (c,r)
local function botEnemySpot(p,c,r)
  for _,d in ipairs(BOT_DIRS) do
    for k=1,p.stats.len do
      local nc,nr=c+d[1]*k,r+d[2]*k
      local t=mget(nc,nr)
      if t~=T_EMPTY then break end
      if foeAt(p,nc,nr) then return true end
    end
  end
  return false
end

-- a bomb laid on (c,r) is a trap when the bot can leave its blast but an enemy in
-- it cannot, the bomb itself blocking that enemy's way
local function botTrapSpot(p,c,r)
  if not botEnemySpot(p,c,r) then return false end
  local from,to=botFireTimes({c=c,r=r,t=BOMB_TIMER,len=p.stats.len})
  if not botEscapePath(c,r,from,to) then return false end
  for _,op in ipairs(players) do
    local k=op.r*W+op.c
    if op.alive and op.team~=p.team and from[k] and not botEscapePath(op.c,op.r,from,to,r*W+c) then
      return true
    end
  end
  return false
end

-- a cell is a target spot when a destructible block is next to it or an enemy is in its blast line
local function botIsTargetSpot(p,c,r)
  for _,d in ipairs(BOT_DIRS) do
    if mget(c+d[1],r+d[2])==T_BLOCK then return true end
  end
  return botEnemySpot(p,c,r)
end

-- first step towards an item within BOT_PICKUP_RANGE steps over cells not on fire, or nil
local function botPickupDir(p,danger)
  if #powerups==0 then return nil end
  local item={}
  for _,pu in ipairs(powerups) do
    if p.team==1 or not QUEST_ITEM[pu.kind] then item[pu.r*W+pu.c]=pu.kind end
  end
  local path=botPath(p.c,p.r,
    function(c,r) return botPassable(c,r) and not danger[r*W+c] end,
    function(c,r) return item[r*W+c] end)
  if not path then return nil end
  local last=path[#path]
  -- quest items are worth any walk: the stage cannot be won without them
  if #path<=BOT_PICKUP_RANGE or QUEST_ITEM[item[last.r*W+last.c]] then
    return {path[1].c-p.c, path[1].r-p.r}
  end
  return nil
end

local function botStepOk(p,d,danger)
  local nc,nr=p.c+d[1],p.r+d[2]
  return botPassable(nc,nr) and not danger[nr*W+nc]
end

-- a random direction onto a free cell outside the danger map, or standing still
local function botSafeDir(p,danger)
  for _=1,8 do
    local d=BOT_DIRS[math.random(4)]
    if botStepOk(p,d,danger) then return d end
  end
  return {0,0}
end

local function botSign(v) return v>0 and 1 or (v<0 and -1 or 0) end

-- while moving, first line up with the current cell's grid on the perpendicular
-- axis, so a turn at a corner is not blocked by a wall corner
local function botSteer(p,dc,dr)
  if dr~=0 and p.x~=gpx(p.c) then return botSign(gpx(p.c)-p.x),0 end
  if dc~=0 and p.y~=gpy(p.r) then return 0,botSign(gpy(p.r)-p.y) end
  return dc,dr
end

-- true when a bomb placed on (c,r) leaves a cell outside its blast reachable
-- before it explodes; cells not yet on fire may be crossed on the way
local function botBombSafe(p,c,r)
  local from,to=botFireTimes({c=c,r=r,t=BOMB_TIMER,len=p.stats.len})
  return botEscapePath(c,r,from,to)~=nil
end

local function botTryBomb(p)
  if not botIsTargetSpot(p,p.c,p.r) or not botBombSafe(p,p.c,p.r) then return false end
  return placeBomb(p)
end

-- for a hero: the first step towards the safe bomb spot nearest to a sparkling crate, so it
-- digs its way to the quest item instead of blowing up the closest crates
function botQuestDir(p,danger)
  local quests={}
  for k in pairs(hidden) do
    if mget(k//100,k%100)==T_BLOCK then quests[#quests+1]={k//100,k%100} end
  end
  if #quests==0 then return nil end
  local function dist(c,r)
    local m=math.huge
    for _,q in ipairs(quests) do m=math.min(m,math.abs(c-q[1])+math.abs(r-q[2])) end
    return m
  end
  local function open(c,r) return botPassable(c,r) and not danger[r*W+c] end
  local spots,seen,queue,i={},{[p.r*W+p.c]=true},{{p.c,p.r}},1
  while queue[i] do
    local c,r=queue[i][1],queue[i][2]
    i=i+1
    if botIsTargetSpot(p,c,r) then spots[#spots+1]={c,r,dist(c,r),i} end
    for _,d in ipairs(BOT_DIRS) do
      local nc,nr=c+d[1],r+d[2]
      if not seen[nr*W+nc] and open(nc,nr) then seen[nr*W+nc]=true queue[#queue+1]={nc,nr} end
    end
  end
  -- ties go to the spot nearer the bot (earlier in the flood); otherwise two equal spots on
  -- opposite sides make it turn back and forth every step
  table.sort(spots,function(a,b) return a[3]<b[3] or a[3]==b[3] and a[4]<b[4] end)
  for _,sp in ipairs(spots) do
    if botBombSafe(p,sp[1],sp[2]) then
      if sp[1]==p.c and sp[2]==p.r then return nil end
      local path=botPath(p.c,p.r,open,function(c,r) return c==sp[1] and r==sp[2] end)
      return path and {path[1].c-p.c,path[1].r-p.r}
    end
  end
  return nil
end

local function updateBot(p)
  if not p.alive then return end
  botOrder=p.botOrder

  p.botDirTimer=p.botDirTimer-1

  local danger=botDanger(BOT_FLEE_FRAMES)
  if mode=="camp" and p.team==1 then
    -- a hero bot keeps a step away from monsters, which kill on touch
    for _,m in ipairs(monsters) do
      danger[m.r*W+m.c]=true
      for _,d in ipairs(BOT_DIRS) do danger[(m.r+d[2])*W+m.c+d[1]]=true end
    end
    -- and out of the line the dragon is about to breathe fire along
    local wn=boss and boss.warn
    if wn then
      for k=1,(wn.row and W or H)-2 do danger[(wn.row and wn.r or k)*W+(wn.row and k or wn.c)]=true end
    end
  end
  local dir
  local pickup=not danger[p.r*W+p.c] and botPickupDir(p,danger)
  if danger[p.r*W+p.c] then
    -- flee: timed path to a cell that is safe on arrival; any path out when none is
    local from,to=botFireTimes()
    local path=botEscapePath(p.c,p.r,from,to)
    -- the timed escape knows only bombs: if it ends next to a monster or in dragon fire,
    -- head for a cell outside all danger instead
    local stop=path and path[#path]
    if not path or (stop and danger[stop.r*W+stop.c]) then
      path=botPath(p.c,p.r,botPassable,function(c,r) return not danger[r*W+c] end) or path
    end
    if path then dir={path[1].c-p.c, path[1].r-p.r} else dir=BOT_DIRS[math.random(4)] end
  elseif botTryBomb(p) then
    dir={0,0}
  elseif pickup then
    dir=pickup
  elseif p.bombs<p.stats.bombs then
    -- hunt: walk to a cell from which a bomb is safe to lay, enemies before blocks
    local function huntStep(isSpot)
      local path=botPath(p.c,p.r,
        function(c,r) return botPassable(c,r) and not danger[r*W+c] end,
        function(c,r) return isSpot(p,c,r) and botBombSafe(p,c,r) end)
      return path and {path[1].c-p.c, path[1].r-p.r}
    end
    dir=(p.team==1 and botQuestDir(p,danger)) or huntStep(botTrapSpot) or huntStep(botEnemySpot)
      or huntStep(botIsTargetSpot)
  end

  if not dir then
    -- nothing to hunt: wander in a safe direction, re-picked on a timer or when stuck
    if p.botDirTimer<=0 or not botStepOk(p,p.botDir,danger) then
      p.botDir=botSafeDir(p,danger)
      p.botDirTimer=15+math.random(25)
    end
    dir=p.botDir
  end
  p.botDir=dir

  if frame%MOVE_PERIOD==0 then
    local dc,dr=botSteer(p,dir[1],dir[2])
    local ox,oy=p.x,p.y
    if dc~=0 or dr~=0 then p.dir={dc,dr} end
    movePlayer(p,dc,dr)
    if p.x==ox and p.y==oy then
      p.botDirTimer=0
    else
      p.walkAnim=p.walkAnim+1
    end
  end

  if blastHurts(p) then blastHit(p) end
end

-- ── arena shrink ──────────────────────────────────────────────────────────────

SHRINK_DELAY=1800
SHRINK_PAUSE=120
SHRINK_WARN=300
SHRINK_CYCLE=SHRINK_PAUSE+SHRINK_WARN
local WARN_COL=9
local WARN_SLOWEST,WARN_FASTEST=24,4

-- open interior still in play; shrinkAt is the frame at which the next step closes
function resetShrink()
  zoneCycle,zoneSteps=SHRINK_CYCLE,0
  shrinkBox={x0=1,y0=1,x1=W-2,y1=H-2}
  shrinkAt=SHRINK_DELAY+SHRINK_CYCLE-1
  roundFrames=0
end
resetShrink()

local function shrinkTile(c,r)
  mset(c,r,T_WALL)
  for i=#monsters,1,-1 do
    if monsters[i].c==c and monsters[i].r==r then table.remove(monsters,i) end
  end
  local items={}
  for _,pu in ipairs(powerups) do
    if pu.c~=c or pu.r~=r then items[#items+1]=pu end
  end
  powerups=items
  for _,p in ipairs(players) do
    if p.alive and p.c==c and p.r==r then killPlayer(p) end
  end
  local keep={}
  for _,b in ipairs(bombs) do
    if b.c==c and b.r==r then
      b.owner.bombs=math.max(0,b.owner.bombs-1)
    else
      keep[#keep+1]=b
    end
  end
  bombs=keep
end

-- the zone stops at this strip in the middle, so its last step never kills everyone at once
local ZONE_MIN_W,ZONE_MIN_H=4,2

-- a box only ZONE_MIN_H tall loses its two side columns per step, a taller one its outline
local function thin(box)
  return box.y1-box.y0+1<=ZONE_MIN_H
end

-- open tiles the next step closes
local function stepCells(box)
  local cells={}
  local function add(c,r)
    if mget(c,r)~=T_WALL then cells[#cells+1]={c,r} end
  end
  for r=box.y0,box.y1 do
    add(box.x0,r)
    if box.x1>box.x0 then add(box.x1,r) end
  end
  if not thin(box) then
    for c=box.x0+1,box.x1-1 do
      add(c,box.y0)
      if box.y1>box.y0 then add(c,box.y1) end
    end
  end
  return cells
end

local function advanceBox(box)
  local sides=thin(box)
  box.x0,box.x1=box.x0+1,box.x1-1
  if not sides then box.y0,box.y1=box.y0+1,box.y1-1 end
end

-- the next step with open tiles, skipping steps that have none; nil once only the middle
-- strip is left
local function nextStepCells()
  local box=shrinkBox
  while not (thin(box) and box.x1-box.x0+1<=ZONE_MIN_W) do
    local cells=stepCells(box)
    if #cells>0 then return cells end
    advanceBox(box)
  end
  return nil
end

-- every SHRINK_CYCLE frames after SHRINK_DELAY one step blinks for SHRINK_WARN frames
-- and then turns to wall all at once
function updateShrink()
  roundFrames=roundFrames+1
  if roundFrames<shrinkAt then return end
  local cells=nextStepCells()
  if not cells then return end
  for _,cell in ipairs(cells) do shrinkTile(cell[1],cell[2]) end
  zoneSteps=zoneSteps+1
  advanceBox(shrinkBox)
  shrinkAt=roundFrames+zoneCycle
end

-- while a step blinks: its open tiles and the frames left before it closes
function shrinkClosing()
  local left=shrinkAt-roundFrames
  if left>SHRINK_WARN then return nil end
  local cells=nextStepCells()
  if not cells then return nil end
  return cells,left
end

-- tiles tinted right now: the closing step, blinking faster as it nears closing
local function shrinkWarnTiles()
  local warn={}
  local cells,left=shrinkClosing()
  if not cells then return warn end
  local progress=1-left/SHRINK_WARN
  local period=math.floor(WARN_SLOWEST-(WARN_SLOWEST-WARN_FASTEST)*progress)
  if roundFrames%period>=period//2 then return warn end
  for _,cell in ipairs(cells) do warn[cell[1]*100+cell[2]]=true end
  return warn
end

-- ── draw ─────────────────────────────────────────────────────────────────────

local WALL_COL=13
local BLOCK_COL=WOOD
local FLOOR_COL=0
local BOMB_COL=2

local function drawMap()
  local warn=shrinkWarnTiles()
  local c0,r0=camX//TILE+1,camY//TILE+1
  for r=r0,math.min(H-2,r0+16) do
    for c=c0,math.min(W-2,c0+30) do
      local t=mget(c,r)
      local col=FLOOR_COL
      if t==T_WALL  then col=WALL_COL
      elseif t==T_BLOCK then col=BLOCK_COL end
      if warn[c*100+r] then col=WARN_COL end
      local x,y=gpx(c)-camX,gpy(r)-camY
      rect(x,y,TILE,TILE,col)
      if t==T_WALL then
        rectb(x,y,TILE,TILE,15)
      elseif t==T_BLOCK and not warn[c*100+r] then
        rectb(x,y,TILE,TILE,WOOD_DARK)
      end
    end
  end
  rectb(-camX,TILE-camY,(W-2)*TILE,(H-2)*TILE,WALL_COL)
end

local function drawBlasts()
  for _,bl in ipairs(blasts) do
    local age=BLAST_TIME-bl.t
    local r=math.min(TILE//2-1,1+age//3)
    local frac=bl.t/BLAST_TIME
    local col=frac>0.66 and 4 or frac>0.33 and 3 or 2
    circ(gpx(bl.c)+TILE//2-camX,gpy(bl.r)+TILE//2-camY,r,col)
  end
end

local function drawBombs()
  for _,b in ipairs(bombs) do
    local blink=(b.t<40 and frame%6<3)
    local col=blink and 7 or BOMB_COL
    local bx,by=gpx(b.c)+TILE//2-camX,gpy(b.r)+TILE//2-camY
    circ(bx,by,3,col)
    local fx,fy=bx+2,by-TILE//2-1
    line(bx,by-3,fx,fy,7)
    circ(fx,fy,1,(frame//2)%2==0 and 9 or 14)
  end
end

-- 8×8 pixels per frame, 6 frames: down0,down1,up0,up1,right0,right1
-- left = right flipped horizontally
-- Helmet in the player's colour around a small face: 0 transparent, 1 skin, 2 player colour,
-- 3 black eyes, 4 legs.
local SPR={
  -- [1] facing down, walk-0
  {0,2,2,2,2,2,2,0,
   2,2,2,2,2,2,2,2,
   2,2,1,1,1,1,2,2,
   2,2,3,1,1,3,2,2,
   2,2,1,1,1,1,2,2,
   0,2,2,2,2,2,2,0,
   0,0,2,2,2,2,0,0,
   0,0,4,0,0,4,0,0},
  -- [2] facing down, walk-1
  {0,2,2,2,2,2,2,0,
   2,2,2,2,2,2,2,2,
   2,2,1,1,1,1,2,2,
   2,2,3,1,1,3,2,2,
   2,2,1,1,1,1,2,2,
   0,2,2,2,2,2,2,0,
   0,2,2,2,2,2,2,0,
   0,0,0,4,4,0,0,0},
  -- [3] facing up, walk-0 (back of the helmet)
  {0,2,2,2,2,2,2,0,
   2,2,2,2,2,2,2,2,
   2,2,2,2,2,2,2,2,
   2,2,2,2,2,2,2,2,
   2,2,2,2,2,2,2,2,
   0,2,2,2,2,2,2,0,
   0,0,2,2,2,2,0,0,
   0,0,4,0,0,4,0,0},
  -- [4] facing up, walk-1
  {0,2,2,2,2,2,2,0,
   2,2,2,2,2,2,2,2,
   2,2,2,2,2,2,2,2,
   2,2,2,2,2,2,2,2,
   2,2,2,2,2,2,2,2,
   0,2,2,2,2,2,2,0,
   0,2,2,2,2,2,2,0,
   0,0,0,4,4,0,0,0},
  -- [5] facing right, walk-0 (one eye)
  {0,2,2,2,2,2,2,0,
   2,2,2,2,2,2,2,2,
   2,2,2,2,1,1,1,2,
   2,2,2,2,1,1,3,2,
   2,2,2,2,1,1,1,2,
   0,2,2,2,2,2,2,0,
   0,0,2,2,2,2,0,0,
   0,0,4,0,4,0,0,0},
  -- [6] facing right, walk-1
  {0,2,2,2,2,2,2,0,
   2,2,2,2,2,2,2,2,
   2,2,2,2,1,1,1,2,
   2,2,2,2,1,1,3,2,
   2,2,2,2,1,1,1,2,
   0,2,2,2,2,2,2,0,
   0,2,2,2,2,0,0,0,
   0,4,0,0,0,4,0,0},
}

local function drawSp(id,x,y,col,flipH)
  local sp=SPR[id]
  local skin=SKIN
  for i=0,63 do
    local c=sp[i+1]
    if c~=0 then
      local px = flipH and (x+7-(i%8)) or (x+(i%8))
      local py = y+math.floor(i/8)
      if c==1 then pix(px,py,skin)
      elseif c==2 then pix(px,py,col)
      elseif c==4 then pix(px,py,13)
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
  drawSp(id,p.x-camX,p.y-camY,p.color,flip)
end

-- Icons are 8x8 character maps, '.' transparent. None uses the red (2) of a lit bomb, so a
-- bomb on the floor is never mistaken for an extra-bomb pickup.
local ICON_COL={g=5,w=12,y=4,o=3,l=13,c=11,b=9,n=8}
local ICONS={
  X={"nnnnnnnn",
     "nyyyyyyn",
     "nynnnnyn",
     "nynnnnyn",
     "nynnnyyn",
     "nynnnnyn",
     "nynnnnyn",
     "nnnnnnnn"},
  K={"........",
     ".yyy....",
     "y...y...",
     "y...yyyy",
     "y...y.y.",
     ".yyy..y.",
     "........",
     "........"},
  E={"...ww...",
     "..wwww..",
     ".wwgwww.",
     ".wwwwww.",
     "wwwgwwww",
     ".wwwwww.",
     ".wwwww..",
     "..www..."},
  B={"......g.",
     ".y...ggg",
     "..l...g.",
     ".llll...",
     "lwllll..",
     "llllll..",
     "llllll..",
     ".llll..."},
  R={"...oo...",
     "...yy...",
     "o..yy..o",
     ".oywwyo.",
     ".oywwyo.",
     "o..yy..o",
     "...yy...",
     "...oo..."},
  S={"cccccccc",
     "cwcccccb",
     "cwccccbb",
     "ccccccbb",
     ".cccccb.",
     ".cccccb.",
     "..cccb..",
     "...cb..."},
}

-- 5x5 versions for the HUD bar (7 px high).
local HUD_ICONS={
  B={"...g.",
     ".lll.",
     "lwlll",
     "lllll",
     ".lll."},
  R={"..o..",
     ".oyo.",
     "oywyo",
     ".oyo.",
     "..o.."},
  S={"ccccb",
     "cwccb",
     "ccccb",
     ".ccb.",
     "..b.."},
}

local function drawIcon(rows,x,y)
  for j=1,#rows do
    local row=rows[j]
    for i=1,#row do
      local col=ICON_COL[row:sub(i,i)]
      if col then pix(x+i-1,y+j-1,col) end
    end
  end
end

local function drawPowerups()
  local bob=(frame//10)%2
  for _,pu in ipairs(powerups) do
    drawIcon(ICONS[pu.kind],gpx(pu.c)-camX,gpy(pu.r)-bob-camY)
  end
end

local function drawPlayers()
  for _,p in ipairs(players) do
    local blinking=p.invul>0 and frame%8<4
    local dying=p.deathT>0 and p.deathT%4<2
    if (p.alive and not blinking) or dying then
      drawPlayer(p)
      if p.alive and p.shield then circb(p.x+3-camX,p.y+3-camY,5+(frame//12)%2,ICON_COL.c) end
    end
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

-- menu items: label and what Z does (true/false: story with or without player 2)
function titleMenu()
  local saved=pmem(SAVE_SLOT)
  if saved>1 then
    return {{L("CONTINUE","DALEJ").." ("..L("STAGE","ETAP").." "..saved..")",false},{L("CONTINUE 2P","DALEJ 2P"),true},
      {L("NEW STORY","NOWA GRA"),"new"},{L("BATTLE","BITWA"),"battle"},{L("LANGUAGE: ENGLISH","JĘZYK: POLSKI"),"lang"}}
  end
  return {{L("STORY","OPOWIEŚĆ"),false},{L("STORY 2P","OPOWIEŚĆ 2P"),true},{L("BATTLE","BITWA"),"battle"},
    {L("LANGUAGE: ENGLISH","JĘZYK: POLSKI"),"lang"}}
end
menuSel=1
TITLE_IDLE=900  -- frames on the menu before the battle demo starts
local LOGO,LOGO_X,LOGO_Y="BLASTIC",57,22

-- print returns the width of the text; drawn off-screen, it only measures
function textW(s,scale) return print(s,0,-20,0,false,scale,true) or 0 end

-- the logo letter by letter, so the intro can drop each one in; dy(i) lifts letter i
local function drawLogo(dy)
  for i=1,#LOGO do
    local x,y=LOGO_X+(i-1)*18,LOGO_Y+(dy and dy(i) or 0)
    print(LOGO:sub(i,i),x+2,y+2,2,true,3)
    print(LOGO:sub(i,i),x,y,4,true,3)
  end
end

-- the stars twinkle slowly: one in nine is dim at a time
local function nightSky(t,cx)
  cls(0)
  for i=1,40 do pix((i*53-(cx or 0)//4)%240,(i*29)%90,(i+t//40)%9==0 and 14 or 13) end
  circ(204,30,9,12) circ(209,27,8,0)
end

local function castle(x,y,c,lit)
  rect(x,y+20,80,40,c) rect(x-10,y,18,60,c) rect(x+72,y,18,60,c) rect(x+30,y-10,20,30,c)
  for i=0,5 do rect(x+i*14,y+16,8,4,c) end
  for i=0,1 do rect(x-10+i*82,y-4,4,4,c) rect(x+4+i*82,y-4,4,4,c) end
  if lit then for i=0,2 do rect(x+8+i*28,y+30,4,6,lit) end rect(x+38,y,4,6,lit) end
end

local function drawTitle()
  titleTimer=titleTimer+1
  if titleTimer==1 then initPalette() initFont() startMusic() end
  local t=titleTimer
  nightSky(t)
  castle(80,104,15,4)
  rect(0,126,240,10,15)
  drawLogo()
  local sub=L("THE SULPHUR LEGEND","LEGENDA O SIARCE")
  print(sub,120-textW(sub,1)//2,48,13,false,1,true)

  local menu=titleMenu()
  for i,item in ipairs(menu) do
    local label=item[1]
    local y=56+i*11
    local w=textW(label,1)
    local x=120-w//2
    if i==menuSel then
      rect(x-14,y-3,w+20,11,0) rectb(x-14,y-3,w+20,11,4)
      circ(x-7,y+2,3,15) pix(x-5,y-2,t%10<5 and 4 or 3)
    end
    print(label,x,y,i==menuSel and 12 or 14,false,1,true)
  end
  local keys=L("P1: ARROWS + Z     P2: WASD + TAB","P1: STRZAŁKI + Z     P2: WASD + TAB")
  print(keys,120-textW(keys,1)//2,128,14,false,1,true)

  if btnp(0) or btnp(1) then
    menuSel=(menuSel+(btnp(0) and -2 or 0))%#menu+1
    titleTimer=2
  end
  if btnp(4) or btnp(12) then
    local act=menu[menuSel][2]
    if act=="battle" then state="game" init()
    elseif act=="new" then pmem(SAVE_SLOT,0) menuSel=1
    elseif act=="lang" then LANG=LANG=="pl" and "en" or "pl" pmem(LANG_SLOT,LANG=="pl" and 1 or 0)
    else startCampaign(act) end
  elseif titleTimer>TITLE_IDLE then
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
-- 5x5 head for the HUD: 2 player colour (grey once dead), 1 skin, 3 eyes
local HUD_HEAD={".222.","22222","23132","22222",".222."}

local function drawHead(x,y,col)
  for j,row in ipairs(HUD_HEAD) do
    for i=1,5 do
      local k=row:sub(i,i)
      if k=="2" then pix(x+i-1,y+j-1,col)
      elseif k=="1" then pix(x+i-1,y+j-1,SKIN)
      elseif k=="3" then pix(x+i-1,y+j-1,0) end
    end
  end
end

-- four player segments of 56 px around a 16 px zone countdown in the middle
local HUD_X={2,58,128,184}

-- a player's head (crossed out once dead) and, from x+gap, bombs, range and shield
function drawPlayerStats(p,x,gap)
  local col=p.alive and p.color or 13
  local txt=p.alive and 12 or 13
  drawHead(x,1,col)
  if not p.alive then
    line(x,1,x+4,5,BOMB_COL)
    line(x+4,1,x,5,BOMB_COL)
  end
  x=x+gap
  drawIcon(HUD_ICONS.B,x,1)
  print(p.stats.bombs,x+6,1,txt,false,1,true)
  drawIcon(HUD_ICONS.R,x+10,1)
  print(p.stats.len,x+16,1,txt,false,1,true)
  if p.shield then drawIcon(HUD_ICONS.S,x+21,1) end
end

local function drawHUD()
  rect(0,0,W*TILE,7,0)
  for i,p in ipairs(players) do
    local x=HUD_X[i]
    drawPlayerStats(p,x,25)
    print(p.human and "P" or "C",x+6,1,p.alive and p.color or 13,false,1,true)
    for k=1,MATCH_WINS do
      if score[i]>=k then rect(x+8+k*4,2,3,3,4) else rectb(x+8+k*4,2,3,3,13) end
    end
  end
  local left=shrinkAt-roundFrames
  local warning=left<=SHRINK_WARN
  if left>0 and not (warning and frame%20<10) then
    local secs=tostring(left//60+1)
    print(secs,120-#secs*2,1,warning and WARN_COL or 12,false,1,true)
  end
end

-- ── campaign: "The Sulphur Legend" ───────────────────────────────────────────
-- Kuba, a Wroclaw shoemaker with sulphur bombs, goes after the dragon of Krakow and finds
-- the devil behind it; from chapter 2 Princess Wanda fights along (P2 in Story 2P, a bot
-- ally otherwise).

BOSS_HP={utopek=3,jaga=3,dragon=4,devil=6}
local CH_BOSS={"utopek","jaga","dragon","devil"}
local GOAL_CYCLE={"exit","enemies","keys","survive"}
local SCROLLS={"h","v",false}
STAGE_COUNT,CHAPTER_LEN=100,25

-- stage n: chapter, goal, crate density, dwarves, bats, skeletons, boss, scroll ("h" wide,
-- "v" tall), boss hp. Every 5th stage is a boss fight: earlier bosses come back in between,
-- the chapter's own boss ends it. Monsters grow with n; bats from chapter 2, skeletons from 3.
function stageDef(n)
  local ch,i=(n-1)//CHAPTER_LEN+1,(n-1)%CHAPTER_LEN+1
  local boss=i%5==0 and (i==CHAPTER_LEN and CH_BOSS[ch] or CH_BOSS[(i//5-1)%math.min(ch,3)+1])
  local foes=not boss
  return {ch,boss and "boss" or GOAL_CYCLE[(n-1)%4+1],0.3+0.05*(n%3),
    foes and math.min(6,2+n//15) or 0,
    foes and ch>=2 and math.min(5,1+(n-26)//15) or 0,
    foes and ch>=3 and math.min(3,1+(n-51)//25) or 0,
    boss,SCROLLS[n%3+1],boss and BOSS_HP[boss]+ch-1}
end

STAGES={}
for n=1,STAGE_COUNT do STAGES[n]=stageDef(n) end
CHAPTERS={{"WROCLAW","WROCŁAW"},{"MOUNT SLEZA","ŚLĘŻA"},{"KRAKOW","KRAKÓW"},{"THE DEVIL'S CELLARS","PIEKIELNE LOCHY"}}
function chapterName(n) return L(CHAPTERS[n][1],CHAPTERS[n][2]) end
local GOALS={exit={"FIND THE EXIT","ZNAJDŹ WYJŚCIE"},enemies={"DEFEAT ALL MONSTERS","POKONAJ POTWORY"},
  keys={"FIND 3 KEYS","ZNAJDŹ 3 KLUCZE"},survive={"SURVIVE THE WALLS","PRZETRWAJ MURY"},boss={"DEFEAT THE BOSS","POKONAJ BOSSA"}}
local SKELETON_COL=13
SAVE_SLOT=0
SURVIVE_STEPS=5  -- a survive stage ends after this many zone steps, with room still left

mode="pvp"
camX,camY=0,0
monsters={}
boss=nil
hidden={}
camp={}

local function stageSize(scroll)
  if scroll=="h" then return 62,18 elseif scroll=="v" then return 32,34 end
  return 32,18
end

local function heroAt(c,r)
  for _,p in ipairs(players) do
    if p.alive and p.team==1 and p.c==c and p.r==r then return p end
  end
  return nil
end

local function aldric() return players[1] end

-- random cells passing ok, as far from the heroes' corner as `minDist`
local function farCells(ok,minDist)
  local out={}
  for r=1,H-2 do for c=1,W-2 do
    if ok(c,r) and math.abs(c-STARTS[1][1])+math.abs(r-STARTS[1][2])>=minDist then out[#out+1]={c,r} end
  end end
  for i=#out,2,-1 do local j=math.random(i) out[i],out[j]=out[j],out[i] end
  return out
end

-- items the goal needs, under crates when there are enough of them, else on the floor
local function hideItems(kind,n)
  local crates=farCells(function(c,r) return mget(c,r)==T_BLOCK end,(W+H)//4)
  local floor=farCells(function(c,r) return mget(c,r)==T_EMPTY end,(W+H)//4)
  for i=1,n do
    local cell=table.remove(crates)
    if cell then hidden[cell[1]*100+cell[2]]=kind
    else cell=table.remove(floor) powerups[#powerups+1]={c=cell[1],r=cell[2],kind=kind} end
  end
end

local function spawnMonster(kind,c,r)
  monsters[#monsters+1]={kind=kind,c=c,r=r,x=gpx(c),y=gpy(r),d={0,0}}
end

function startStage(n)
  local st=STAGES[n]
  camp.stage,camp.keys,camp.done=n,0,false
  math.randomseed(n*7919+camp.tries)
  setArena(stageSize(st[8]))
  blockDensity=st[3]
  bombs,blasts,powerups,monsters,hidden,boss={},{},{},{},{},nil
  initMap()
  players={}
  local function hero(id,c,r)
    local p=newPlayer(id,c,r)
    p.team,p.human=1,id==1 or camp.coop
    p.stats={bombs=camp.stats[id].bombs,len=camp.stats[id].len}
    players[#players+1]=p
  end
  hero(1,STARTS[1][1],STARTS[1][2])
  if st[1]>=2 then hero(2,STARTS[1][1],STARTS[1][2]+1) end
  local far={STARTS[4],STARTS[st[8]=="v" and 3 or 2]}
  for i=1,st[6] do
    local p=newPlayer(2+i,far[i][1],far[i][2])
    p.team,p.human,p.color=2,false,SKELETON_COL
    players[#players+1]=p
  end
  local free=farCells(function(c,r) return mget(c,r)==T_EMPTY end,8)
  for _=1,st[4] do local cell=table.remove(free) if cell then spawnMonster("g",cell[1],cell[2]) end end
  for _=1,st[5] do local cell=table.remove(free) if cell then spawnMonster("b",cell[1],cell[2]) end end
  if st[2]=="exit" then hideItems("X",1) elseif st[2]=="keys" then hideItems("K",3) end
  if st[7] then
    local c,r=W//2-1,H//2-1
    for dc=0,1 do for dr=0,1 do mset(c+dc,r+dr,T_EMPTY) end end
    boss={kind=st[7],c=c,r=r,x=gpx(c),y=gpy(r),hp=st[9],max=st[9],t=0,inv=0}
    if st[7]=="dragon" then hideItems("E",1) end
  end
  resetShrink()
  -- survive: the walls start after 10 s and step on as soon as the 5 s blink is over
  if st[2]=="survive" then shrinkAt,zoneCycle=600,SHRINK_WARN else shrinkAt=math.huge end
  frame,state,restartTimer=0,"game",0
end

local function chapterStart(n)
  return n==1 or STAGES[n][1]~=STAGES[n-1][1]
end

function startCampaign(coop)
  mode="camp"
  local saved=pmem(SAVE_SLOT)
  camp={coop=coop,lives=3,tries=0,friend=false,stage=(saved>=1 and saved<=#STAGES) and saved or 1,
    stats={{bombs=MAX_BOMBS,len=BLAST_LEN},{bombs=MAX_BOMBS,len=BLAST_LEN}}}
  beginChapterOrMap(camp.stage)
end

function beginChapterOrMap(n)
  camp.stage=n
  pmem(SAVE_SLOT,n)
  if chapterStart(n) then
    camp.stats={{bombs=MAX_BOMBS,len=BLAST_LEN},{bombs=MAX_BOMBS,len=BLAST_LEN}}
    playScene(SCENE_OF_CHAPTER[STAGES[n][1]],function() showMap(n) end)
  else
    showMap(n)
  end
end

-- ── monsters ──────────────────────────────────────────────────────────────────

local MONSTER_PERIOD={g=3,b=2}

local function updateMonsters()
  for i=#monsters,1,-1 do
    local m=monsters[i]
    if isBlast(m.c,m.r) then
      table.remove(monsters,i)
    elseif frame%MONSTER_PERIOD[m.kind]==0 then
      if m.x==gpx(m.c) and m.y==gpy(m.r) then
        if m.kind=="b" then
          local path=botPath(m.c,m.r,botPassable,heroAt)
          m.d=path and {path[1].c-m.c,path[1].r-m.r} or {0,0}
        elseif math.random()<0.15 or not botPassable(m.c+m.d[1],m.r+m.d[2]) then
          m.d=BOT_DIRS[math.random(4)]
        end
        if not botPassable(m.c+m.d[1],m.r+m.d[2]) then m.d={0,0} end
      end
      m.x,m.y=m.x+m.d[1],m.y+m.d[2]
      m.c,m.r=gcol(m.x+TILE//2),grow(m.y+TILE//2)
    end
  end
end

-- ── bosses ────────────────────────────────────────────────────────────────────

local function bossCovers(b,c,r)
  return c>=b.c and c<=b.c+1 and r>=b.r and r<=b.r+1
end

local function bossFree(c,r)
  for dc=0,1 do for dr=0,1 do
    if not botPassable(c+dc,r+dr) or heroAt(c+dc,r+dr) then return false end
  end end
  return true
end

local function bossTeleport(b)
  local spots=farCells(function(c,r) return bossFree(c,r) end,0)
  local a=aldric()
  for _,s in ipairs(spots) do
    if math.abs(s[1]-a.c)+math.abs(s[2]-a.r)>=6 then
      b.c,b.r,b.x,b.y=s[1],s[2],gpx(s[1]),gpy(s[2])
      return
    end
  end
end

-- the dragon's breath: a row (or column) through a hero, warned a second before it burns
local function bossFire(b)
  if not b.warn then
    local a=aldric()
    b.warn={row=math.random()<0.5,c=a.c,r=a.r,t=60}
  else
    b.warn.t=b.warn.t-1
    if b.warn.t<=0 then
      for k=1,(b.warn.row and W or H)-2 do
        local c,r=b.warn.row and k or b.warn.c,b.warn.row and b.warn.r or k
        if mget(c,r)==T_EMPTY and not bossCovers(b,c,r) then addBlast(c,r,BOSS_FIRE) end
      end
      b.warn=nil
    end
  end
end

local function updateBoss()
  local b=boss
  if not b or b.hp<=0 then return end
  b.t=b.t+1
  if b.inv>0 then b.inv=b.inv-1 end
  for dc=0,1 do for dr=0,1 do
    for _,bl in ipairs(blasts) do
      if b.inv==0 and bl.owner~=BOSS_FIRE and bl.c==b.c+dc and bl.r==b.r+dr then
        b.hp,b.inv=b.hp-1,60
        sndShield()
      end
    end
  end end
  local kind=b.kind
  if kind=="devil" then kind=b.hp>4 and "jaga" or b.hp>2 and "summon" or "dragon" end
  if kind=="utopek" and b.t%3==0 then
    local a=aldric()
    if b.x==gpx(b.c) and b.y==gpy(b.r) then
      b.d={0,0}
      for _,d in ipairs(BOT_DIRS) do
        local nc,nr=b.c+d[1],b.r+d[2]
        if bossFree(nc,nr) and math.abs(nc-a.c)+math.abs(nr-a.r)<math.abs(b.c-a.c)+math.abs(b.r-a.r) then b.d=d end
      end
    end
    b.x,b.y=b.x+b.d[1],b.y+b.d[2]
    b.c,b.r=gcol(b.x+TILE//2),grow(b.y+TILE//2)
  elseif (kind=="jaga" or kind=="summon") and b.t%150==0 then
    if kind=="summon" then spawnMonster("g",b.c,b.r) end
    bossTeleport(b)
    if kind=="jaga" then bombs[#bombs+1]={c=b.c,r=b.r,t=BOMB_TIMER,len=3,owner=BOSS_FIRE} end
  elseif kind=="dragon" and (b.warn or b.t%120==0) then
    bossFire(b)
  end
end

-- ── campaign rules ────────────────────────────────────────────────────────────

local function stageGoalMet()
  local goal=STAGES[camp.stage][2]
  if goal=="exit" then return camp.done
  elseif goal=="keys" then return camp.keys>=3
  elseif goal=="survive" then return zoneSteps>=SURVIVE_STEPS
  elseif goal=="boss" then return boss.hp<=0 or camp.friend end
  for _,p in ipairs(players) do if p.alive and p.team==2 then return false end end
  return #monsters==0
end

-- camera follows the heroes along the stage's one scrolling axis
local function updateCamera()
  local x,y,n=0,0,0
  for _,p in ipairs(players) do
    if p.team==1 and p.alive then x,y,n=x+p.x,y+p.y,n+1 end
  end
  if n==0 then return end
  camX=math.max(0,math.min((W-2)*TILE-240,x//n-116))
  camY=math.max(0,math.min((H-2)*TILE-128,y//n-60))
end

function updateCampaign()
  updateMonsters()
  updateBoss()
  local heroes=0
  for _,p in ipairs(players) do
    if p.alive and p.team==1 then
      collectPowerup(p)  -- an item can appear under a hero who stands still
      for _,m in ipairs(monsters) do if m.c==p.c and m.r==p.r then blastHit(p) end end
      if boss and boss.hp>0 and not camp.friend and bossCovers(boss,p.c,p.r) then blastHit(p) end
      if p.alive then heroes=heroes+1 end
    end
  end
  updateCamera()
  if heroes==0 then
    camp.lives=camp.lives-1
    state,restartTimer=camp.lives>0 and "lost" or "gameover",150
  elseif stageGoalMet() then
    for _,p in ipairs(players) do
      if p.team==1 then camp.stats[p.id]={bombs=p.stats.bombs,len=p.stats.len} end
    end
    state,restartTimer="clear",120
  end
end

-- after a stage: next stage, a chapter scene, or the ending
function campaignNext()
  if state=="clear" then
    camp.tries=0
    if camp.stage==#STAGES then
      pmem(SAVE_SLOT,0)
      playScene("ending",function() mode="pvp" state="title" titleTimer=2 end)
    else
      beginChapterOrMap(camp.stage+1)
    end
  elseif state=="lost" then
    camp.tries=camp.tries+1
    startStage(camp.stage)
  else
    mode,state,titleTimer="pvp","title",2
  end
end

-- ── campaign drawing ──────────────────────────────────────────────────────────

-- 8x8 art, one character per pixel: '.' transparent, other letters index ART_COL
local ART_COL={g=5,k=0,w=12,d=15,r=2,y=4,s=10,t=7,p=9,o=3,c=13}
local ART={
  g={"...rr...","..rrrr..",".rrrrrr.","..skks..","..ssss..",".wwwwww.",".pwwwwp.","..d..d.."},
  b={"d......d","dd.dd.dd","ddddddd.",".drddrd.","..dddd..","...dd...","........","........"},
  utopek={"..tttt..",".tttttt.","tggggggt","gwkggwkg","gggggggg","g.kkkk.g",".gggggg.","t.g..g.t"},
  jaga={"..rrrr..",".rrrrrr.","rrssssrr",".skssks.",".sssoss.",".csssc..",".dddddd.","dddddddd"},
  dragon={"r......r","rr.rr.rr","rrrrrrrr","rwkrrwkr","rrrrrrrr","ryyyyyyr",".rr..rr.","rr....rr"},
  heart={"........",".rr.rr..","rrrrrrr.","rrrrrrr.",".rrrrr..","..rrr...","...r....","........"},
  devil={"k......k",".krrrrk.","rrrrrrrr","ryrrrryr","rrrrrrrr","kkkrrkkk",".rrrrrr.","r.dddd.r"},
}

function drawArt(name,x,y,scale,flash)
  local rows=ART[name]
  for j=1,8 do
    local row=rows[j]
    for i=1,8 do
      local col=ART_COL[row:sub(i,i)]
      if col then rect(x+(i-1)*scale,y+(j-1)*scale,scale,scale,flash and 12 or col) end
    end
  end
end

local function drawMonsters()
  for _,m in ipairs(monsters) do drawArt(m.kind,m.x-camX,m.y-camY,1) end
end

local function drawBoss()
  local b=boss
  if not b or b.hp<=0 or camp.friend then return end
  if b.warn and frame%8<4 then
    for k=1,(b.warn.row and W or H)-2 do
      local c,r=b.warn.row and k or b.warn.c,b.warn.row and b.warn.r or k
      rectb(gpx(c)-camX,gpy(r)-camY,TILE,TILE,BOMB_COL)
    end
  end
  drawArt(b.kind,b.x-camX,b.y-camY,2,b.inv>0 and frame%6<3)
end

local function drawCampaignHUD()
  rect(0,0,240,7,0)
  for k=1,camp.lives do drawArt("heart",2+(k-1)*7,0,1) end
  print(STAGES[camp.stage][1].."-"..((camp.stage-1)%CHAPTER_LEN+1),24,1,12,false,1,true)
  local x=44
  for _,p in ipairs(players) do
    if p.team==1 then
      drawPlayerStats(p,x,7)
      x=x+40
    end
  end
  local goal,txt=STAGES[camp.stage][2],nil
  if goal=="keys" then txt=L("KEYS ","KLUCZE ")..camp.keys.."/3"
  elseif goal=="enemies" then
    local n=#monsters
    for _,p in ipairs(players) do if p.alive and p.team==2 then n=n+1 end end
    txt=L("LEFT ","ZOSTAŁO ")..n
  elseif goal=="survive" then txt=L("HOLD ON ","WYTRWAJ ")..math.max(0,SURVIVE_STEPS-zoneSteps)
  elseif goal=="exit" then txt=L("FIND EXIT","SZUKAJ WYJŚCIA") end
  if txt then print(txt,238-#txt*4,1,12,false,1,true) end
  if goal=="boss" and boss then
    rect(160,2,74,3,15)
    rect(160,2,74*math.max(0,boss.hp)//boss.max,3,BOMB_COL)
  end
end

function drawCampaign()
  -- crates hiding a quest item sparkle now and then, so the search is no lottery
  if frame%50<6 then
    for k in pairs(hidden) do
      local c,r=k//100,k%100
      if mget(c,r)==T_BLOCK then
        local x,y=gpx(c)-camX+5,gpy(r)-camY+2
        line(x-1,y,x+1,y,12) line(x,y-1,x,y+1,12)
      end
    end
  end
  drawMonsters()
  drawBoss()
  drawCampaignHUD()
  local msg=state=="clear" and L("STAGE CLEAR!","ETAP ZALICZONY!") or state=="lost" and L("OUCH!","AUĆ!")
    or state=="gameover" and L("GAME OVER","KONIEC GRY")
  if msg then
    if state=="clear" then
      for k=1,40 do
        pix((k*53+frame*(k%3+1))%240,(k*29+frame*(k%4+1))%136,k%15+1)
      end
    end
    print(msg,120-textW(msg,2)//2,52+(state=="clear" and math.floor(math.sin(frame/6)*3) or 0),12,false,2,true)
    if state=="lost" then print(L("LIVES LEFT: ","ŻYCIA: ")..camp.lives,90,72,13,false,1,true) end
    restartTimer=restartTimer-1
    if restartTimer<=0 or (restartTimer<90 and btnp(4)) then campaignNext() end
  end
end

-- story:begin (make_tic.py moves this section into the cart's MUSIC PATTERNS data and loads
-- it from there, so the scenes do not count against the code limit; it may use only globals)
-- ── scenes ────────────────────────────────────────────────────────────────────
-- A scene is a film: shots with their own backdrop, camera pan, actors and lines, cut with a
-- fade. Backdrops are painted by tools/scenes/paint.py; the cast is drawn from shapes, larger
-- than the game sprites, in colours the backdrops leave alone (all but 1, 5, 7 and 11).

local sin,cos=math.sin,math.cos

-- scenes.bin sits in MAP RAM; a shot's backdrop is unpacked into MUSIC PATTERNS RAM (the
-- tracker plays PCM, so TIC-80's own music never reads it) and copied to the screen each frame
local ART_RAM,BACKDROP_RAM,BACKDROP_BYTES=0x08000,0x11164,11520
local BACKDROPS={"rynek","workshop","road","sleza","wawel","hall","cellars","night"}
local BAR=20  -- letterbox bar height; the backdrop fills the 96 rows between the bars
SUB_Y=127     -- the line being typed, in the bottom bar

-- fading works on the palette: TIC-80 has no transparency to darken a frame with
local palBase,palShot,sky,fadeK
local function fadePal(k)
  fadeK=k
  for i=0,47 do poke(0x03FC0+i,palShot[i]*k//1) end
end

local function rgbAt(p) return {peek(p),peek(p+1),peek(p+2)} end

-- unpacks backdrop name, sets its three colours and sky; false when the cart has no art
local function loadBackdrop(name)
  palShot,sky={},nil
  for i=0,47 do palShot[i]=palBase[i] end
  local k
  for i,n in ipairs(BACKDROPS) do if n==name then k=i end end
  if not k or peek(ART_RAM)<k then return false end
  local e=ART_RAM+1+(k-1)*20
  for i,c in ipairs{1,5,7} do
    for j=0,2 do palShot[c*3+j]=peek(e+2+(i-1)*3+j) end
  end
  sky={rgbAt(e+11),rgbAt(e+14),rgbAt(e+17)}
  -- byte RLE: c<128 copies the next c+1 bytes, c>=128 repeats the next byte c-126 times
  local src,dst=ART_RAM+(peek(e)|peek(e+1)<<8),BACKDROP_RAM
  while dst<BACKDROP_RAM+BACKDROP_BYTES do
    local c=peek(src)
    if c<128 then memcpy(dst,src+1,c+1) src,dst=src+c+2,dst+c+1
    else memset(dst,peek(src+1),c-126) src,dst=src+2,dst+c-126 end
  end
  return true
end

-- the sky colour (11) changes on every scanline, like the Amiga copper
function BDR(row)
  local y=row-4-BAR
  if not sky or y<0 or y>95 then return end
  local k=y/95*2
  local i=math.min(1,k//1)
  local a,b,f=sky[i+1],sky[i+2],k-i
  for c=1,3 do poke(0x03FC0+32+c,(a[c]+(b[c]-a[c])*f)*fadeK//1) end
end

-- figure units: feet at (x,y), about 25 units tall, s pixels per unit, mirrored when left
local function fig(who,x,y,s,t,left,walk,fire)
  local m=left and -1 or 1
  local function R(dx,dy,w,h,c) if left then dx=-dx-w end rect(x+dx*s,y+dy*s,w*s,h*s,c) end
  local function C(dx,dy,r,c) circ(x+dx*m*s,y+dy*s,r*s,c) end
  local function T(a,b,c,d,e,f,col) tri(x+a*m*s,y+b*s,x+c*m*s,y+d*s,x+e*m*s,y+f*s,col) end
  local step=walk and t//6%2*2-1 or 0
  local function face(c)
    C(0,-17,4,c)
    R(1,-18,1,1,0) R(3,-18,1,1,0)
  end
  if who=="dratewka" then
    R(-3+step,-5,2,5,14) R(1-step,-5,2,5,14) R(-3+step,-1,2,1,0) R(1-step,-1,2,1,0)
    R(-4,-13,8,8,12) R(-3,-11,6,7,8)
    face(SKIN)
    R(-4,-19,2,3,8) R(-4,-22,8,3,2) R(2,-20,4,1,2)
    C(7,-9,3,12) C(9,-11,2,12) R(10,-11,2,2,0) R(6,-14,1,2,13)
    if t%8<4 then R(6,-15,1,1,4) end
  elseif who=="wanda" then
    R(-5,-19,4,13,4)
    T(-6,0,6,0,0,-12,2) R(-2,-13,4,4,12)
    face(SKIN)
    R(-4,-21,8,2,4) R(-4,-22,8,1,6) R(-3,-23,1,1,2) R(0,-23,1,1,9) R(3,-23,1,1,12)
  elseif who=="krak" then
    T(-7,0,7,0,0,-14,2) R(-7,-1,14,1,12) R(-1,-12,2,11,12)
    face(SKIN)
    T(-3,-15,3,-15,0,-9,12)
    R(-3,-23,7,2,4) R(-3,-24,1,1,4) R(0,-25,1,2,4) R(3,-24,1,1,4)
  elseif who=="twardowski" then
    T(-6,0,6,0,0,-14,9) R(-1,-13,2,13,2) R(-4,-8,8,2,4)
    face(SKIN)
    R(-2,-15,7,1,0)
    R(-4,-25,8,5,8) R(-3,-26,6,1,2) R(3,-29,1,4,12)
  elseif who=="devil" then
    T(-7,0,7,0,0,-15,2) T(-6,0,6,0,0,-14,0)
    R(-9,-4,3,1,2) R(-9,-8,1,4,2) T(-10,-8,-8,-8,-9,-10,2)
    C(0,-17,4,2) R(1,-18,1,1,4) R(3,-18,1,1,4) R(-1,-15,7,1,0)
    T(-3,-20,-1,-20,-4,-25,0) T(1,-20,3,-20,4,-25,0)
  elseif who=="jaga" then
    R(-6,-16,1,16,8) T(-8,0,-4,0,-6,-5,4)
    T(-6,0,6,0,0,-12,14)
    C(0,-15,5,2) C(1,-14,4,SKIN) R(4,-14,2,1,3) R(2,-15,1,1,0) R(-2,-12,5,1,13)
  elseif who=="dwarf" then
    R(-2,-2,1,2,0) R(1,-2,1,2,0) R(-3,-6,6,4,9)
    C(0,-10,3,SKIN) T(-3,-9,3,-9,0,-4,12) R(1,-11,1,1,0)
    T(-4,-12,4,-12,0,-20,2)
  elseif who=="rooster" then
    T(-4,-8,-13,-20,-6,-4,6) T(-4,-8,-11,-15,-4,-4,0)
    C(0,-8,5,3) C(4,-14,3,3) R(3,-18,3,2,2) R(6,-13,1,2,2) T(7,-15,10,-14,7,-13,4)
    R(5,-15,1,1,0) R(-1,-3,1,3,4) R(1,-3,1,3,4)
  elseif who=="dragon" then
    local flap=sin(t/6)*6
    T(-6,-9,-6,-4,-22,-3,2)
    T(-7,-13,-6,-36+flap,14,-13,0) T(-5,-14,-5,-32+flap,10,-14,2)
    C(0,-10,9,2) C(2,-8,5,3)
    R(-6,-3,3,3,2) R(3,-3,3,3,2)
    T(4,-16,9,-16,10,-26,2) C(11,-26,5,2) R(13,-27,7,4,2)
    R(11,-29,2,2,4) R(12,-29,1,2,0) T(8,-30,10,-31,6,-36,13)
    if fire then T(20,-26,44,-34,44,-18,3) T(20,-26,36,-29,36,-23,4) end
  end
end

-- what moves on a backdrop: sparks of the bonfire, embers, the candle, the river, stars
local function rising(t,n,x,y,w,h,c1,c2)
  for k=0,n do
    local p=(t+k*23)%h
    pix(x+(k*41)%w+sin(t/15+k)*3,y-p,p<h//2 and c1 or c2)
  end
end
local OVERLAYS={
  sleza=function(t) rising(t,10,118,44,12,30,4,2) rising(t,5,0,100,240,50,4,6) end,
  cellars=function(t) rising(t,24,0,116,240,90,4,2) end,
  workshop=function(t) rect(89,70+t//5%2,2,4,t//3%2==0 and 4 or 3) end,
  wawel=function(t) for k=0,14 do pix((k*53+t//4)%240,106+k%4*3,t//8%2==k%2 and 12 or 4) end end,
  night=function(t) for k=0,6 do pix((k*67)%240,24+(k*29)%40,(t//20+k)%3==0 and 12 or 13) end end,
}

-- fireworks over the castle at the end: bursts of bombs, each on its own clock
local function fireworks(t)
  for k=0,4 do
    local p=(t+k*29)%80
    local n=(t+k*29)//80
    local x,y=(k*67+n*41)%180+30,36+(k*31+n*17)%36
    if p<10 then pix(x,y+40-p*4,13)
    elseif p<50 then
      for j=0,11 do
        local a,r=j*0.5236,(p-10)*0.7
        circ(x+cos(a)*r,y+sin(a)*r+(p-10)^2/120,1,(p<44) and (k%4)+2 or 14)
      end
    end
  end
end

-- actors: {who, x0,y0, x1,y1, t0,t1, scale=2, faces left (default: walks left)}; standing
-- feet at y=108, close-ups at scale 4 with feet at y=126 under the bar
-- shots: bd (backdrop), pan (camera travel in px), len (frames without lines), cap (place,
-- top bar), title (big caption), fx: flash | shake | fire (dragon breath) | fireworks;
-- lines start once every actor stands still
local function closeUp(who,x,left) return {{who,x,126,x,126,0,0,4,left}} end
local SPEAKER_PL={DEVIL="DIABEŁ",DRAGON="SMOK",DWARF="KRASNAL"}
SCENES={
  wroclaw={
    {bd="rynek",len=170,cap={"WROCLAW, THE MARKET SQUARE","WROCŁAW, RYNEK"},
      act={{"dwarf",30,108,30,108,0,0},{"dwarf",206,108,206,108,0,0,2,true}}},
    {bd="rynek",act={{"dwarf",-20,108,96,108,0,70,3}},
      say={{"DWARF","News from Krakow! A dragon eats the sheep!","Wieści z Krakowa! Smok pożera owce!"},
        {"DWARF","King Krak gives half his kingdom to a hero!","Król Krak da pół królestwa bohaterowi!"}}},
    {bd="workshop",act=closeUp("dratewka",110),
      say={{"DRATEWKA","Half a kingdom for one dragon?","Pół królestwa za jednego smoka?"},
        {"DRATEWKA","Wool, sulphur, a bit of love...","Wełna, siarka, odrobina serca..."}}},
    {bd="workshop",fx="flash",act=closeUp("dratewka",110),
      say={{"DRATEWKA","...and less sulphur next time.","...i następnym razem mniej siarki."}}},
    {bd="night",act={{"rooster",-40,70,280,44,0,170,1},{"twardowski",-38,62,282,36,0,170,1},{"dratewka",60,108,60,108,0,0}},
      say={{"DRATEWKA","Master Twardowski on his rooster.","Mistrz Twardowski na swoim kogucie."},
        {"DRATEWKA","Where he flies, trouble follows.","Gdzie on leci, tam kłopoty."}}},
    {bd="rynek",len=150,act={{"dratewka",-10,108,250,108,0,150}}},
    {bd="black",len=120,title=1},
  },
  sleza={
    {bd="road",len=170,cap={"THE ROAD SOUTH","DROGA NA POŁUDNIE"},act={{"dratewka",-10,108,120,108,0,170,1}}},
    {bd="sleza",len=150,cap={"MOUNT SLEZA, KUPALA NIGHT","ŚLĘŻA, NOC KUPAŁY"}},
    {bd="sleza",act={{"wanda",150,108,150,108,0,0,2,true},{"dratewka",-20,108,90,108,0,70}},
      say={{"DRATEWKA","A princess? On a mountain? At night?","Królewna? Na górze? W nocy?"},
        {"WANDA","I ran away. Father wants to marry me to a hero.","Uciekłam. Ojciec chce mnie wydać za bohatera."}}},
    {bd="sleza",act=closeUp("wanda",120,true),
      say={{"WANDA","Don't get any ideas, shoemaker.","Nawet o tym nie myśl, szewczyku."}}},
    {bd="sleza",fx="flash",act=closeUp("jaga",130,true),
      say={{"BABA JAGA","Twardowski sends his regards!","Pozdrowienia od Twardowskiego!"}}},
    {bd="sleza",act=closeUp("dratewka",110),say={{"DRATEWKA","Twardowski. I knew it.","Twardowski. Wiedziałem."}}},
    {bd="black",len=120,title=2},
  },
  krakow={
    {bd="wawel",len=170,cap={"KRAKOW, WAWEL HILL","KRAKÓW, WZGÓRZE WAWELSKIE"},act={{"dragon",-80,80,320,50,0,170,1}}},
    {bd="wawel",act={{"dratewka",40,108,40,108,0,0},{"wanda",70,108,70,108,0,0},{"dragon",190,110,190,110,0,0,2,true}},
      say={{"DRATEWKA","Here, dragon! Have a sheep!","Masz, smoku! Zjedz owieczkę!"}}},
    {bd="wawel",fx="fire",act={{"dragon",70,118,70,118,0,0,2}},
      say={{"DRAGON","*burp* Spicy. Who sent you?","*bek* Ostre. Kto was przysłał?"},
        {"DRAGON","A gentleman with a tail took my egg.","Pan z ogonem ukradł mi jajo."}}},
    {bd="wawel",act=closeUp("wanda",120,true),
      say={{"WANDA","A gentleman with a tail... the devil!","Pan z ogonem... diabeł!"}}},
    {bd="night",fx="flash",act=closeUp("twardowski",120,true),
      say={{"TWARDOWSKI","Yes. He holds my pact.","Tak. Ma mój cyrograf."},
        {"TWARDOWSKI","He makes me send the dragon. Burn the pact!","Każe mi nasyłać smoka. Spalcie cyrograf!"}}},
    {bd="black",len=120,title=3},
  },
  cellars={
    {bd="cellars",len=170,cap={"THE DEVIL'S CELLARS","PIEKIELNE LOCHY"}},
    {bd="cellars",fx="flash",act=closeUp("devil",120,true),
      say={{"DEVIL","A shoemaker? Against me?","Szewczyk? Przeciwko mnie?"},
        {"DEVIL","I own Twardowski. Soon I own Krakow.","Mam Twardowskiego. Wkrótce będę miał Kraków."}}},
    {bd="cellars",act=closeUp("dratewka",110),say={{"DRATEWKA","I brought sheep.","Przyniosłem owce."}}},
    {bd="cellars",act={{"dratewka",-20,108,70,108,0,60},{"wanda",-50,108,40,108,0,60},{"twardowski",130,108,130,108,0,0,2,true}},
      say={{"TWARDOWSKI","Three pages of the pact are hidden here.","Trzy karty cyrografu są tu ukryte."},
        {"TWARDOWSKI","Find them and burn them!","Znajdźcie je i spalcie!"}}},
    {bd="black",len=120,title=4},
  },
  ending={
    {bd="cellars",fx="shake",act={{"devil",120,108,300,30,10,90}},say={{"DEVIL","My pact! Noooo!","Mój cyrograf! Nieee!"}}},
    {bd="night",act={{"rooster",60,104,190,48,20,200,1},{"twardowski",62,96,192,40,20,200,1}},
      say={{"TWARDOWSKI","Free at last! I'm off to the moon.","Wolny! Lecę na Księżyc."},
        {"TWARDOWSKI","It's quieter up there.","Tam jest spokojniej."}}},
    {bd="hall",act={{"krak",120,108,120,108,0,0},{"wanda",-30,108,80,108,0,80},{"dratewka",-60,108,164,108,0,90,2,true}},
      say={{"KRAK","My hero! Here is your reward...","Mój bohaterze! Oto twoja nagroda..."},{"KRAK","Cheese!","Ser!"},
        {"WANDA","Half the kingdom, father.","Pół królestwa, ojcze."},{"KRAK","Half the cheese?","Pół sera?"}}},
    {bd="night",fx="fireworks",len=240},
    {bd="rynek",act={{"dwarf",40,108,40,108,0,0},{"dwarf",206,108,206,108,0,0,2,true},{"dratewka",-10,108,120,108,0,120}},
      say={{"DRATEWKA","Home. No more dragons.","Dom. Koniec ze smokami."}}},
    {bd="black",len=200,title="end"},
  },
}
SCENE_OF_CHAPTER={"wroclaw","sleza","krakow","cellars"}

local scene,backdrop
local LINE_FRAMES,FADE=150,12

local function nextShot()
  local s=scene
  s.n=s.n+1
  local sh=s.shots[s.n]
  if not sh then
    palShot,sky=palBase,nil
    fadePal(1)
    scene=nil
    s.after()
    return
  end
  backdrop=loadBackdrop(sh.bd)
  local stop=0
  for _,a in ipairs(sh.act or {}) do stop=math.max(stop,a[7]) end
  s.sh,s.t,s.line,s.lineT,s.start,s.leave=sh,0,1,0,stop+10,nil
end

function playScene(name,after)
  initPalette()
  initFont()
  if not palBase then
    palBase={}
    for i=0,47 do palBase[i]=peek(0x03FC0+i) end
  end
  scene={shots=SCENES[name],n=0,after=after}
  nextShot()
  state="scene"
end

local function drawActor(a,t)
  local who,x0,y0,x1,y1,t0,t1,sc,left=table.unpack(a)
  local k=t1>t0 and math.max(0,math.min(1,(t-t0)/(t1-t0))) or 1
  local e=k*k*(3-2*k)
  if left==nil then left=x1<x0 end
  return who,x0+(x1-x0)*e,y0+(y1-y0)*e,sc or 2,left,k>0 and k<1
end

function drawScene()
  local s=scene
  local sh=s.sh
  s.t=s.t+1
  local t=s.t
  local len=sh.len or s.start+60
  local cx=(sh.pan or 0)*math.min(1,t/len)//1
  local dy=sh.fx=="shake" and t<60 and sin(t*7)*2//1 or 0
  cls(0)
  if sh.fx=="flash" and t<8 then cls(12)
  elseif backdrop then memcpy((BAR+dy)*120,BACKDROP_RAM,BACKDROP_BYTES) end
  if OVERLAYS[sh.bd] then OVERLAYS[sh.bd](t) end
  if sh.fx=="fireworks" then fireworks(t) end
  for _,a in ipairs(sh.act or {}) do
    local who,x,y,sc,left,moving=drawActor(a,t)
    fig(who,x-cx,y+dy,sc,t,left,moving,sh.fx=="fire")
  end
  local title=sh.title
  if title then
    title=CHAPTERS[title] and L("CHAPTER ","ROZDZIAŁ ")..title or L("THE END","KONIEC")
    local w=textW(title,2)
    print(title,120-w//2,56,12,false,2,true)
    if CHAPTERS[sh.title] then
      local name=chapterName(sh.title)
      print(name,120-textW(name,1)//2,72,4,false,1,true)
    end
  end
  rect(0,0,240,BAR,0) rect(0,136-BAR,240,BAR,0)
  if sh.cap then
    local cap=L(sh.cap[1],sh.cap[2])
    print(cap:sub(1,t//3),120-textW(cap,1)//2,8,13,false,1,true)
  end

  if s.leave then
    s.leave=s.leave-1
    fadePal(s.leave/FADE)
    if s.leave<=0 then nextShot() end
    return
  end
  fadePal(math.min(1,t/FADE))
  local done
  if sh.say then
    if t>=s.start then
      local l=sh.say[s.line]
      s.lineT=s.lineT+1
      print(L(l[1],SPEAKER_PL[l[1]]),8,119,4,false,1,true)
      print(L(l[2],l[3]):sub(1,s.lineT//2),8,SUB_Y,12,false,1,true)
      if s.lineT>LINE_FRAMES or (s.lineT>20 and btnp(4)) then
        s.line,s.lineT=s.line+1,0
        done=s.line>#sh.say
      end
    elseif btnp(4) then
      s.t=s.start
    end
  else
    done=t>=len or (t>20 and btnp(4))
  end
  if done then s.leave=FADE end
end

-- story:end

-- ── game intro: a fuse burns to a bomb, the bomb blows the logo onto the screen ──

local sin,cos=math.sin,math.cos

introT=0
local INTRO_BOOM,INTRO_END=110,330

local function drawIntro()
  introT=introT+1
  local t=introT
  if t==1 then initPalette() initFont() startMusic() end
  if t==INTRO_BOOM then sndExplosion() end
  cls(0)
  if t<INTRO_BOOM then
    local sx=t*126//INTRO_BOOM
    for x=sx,126 do pix(x,58+sin(x/10)*4,13) end
    circ(132,74,14,15) circ(127,69,4,14) rect(129,57,6,4,14)
    local sy=58+sin(sx/10)*4
    for k=0,5 do pix(sx+sin(t*3+k)*3,sy+cos(t*5+k*2)*3,k%2==0 and 4 or 3) end
    circ(sx,sy,1,12)
  elseif t<INTRO_BOOM+6 then
    cls(12)
  else
    local b=t-INTRO_BOOM
    nightSky(t)
    if b<60 then
      for k=0,2 do circ(120,70,math.max(0,b*4-k*14),({2,3,4})[k+1]) end
      circ(120,70,math.max(0,b*4-48),0)
      for k=0,20 do pix(120+cos(k)*b*3,70+sin(k)*b*2+b*b/40,k%3+2) end
    end
    drawLogo(function(i)
      local d=b-10-i*6
      if d<0 then return -60 elseif d<10 then return d*3-30 end
      return d<20 and -math.abs(sin((d-10)/3))*4//1 or 0
    end)
    if b>90 then
      local sub=L("THE SULPHUR LEGEND","LEGENDA O SIARCE")
      print(sub:sub(1,(b-90)//3),120-textW(sub,1)//2,48,13,false,1,true)
    end
  end
  if t>=INTRO_END or (t>10 and btnp(4)) then
    state,titleTimer="title",2
  end
end

-- ── world map between stages ──────────────────────────────────────────────────

local mapAnim
local REGION_COL={6,7,13,15}

-- the chapter's 25 stages as a snake of five rows
local function nodePos(n)
  local i=(n-1)%CHAPTER_LEN
  local row,col=i//5,i%5
  if row%2==1 then col=4-col end
  return 40+col*40,40+row*18
end

function showMap(n)
  mapAnim={n=n,t=0}
  state="map"
end

function drawWorldMap()
  local m=mapAnim
  m.t=m.t+1
  local st=STAGES[m.n]
  local first=(st[1]-1)*CHAPTER_LEN+1
  cls(REGION_COL[st[1]])
  for i=first,first+CHAPTER_LEN-2 do
    local x0,y0=nodePos(i) local x1,y1=nodePos(i+1)
    line(x0,y0,x1,y1,12)
  end
  for i=first,first+CHAPTER_LEN-1 do
    local x,y=nodePos(i)
    circ(x,y,STAGES[i][7] and 4 or 2,i<m.n and 4 or (i==m.n and frame%20<10) and 12 or 0)
  end
  local fx,fy=nodePos(math.max(first,m.n-1))
  local tx,ty=nodePos(m.n)
  local k=math.min(1,m.t/60)
  drawSp(5+(k<1 and (m.t//8)%2 or 0),fx+(tx-fx)*k-4,fy+(ty-fy)*k-11,12,tx<fx)
  local title=chapterName(st[1])
  print(title,120-(print(title,0,-20) or 0)//2,4,12,false,1,false)
  local sub=L("STAGE ","ETAP ")..st[1].."-"..((m.n-1)%CHAPTER_LEN+1)..": "..L(table.unpack(GOALS[st[2]]))
  print(sub,120-textW(sub,1)//2,16,4,false,1,true)
  if m.t>60 and m.t%40<28 then print(L("PRESS Z","NACIŚNIJ Z"),104,128,12,false,1,true) end
  if m.t>200 or (m.t>30 and btnp(4)) then mapAnim=nil startStage(m.n) end
end

-- ── main loop ────────────────────────────────────────────────────────────────

function TIC()
  frame=frame+1
  updateMusic()
  updateDeaths()

  if state=="intro" then
    drawIntro()
    return
  elseif state=="title" then
    drawTitle()
    return
  elseif state=="scene" then
    drawScene()
    return
  elseif state=="map" then
    drawWorldMap()
    return
  end

  cls(FLOOR_COL)

  if state=="game" then
    updateBombs()
    updateBlasts()
    updateInvul()
    updateShrink()
    for _,p in ipairs(players) do
      if p.human then updatePlayer(p) else updateBot(p) end
    end

    if mode=="camp" then
      updateCampaign()
    else
      local alive,last=countAlive()
      if alive<=1 then
        state="over"
        winner=last
        score=addRoundWin(score, winner and winner.id)
        restartTimer=210
      end
    end

    drawMap()
    drawBlasts()
    drawBombs()
    drawPowerups()
    drawPlayers()
    if mode=="camp" then drawCampaign() else drawHUD() end

  elseif mode=="camp" then
    drawMap()
    drawBombs()
    drawPowerups()
    drawPlayers()
    drawCampaign()

  elseif state=="over" then
    updateBombs()
    updateBlasts()
    drawMap()
    drawBlasts()
    drawBombs()
    drawPlayers()
    drawPowerups()
    drawHUD()

    local msg=winner and ("P"..winner.id..L(" WINS!"," WYGRYWA!")) or L("DRAW!","REMIS!")
    local col=winner and winner.color or 7
    local mx=120-#msg*3
    print(msg,mx,50,col,false,2,true)

    if winner then
      local sub=winner.id<=2 and L("YOU WIN!","WYGRAŁEŚ!") or L("BOT WINS","WYGRAŁ BOT")
      local sc=winner.id<=2 and 12 or 9
      print(sub,120-#sub*2,72,sc,false,1,true)
    end

    local pct=math.ceil(restartTimer/210*100)
    print(L("restarting ","restart ")..pct.."%",88,90,13,false,1,true)

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
    local msg="P"..w..L(" WINS THE MATCH!"," WYGRYWA MECZ!")
    print(msg,120-#msg*3,50,players[w].color,false,1,true)
    print(L("new match in ","nowy mecz za ")..math.ceil(restartTimer/60).."s",88,90,13,false,1,true)

    restartTimer=restartTimer-1
    if restartTimer<=0 then
      score={0,0,0,0}
      init()
    end
  end
end

-- entry point
titleTimer=0
