# Wire In Your AI


## The ring is a face (state files)

The ring polls the server, and the server reads three tiny files in `state/`:

- `state/state`: one word, `idle`, `listening`, `thinking`, or `speaking`
- `state/mood.json`: `{"mood": "green", "ts": <unix time>}` (also `amber`, `red`)
- `state/wave.json`: `{"samples": [0..1 ×64], "ts": <unix time>}` (the voice waveform, only read while speaking)

No files? The ring just breathes. Write `thinking` to `state/state` and watch it spin up. That's the whole integration.

## The board is a stage (the /cmd channel)

Your AI stages things by POSTing JSON to `/cmd`; use `bin/board.sh`:

- `{"a":"add_card","title":"IDEA","body":"..."}`: a glass card materializes
- `{"a":"add_img","src":"misc/chart.png"}`: an image from the media airlock
- `{"a":"hand","src":"models/engine.glb"}`: deliver a 3D model to your reach
- `{"a":"explode"}` / `{"a":"assemble"}`: part and rebuild a model
- `{"a":"yank","title":"IDEA"}`: take it back off the board, with attitude

And `bin/board-state.sh` is the reverse: it prints what's actually on the board, so your assistant can look before it speaks.

## Claude Code users

