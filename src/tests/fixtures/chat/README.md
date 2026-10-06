# `walk_s7.jsonl` — a scripted chat body, seed 7

One reply a line, **in call order**, each line exactly the text the model would
have sent (A §5's `--policy scripted:`). Forty-five lines for forty-four steps:
one step is refused twice and defaults, and a retry reads the next line.

| line (1-based) | step | what it is there for |
|---|---|---|
| 1 | 1 | names a destination, `[42, 23]` shown = `[42, 40]` world, seed 7's first errand cell — answered by a route line on turn 2 |
| 2 | 2 | `destination: null`, which is an answer and never retries (A §3.4) |
| 3, 4 | 3 | two cells off the map (`[64, 23]`, `[42, -1]`): `reply_invalid` twice, then the `noop` default |
| 5 | 4 | the turn after a default reports `waited` and answers no destination |
| 6 | 5 | names the cell this step walks onto, so turn 6 gets no route line and no `route` row |
| 7–19 | 6–18 | walks south then east |
| 20 | 19 | stands on `[42, 40]`: the `arrival` row, index 0. Names `[22, 39]` shown = the second errand cell, answered on turn 20 |
| 21–45 | 20–44 | walks back west and north |

The walk is a breadth-first path over seed 7's walkable cells, so every step but
step 3's default moves. The note lands with frame 10 and rides turn 11.

`test_chat_cell.py` guards these landmarks in
`test_the_fixture_is_the_run_these_tests_say_it_is`: edit the file and that test
says so before the rest go quiet.
