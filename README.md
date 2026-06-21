# Cortical Peaks Challenge 2026

A collection of arcade games built with Python and Pygame, designed and implemented to serve as the competition environment for the [Cortical Peaks Challenge](https://www.tugraz.at/institute/ine/graz-bci-conferences/10th-graz-bci-conference-2026/cortical-peaks-challenge-2026) at the Graz BCI Conference 2026.

| Game            | Description                                  |
| --------------- | -------------------------------------------- |
| **Brain Ski 1** | Chrome-style dinosaur runner (1P)            |
| **Pong**        | Classic two-paddle ball game (1P vs AI / 2P) |
| **Brain Ski 2** | Obstacle avoidance game (player count TBD)   |

## Getting Started

### Prerequisites

The project uses [**uv**](https://docs.astral.sh/uv/) as a package and project management tool. Please refer to the [official website](https://docs.astral.sh/uv/) for installation steps. For Windows users, we expect you to use Windows PowerShell as your shell.

### Installation

```bash
git clone https://github.com/neuroTUM/cortical-peaks-challenge-2026.git
```

```bash
cd cortical-peaks-challenge-2026
```

```bash
uv sync --dev
```

If you activate/source the virtual environment created by `uv` you can omit `uv run` as a prefix and use `just <recipe>` directly.

```bash
uv run just setup
```

You can take a look at all pre-configured recipes using `uv run just --list`. Please consult the [official website](https://just.systems/man/en/) of just for an overview on how to use `just`.

### Quickstart

Cortical Peaks Challenge 2026 consists of three separate applications:

- **Game Server**: The authoritative source of truth for game logic and state. Manages sessions and starts games.
- **Spectator**: Display-only client for viewing running games.
- **BCI Client**: Implemented by each competing team; sends inputs to the server during a game.

The Game Server and Spectator are provided by Cortical Peaks Challenge 2026, while the BCI Client is expected to be implemented by the competing teams. A reference implementation in Python is available at `examples/bci_client.py`.

To see what it should look like, run the following commands in separate shell sessions:

```bash
uv run just run server
```

```bash
uv run just run spectator
```

```bash
uv run just example-bci
```

This will launch the server, a spectator, and an example BCI client. From there you can explore the UI and see how it works!

#### Playing a game

With all three running, start a game:

1. **Connect the BCI controller.** The example client (`uv run just example-bci`) registers with the server automatically; a team's own client connects the same way.
2. **Connect the spectator.** In the spectator window, click **CONNECT TO SERVER**, enter the server IP and port (defaults `127.0.0.1` and `5000`), then click **CONNECT**.
3. **Pick a game on the server.** In the server window, open the **CONNECTIONS** tab and choose a game for a connected player: **BSJ** (BrainSki, jump only), **BSDJ** (BrainSki, jump & duck), **PONG PVP**, or **PONG AI**.
4. **Watch it play.** In the spectator window, click the player in the **PLAYER** column. The game begins after a 10-second countdown and then responds to the BCI inputs.

#### Developer flags

The server and spectator accept extra flags for development, passed through `just run`:

- **Debug** (`--debug`) -- draws the layout grid and obstacle hitboxes.
- **Audit** (`--audit`) -- writes a JSON Lines log of every server event (registrations, inputs, game start/over, disconnects) to `data/audit/`. Server-side only.

```bash
uv run just run server --debug --audit   # use either or both flags
```

## Contributing

Contributions are welcome! For non-trivial changes we'd appreciate a GitHub issue to discuss the approach before opening a pull request. See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, commit conventions, and protocol references.

### For Participating Teams

If you run into any bugs or have any feature requests, please open an issue right here in the repository. It's the best way for us to track requests and discuss them with you!

## License

<sup>
Licensed under either of <a href="LICENSE-APACHE">Apache License, Version
2.0</a> or <a href="LICENSE-MIT">MIT license</a> at your option.
</sup>

<br>

<sub>
Unless you explicitly state otherwise, any contribution intentionally submitted
for inclusion in this repository by you, as defined in the Apache-2.0 license, shall
be dual licensed as above, without any additional terms or conditions.
</sub>
