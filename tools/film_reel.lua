-- Developer reel, appended to the game code by `python make_tic.py --films`: plays every
-- story scene in a loop, so they can be judged in TIC-80 without playing the campaign.
local REEL={"wroclaw","sleza","krakow","cellars","ending"}
local reelAt=0
local function nextFilm()
  reelAt=reelAt%#REEL+1
  playScene(REEL[reelAt],nextFilm)
end
startMusic()
nextFilm()
