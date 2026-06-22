# Internal Wire Protocol

This document describes the internal wire protocol used by spectator (renderer) clients, and the binary game-state formats carried inside `STATE` messages. It extends the BCI client protocol defined in `PROTOCOL.md`.

Developers adding a new game must:
1. Define a `GameState` dataclass and a binary codec (see [Game State Binary Format](#game-state-binary-format)).
2. Assign a new `game` byte value (next free value after `0x03`).
3. Register the codec in the server's `_broadcast_state` and the spectator client's decode path.

---

## Device Type

| Value  | Name        |
| ------ | ----------- |
| `0x00` | `BCI`       |
| `0x01` | `SPECTATOR` |

Spectator clients use `device = 0x01` in `REGISTER`, `PING`, and `PONG` messages (see `PROTOCOL.md` sections 5.1, 5.3, 5.5).

---

## Additional Message Types

| Value  | Name       | Direction           |
| ------ | ---------- | ------------------- |
| `0x06` | `SPECTATE` | Spectator to Server |
| `0x07` | `STATE`    | Server to Spectator |
| `0x08` | `SESSIONS` | Server to Spectator |

---

## Message Definitions

### SPECTATE (0x06)

Sent by a spectator client to start watching a specific player session. `target_uid` is the BCI token of the session to watch. Setting `target_uid` to the empty string (all-null bytes) stops watching the current session.

| Offset | Type  | Field         |
| ------ | ----- | ------------- |
| 0      | `B`   | type = `0x06` |
| 1-8    | `8s`  | viewer_token  |
| 9-24   | `16s` | target_uid    |

### STATE (0x07)

Sent by the server to spectator clients watching an active game. `game` identifies the game type and determines how to interpret `content`. The content bytes are the serialised game state — see [Game State Binary Format](#game-state-binary-format) for the per-game layouts.

| Offset | Type | Field         |
| ------ | ---- | ------------- |
| 0      | `B`  | type = `0x07` |
| 1      | `B`  | game          |
| 2+     | -    | content       |

**game** (`B`, 1 byte):

| Value  | Name        |
| ------ | ----------- |
| `0x01` | `DINO`      |
| `0x02` | `PONG`      |
| `0x03` | `PONG_AI`   |
| `0x04` | `DINO_JUMP` |

### SESSIONS (0x08)

Broadcast by the server to all spectator clients whenever the session list changes. Each entry describes one registered BCI player session.

| Offset    | Type  | Field                     |
| --------- | ----- | ------------------------- |
| 0         | `B`   | type = `0x08`             |
| 1         | `B`   | count                     |
| 2 + n×34  | `16s` | sessions[n].uid           |
| 18 + n×34 | `16s` | sessions[n].display_name  |
| 34 + n×34 | `B`   | sessions[n].game          |
| 35 + n×34 | `B`   | sessions[n].bci_connected |

Each session entry is 34 bytes: `uid` (16s) + `display_name` (16s) + `game` (B) + `bci_connected` (B).

**game** (`B`, 1 byte): `0x00` = no game active, `0x01` = Dino, `0x02` = Pong, `0x03` = Pong AI, `0x04` = Dino (Jump Only).

**bci_connected** (`B`, 1 byte): `0x00` = disconnected, `0x01` = connected.

---

## Game State Binary Format

All multi-byte fields use **big-endian (network byte order)** — Python `struct` format prefix `!`. Field type codes follow the same conventions as `PROTOCOL.md` Section 4.1.

When a field is removed from or added to a game state struct, **both** `dump_bytes` and `validate_bytes` in the game's `state.py` must be updated together. The format string comment (`# N bytes`) must also be kept in sync — it is the only human-readable record of the field order.

### Dino (`game = 0x01` or `0x04`)

Both Dino variants (Jump & Duck = `0x01`, Jump Only = `0x04`) use the identical layout below. The `content` bytes for a Dino `STATE` message are laid out as:

```
[ GameState header (42 bytes) ][ DinoState (24 bytes) ][ ObstacleState × N (11 bytes each) ]
```

`N` is given by `obstacle_count` in the header.

#### GameState header — `"!16sfBHHHBfhhfBB"` (42 bytes)

| Offset | Type  | Field           | Notes                         |
| ------ | ----- | --------------- | ----------------------------- |
| 0      | `16s` | username        | UTF-8, null-padded            |
| 16     | `f`   | time_left       | seconds remaining             |
| 20     | `B`   | obstacle_count  | number of ObstacleState items |
| 21     | `H`   | current_speed   | pixels per frame              |
| 23     | `H`   | game_timer      | elapsed frames                |
| 25     | `H`   | score           |                               |
| 27     | `B`   | game_over       | `0x00` or `0x01`             |
| 28     | `f`   | countdown       | pre-game countdown in seconds |
| 32     | `h`   | clouds_offset   | pixels, wraps                 |
| 34     | `h`   | track_offset    | pixels, wraps                 |
| 36     | `f`   | spawn_timer     | frames since last spawn       |
| 40     | `B`   | is_paused       | `0x00` or `0x01`             |
| 41     | `B`   | lives           | remaining lives               |

#### DinoState — `"!hhhhHHBBHHfH"` (24 bytes)

| Offset | Type | Field        | Notes                            |
| ------ | ---- | ------------ | -------------------------------- |
| 0      | `h`  | base_x       | centre-bottom x, pixels          |
| 2      | `h`  | base_y       | centre-bottom y, pixels          |
| 4      | `h`  | hitbox_x     | top-left x                       |
| 6      | `h`  | hitbox_y     | top-left y                       |
| 8      | `H`  | width        | pixels                           |
| 10     | `H`  | height       | pixels (shrinks on duck)         |
| 12     | `B`  | is_jumping   | `0x00` or `0x01`                |
| 13     | `B`  | is_ducking   | `0x00` or `0x01`                |
| 14     | `H`  | duck_timer   | frames remaining                 |
| 16     | `H`  | frame_count  | animation frame counter          |
| 18     | `f`  | y_speed      | pixels/frame, signed             |
| 22     | `H`  | invuln_timer | post-hit grace frames remaining  |

#### ObstacleState — `"!hhHHBH"` (11 bytes, repeated N times)

| Offset | Type | Field       | Notes                                       |
| ------ | ---- | ----------- | ------------------------------------------- |
| 0      | `h`  | hitbox_x    | top-left x (may be negative when off-screen)|
| 2      | `h`  | hitbox_y    | top-left y                                  |
| 4      | `H`  | width       | pixels                                      |
| 6      | `H`  | height      | pixels                                      |
| 8      | `B`  | type        | `0x00` cactus, `0x01` bird                  |
| 9      | `H`  | frame_count | animation frame counter                     |
