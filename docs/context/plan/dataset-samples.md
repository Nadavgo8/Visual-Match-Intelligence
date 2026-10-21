# What each dataset looks like

These are real records pulled on 2026-10-09 and trimmed for length. The Wyscout, SkillCorner tracking and DFL samples come from the small test files in the **kloppy** library, which use the providers' real formats. The full downloads are large or stored in Git LFS. Google Research Football is shown from its documented observation format and was not run here.

There are two kinds of data:
- **Event data** is one row per action (a pass, a shot, a tackle) with who, where and when.
- **Tracking data** is the x/y position of every player and the ball, 10 to 25 times a second. Speed, distance and pressure are computed from it.

---

## 1. StatsBomb Open Data (events, JSON)
Pitch is 120 × 80. Each event links to related events, so a key pass points to the shot it created. This sample is a through ball by Chelsea FCW followed by the shot from it.
```json
{ "index": 33, "period": 1, "timestamp": "00:00:38.660",
  "type": {"name": "Pass"}, "play_pattern": {"name": "From Counter"},
  "team": {"name": "Chelsea FCW"},
  "player": {"name": "Anita Amma Ankyewah Asante"}, "position": {"name": "Center Back"},
  "location": [44.0, 17.0], "duration": 3.453,
  "pass": { "recipient": {"name": "Francesca Kirby"},
            "length": 51.35, "angle": 0.117, "height": {"name": "High Pass"},
            "end_location": [95.0, 23.0], "through_ball": true,
            "shot_assist": true, "assisted_shot_id": "9b82eaa3-…",
            "body_part": {"name": "Right Foot"} } }

{ "index": 42, "timestamp": "00:00:47.620", "type": {"name": "Shot"},
  "player": {"name": "Francesca Kirby"}, "location": [115.0, 25.0],
  "shot": { "statsbomb_xg": 0.0189, "end_location": [117.0, 34.0],
            "key_pass_id": "00821d9b-…", "type": {"name": "Open Play"},
            "outcome": {"name": "Blocked"} } }
```
Some matches also include "360" freeze-frames, which give every visible player's position at the moment of the event.

## 2. Wyscout public dataset (events, JSON)
This format is much leaner, with numeric codes for event types and tags. Coordinates run from 0 to 100.
```json
{ "id": 190078344, "matchId": 2499773, "teamId": 1612, "playerId": 25393,
  "matchPeriod": "1H", "eventSec": 4.35,
  "eventName": 8, "subEventName": 83,          // 8 = Pass, 83 = High pass
  "positions": [{"x": 29, "y": 41}, {"x": 71, "y": 94}],   // start → end
  "tags": [{"id": 1802}] }                      // 1802 = inaccurate
```

## 3. Metrica Sports sample data (events and tracking, CSV)
Players are anonymized and coordinates run from 0 to 1. Tracking is 25 frames per second.

Events:
```
Team,Type,Subtype,Period,Start Frame,Start Time [s],End Frame,End Time [s],From,To,Start X,Start Y,End X,End Y
Away,SET PIECE,KICK OFF,1,1,0.04,0,0,Player19,,NaN,NaN,NaN,NaN
Away,PASS,,1,1,0.04,3,0.12,Player19,Player21,0.45,0.39,0.55,0.43
Away,PASS,,1,3,0.12,17,0.68,Player21,Player15,0.55,0.43,0.58,0.21
```
Tracking has one row per frame and an x,y column pair per player plus the ball:
```
Period,Frame,Time [s],Player11 x,y,Player1 x,y,Player2 x,y, … ,Ball x,y
1,1,0.04,0.00082,0.48238,0.32648,0.65322,0.33701,0.48863, … ,0.45472,0.38709
```

## 4. SkillCorner open data (tracking from TV footage and "dynamic events")
Tracking is JSON lines at 10 frames per second, with metres from the centre spot. `is_detected: false` means the player was off-camera and their position was estimated.
```json
{ "frame": 20, "timestamp": "00:00:01.00", "period": 1,
  "ball_data": {"x": 0.0, "y": -0.31, "z": 0.2, "is_detected": true},
  "possession": {"player_id": null, "group": null},
  "player_data": [ {"player_id": 76, "x": -41.97, "y": -0.61, "is_detected": false},
                   {"player_id": 94, "x": -19.77, "y": -7.34, "is_detected": false} ] }
```
Dynamic events are a very wide CSV with about 300 columns of tactical context per action. Selected columns from the first row of an A-League match:
```
event_type=player_possession  player_name=J. Caletti  player_position=RDM  team=Brisbane FC
x_start=0.3 y_start=0.23  third_start=middle_third  channel_start=center
game_state=drawing  team_in_possession_phase=create  opponent_phase=medium_block
end_type=pass  pass_outcome=successful  speed_category=jogging  pass_direction=backward ...
```
The repo also has season aggregates (passing, physical) and body-pose samples.

## 5. DFL / Sportec open data (Bundesliga, XML)
Events are rich XML, and tackles record who won the duel and how:
```xml
<Event EventTime="2020-06-05T20:30:03.333+02:00" X-Position="73.94" Y-Position="37.21">
  <Play Player="DFL-OBJ-0000ZS" Recipient="DFL-OBJ-002G3I" Team="DFL-CLU-000004"
        Evaluation="successfullyCompleted" Height="high" Distance="long"
        PlayAngle="329.23" FromOpenPlay="true">
    <Pass Direction="diagonalBall"/>
  </Play>
</Event>
<Event EventTime="2020-06-05T20:30:14.200+02:00" X-Position="27.57" Y-Position="63.81">
  <TacklingGame Winner="DFL-OBJ-0001E5" Loser="DFL-OBJ-00017V" WinnerResult="layoff"
                Type="ground" PossessionChange="false"/>
</Event>
```
Tracking is 25 frames per second. Each frame comes with **speed (S, km/h), distance (D) and acceleration (A)** already computed, which suits the brief's speed and distance features well.
```xml
<FrameSet GameSection="firstHalf" TeamId="BALL" PersonId="DFL-OBJ-0000XT">
  <Frame N="10001" T="2020-06-05T20:29:57.880+02:00" X="3.41" Y="0.26" Z="0.08"
         D="72.08" A="0.00" S="65.59" BallPossession="1" BallStatus="1"/>
```

## 6. Google Research Football (simulator, fully synthetic)
There is no file to download. You run matches, and each step returns a state like the one below, roughly 10 per second. You'd write the events (pass, shot, tackle) yourself by watching for changes in `ball_owned_player`, `game_mode` and `score`.
```python
{ "ball": [0.12, -0.03, 0.11],          # x, y, z  (x in -1..1, y in -0.42..0.42)
  "ball_owned_team": 0, "ball_owned_player": 7,
  "left_team":  [[-1.0, 0.0], [-0.42, -0.19], ...],   # 11 player positions
  "right_team": [[1.0, 0.0], ...],
  "left_team_direction": [[0.001, 0.0], ...],         # per-player velocity
  "score": [1, 0], "steps_left": 2310, "game_mode": 0 }
```
This is shown from the documented format and has not been run.

---

## What this means for us
- **StatsBomb** is the best model for our synthetic event schema, because it has explicit links between passes and shots and gives xG for every shot.
- **DFL/Sportec** tracking already includes speed and distance per frame, which suits the player tagging and speed features in the brief.
- **SkillCorner's** tactical labels (block type, phase of play, game state) suit the "explain why it matters" stage.
- **kloppy** reads all five file formats into one model.
