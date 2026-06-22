# Cortical Peaks Challenge 2026 -- BCI Client / Game Server Protocol

## 1. Overview

The Cortical Peaks Challenge 2026 server maintains authoritative, headless game loops. A BCI client connects over UDP, registers to obtain a session token, submits game commands, and sustains a bidirectional heartbeat. Games are started and stopped exclusively by the server operator; the BCI client has no mechanism to initiate or terminate a game.

---

## 2. Conventions

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

---

## 3. Transport

All communication uses UDP. The server listens on port 5000 by default.

---

## 4. Wire Format

Every message is a binary datagram. All multi-byte integer and float fields use **big-endian (network byte order)** byte ordering.

### 4.1 Scalar Field Types

| Code | Width   | Signed | Description                                            |
| ---- | ------- | ------ | ------------------------------------------------------ |
| `B`  | 1 byte  | No     | Unsigned integer; type bytes, flags, small counters    |
| `b`  | 1 byte  | Yes    | Signed integer; direction values (-1 or 1)             |
| `H`  | 2 bytes | No     | Unsigned integer; pixel sizes, larger counters         |
| `h`  | 2 bytes | Yes    | Signed integer; pixel coordinates that may be negative |
| `f`  | 4 bytes | -      | IEEE 754 single-precision float, big-endian            |
| `Ns` | N bytes | -      | Fixed-size byte string; see Section 4.2                |

### 4.2 String Fields

String fields are encoded as UTF-8 and stored in a fixed-size byte array. If the UTF-8 encoding is shorter than the field, the remaining bytes MUST be `0x00`. On decode, trailing null bytes MUST be stripped. A field of all null bytes represents the empty string.

### 4.3 Token Fields

Session tokens are 8 raw bytes on the wire. This document represents them as 16-character lowercase hex strings (e.g. `abcdef0123456789`).

### 4.4 Enum Values

**MessageType** (`B`, 1 byte):

| Value  | Name       | Direction       |
| ------ | ---------- | --------------- |
| `0x01` | `REGISTER` | BCI to Server   |
| `0x02` | `ACK`      | Server to BCI   |
| `0x03` | `PING`     | both directions |
| `0x04` | `PONG`     | both directions |
| `0x05` | `CMD`      | BCI to Server   |

`PING` (`0x03`) and `PONG` (`0x04`) are reused for both directions. The two cases are distinguished by frame size: a server-originated `PING` or `PONG` is exactly 1 byte; a client-originated `PING` or `PONG` is 10 bytes and additionally carries `device` and `session_token`.

**DeviceType** (`B`, 1 byte):

| Value  | Name  |
| ------ | ----- |
| `0x00` | `BCI` |

---

## 5. Message Definitions

All byte offsets are zero-indexed from the start of the datagram.

### 5.1 REGISTER

A BCI client MUST send this message to create a session. Each `REGISTER` creates a new session with a freshly issued token; there is no mechanism to reclaim a previous session. The `display_name` field is shown in the server UI and plays no role in session routing or reconnection.

| Offset | Type  | Field         |
| ------ | ----- | ------------- |
| 0      | `B`   | type = `0x01` |
| 1      | `B`   | device        |
| 2-17   | `16s` | display_name  |

Example: display_name `"alice"`, device BCI:

```
01  00  61 6c 69 63 65 00 00 00 00 00 00 00 00 00 00 00
^   ^   ^-- "alice" (5 bytes) --^  ^--- zero padding ---^
|   device=BCI
type=REGISTER
```

### 5.2 ACK

Sent by the server in response to a successful `REGISTER`. The `session_token` is 8 raw bytes that serve as the sole session identifier and MUST be included in all subsequent client messages.

| Offset | Type | Field         |
| ------ | ---- | ------------- |
| 0      | `B`  | type = `0x02` |
| 1-8    | `8s` | session_token |

Example -- token `abcdef0123456789` (the hex representation of the 8 wire bytes):

```
02  ab cd ef 01 23 45 67 89
^   ^--- session_token (8 bytes) ---^
type=ACK
```

### 5.3 PING, client-initiated

Sent by the client to maintain the session. The server MUST respond with a server PONG (Section 5.6).

| Offset | Type | Field         |
| ------ | ---- | ------------- |
| 0      | `B`  | type = `0x03` |
| 1      | `B`  | device        |
| 2-9    | `8s` | session_token |

Example:

```
03  00  ab cd ef 01 23 45 67 89
^   ^   ^--- session_token (8 bytes) ---^
|   device=BCI
type=PING
```

### 5.4 PING, server-initiated

Sent by the server to verify client liveness. The client MUST respond with a client PONG (Section 5.5). The 1-byte frame size distinguishes this from the 10-byte client-initiated PING.

| Offset | Type | Field         |
| ------ | ---- | ------------- |
| 0      | `B`  | type = `0x03` |

Example:

```
03
^
type=PING
```

### 5.5 PONG, client response

Sent by the client in response to a server-initiated PING.

| Offset | Type | Field         |
| ------ | ---- | ------------- |
| 0      | `B`  | type = `0x04` |
| 1      | `B`  | device        |
| 2-9    | `8s` | session_token |

Example:

```
04  00  ab cd ef 01 23 45 67 89
^   ^   ^--- session_token (8 bytes) ---^
|   device=BCI
type=PONG
```

### 5.6 PONG, server response

Sent by the server in response to a client-initiated PING. The 1-byte frame size distinguishes this from the 10-byte client PONG.

| Offset | Type | Field         |
| ------ | ---- | ------------- |
| 0      | `B`  | type = `0x04` |

Example:

```
04
^
type=PONG
```

### 5.7 CMD

Delivers a game input to the server. `content` is a command string zero-padded to 8 bytes; valid values are listed in Section 8. The server MUST discard CMD messages received before a game is active or while the countdown is non-zero. The server MUST silently drop any CMD message whose `session_token` is not recognised.

| Offset | Type | Field         |
| ------ | ---- | ------------- |
| 0      | `B`  | type = `0x05` |
| 1      | `B`  | device        |
| 2-9    | `8s` | session_token |
| 10-17  | `8s` | content       |

Example -- content `"jump"` (`6a 75 6d 70`), zero-padded to 8 bytes:

```
05  00  ab cd ef 01 23 45 67 89  6a 75 6d 70 00 00 00 00
^   ^   ^--- session_token ---^  ^-"jump"-^  ^-padding-^
|   device=BCI
type=CMD
```

---

## 6. Registration

A BCI client MUST send `REGISTER` messages until it receives an `ACK`. On receipt of `ACK` the client MUST store the `session_token` and MUST NOT send further `REGISTER` messages while that token is held.

If a `REGISTER` arrives for a `display_name` that already has an active session (e.g. the client retried after an `ACK` was lost in transit), the server MUST reuse the existing session and re-send the `ACK` with the original token rather than creating a duplicate session. The session token is the sole identifier used in all subsequent messages.

---

## 7. Heartbeat and Timeout

The heartbeat is bidirectional and both directions operate independently with a three-second inactivity timeout.

**Client to Server.** The client MAY periodically send PING messages (Section 5.3). The server MUST respond to each with a server PONG (Section 5.6). Any received server message resets the client's inactivity timer. If no server message is received within three seconds, the client MUST treat the server as unreachable, discard the session token, and resume sending `REGISTER` messages. Note that the client-initiated PING mirrors the server-initiated direction and is primarily useful for the client to detect server unreachability; from the server's perspective, any message carrying a valid session token -- including PONG responses and CMD messages -- resets the inactivity timer equally.

**Server to Client.** The server MUST periodically send PING messages (Section 5.4) to the client's last known address. The client MUST respond to each with a client PONG (Section 5.5). Any `PING`, `PONG`, or `CMD` carrying a valid session token updates the server's last-seen timestamp and, if the BCI was previously considered disconnected, immediately marks it as reconnected. If a client fails to respond to server PINGs and sends no other messages, the server MUST consider the BCI disconnected after three seconds and pause the game.

---

## 8. Game Commands

The `content` field of a `CMD` message MUST be one of the strings listed below, zero-padded to 8 bytes. The server MUST silently drop any `CMD` with an unrecognised `content` value.

| Game                | `INPUT_A` | `INPUT_B`  |
| ------------------- | --------- | ---------- |
| Dino (Jump & Duck)  | jump      | duck       |
| Dino (Jump Only)    | jump      | (unused)   |
| Pong vs AI          | move up   | move down  |
| Pong PvP            | move up   | move down  |

The `content` field MUST be either `"INPUT_A"` or `"INPUT_B"`, zero-padded to 8 bytes. The server maps these to game-specific actions as shown above.

---

## 9. Game Lifecycle

Games are started by the server operator, not by the BCI client.

When the operator selects a game for a given player, the server initialises a fresh game state with a countdown during which the game is paused. CMD messages arriving while the countdown is non-zero MUST be discarded. When the countdown reaches zero the game enters its active phase and CMD messages are processed as game input.

A Dino game ends when the player loses all lives (one life is lost per obstacle collision) or the time limit expires. A Pong game ends when one side reaches the score limit. On game over the server holds the final state for a linger period, then resets. The server MUST NOT accept further commands during the linger period.

If the BCI disconnects while a game is running, the game MUST pause immediately and MUST resume when the BCI reconnects.

---

## 10. Disconnection and Eviction

A BCI is considered disconnected when no message has been received from it for more than three seconds. Any `PING`, `PONG`, or `CMD` carrying the session token within a thirty-second window MUST reconnect the session immediately; no `REGISTER` is required.

If thirty seconds elapse without any message carrying the session token, the server MUST evict the session. After eviction the client MUST send a new `REGISTER` to obtain a fresh session token.

---

## 11. Example: Dino Game Playthrough

`C` is the BCI client; `S` is the game server. Messages are shown as field descriptors rather than raw hex for readability; the actual wire encoding follows the layouts in Section 5.

```
C to S  REGISTER  display_name="alice"  device=BCI             (18 bytes)

        Server creates a new session and issues a token.

S to C  ACK  session_token=abcdef0123456789                    (9 bytes)

        Client stores session_token and stops sending REGISTER.

-- Heartbeat exchanges begin on both sides. --

C to S  PING  device=BCI  session_token=abcdef0123456789       (10 bytes)
S to C  PONG                                                    (1 byte)

S to C  PING                                                    (1 byte)
C to S  PONG  device=BCI  session_token=abcdef0123456789       (10 bytes)

-- Operator selects Dino for "alice". Server initialises game with countdown, game paused. --

C to S  CMD  session_token=abcdef0123456789  content="jump"    (18 bytes)

        Discarded: countdown has not yet expired.

-- Countdown expires. Game enters active phase. --

C to S  CMD  session_token=abcdef0123456789  content="jump"    (18 bytes)

        Accepted. Dino jumps over a cactus.

C to S  CMD  session_token=abcdef0123456789  content="duck"    (18 bytes)

        Accepted. Dino ducks under a low obstacle.

-- Many CMD messages follow. Heartbeats continue throughout. --

        Dino collides with an obstacle and loses its last life.
        Server sets game_over and enters the linger period.
        No further commands are accepted.

        Linger ends. Game state is reset. Player idles until the
        operator starts another game.
```

---

## 12. Implementation Notes

### Buffer sizing

All messages have statically known or easily computed sizes. A BCI client only ever receives ACK (9 bytes), server PING (1 byte), and server PONG (1 byte). A receive buffer of 32 bytes is sufficient.

If your receive buffer is smaller than the incoming datagram, the OS silently truncates it and the excess bytes are discarded. Always allocate a buffer at least as large as the largest message you expect to receive.

### Partial reads and message boundaries

UDP preserves datagram boundaries: each `recvfrom` call returns exactly one complete datagram as transmitted. Unlike TCP, you will never receive a partial message or have two messages merged into a single read.

### Length validation

Before unpacking any fields, implementations SHOULD verify that the received byte count matches the expected size for the decoded message type. Datagrams whose length does not match SHOULD be discarded.

For `PING` (0x03) and `PONG` (0x04), check the total datagram length to distinguish server-originated (1 byte) from client-originated (10 bytes). Any datagram whose type byte is not in `{0x01..0x05}` SHOULD be discarded.

### Endianness

All multi-byte fields (`H`, `h`, `f`) are big-endian. On little-endian hosts, byte-swap these fields on both read and write. Standard library support: Python `struct` with `>` format prefix, C `ntohs`/`ntohl`/`htons`/`htonl`, Rust `u16::from_be_bytes`, Java `ByteBuffer.order(ByteOrder.BIG_ENDIAN)`.
