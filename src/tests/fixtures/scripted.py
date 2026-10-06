"""Scripted replies for the trace tests — A §5's `--policy scripted:`, in process.

A `Script` answers by round, with per-occasion overrides keyed `(step, round)`:
each key holds a queue, so the second R1 page of a step, or the retry of an
invalid reply, gets its own line. The step is read off the page the way the
model reads it — out of the state line's `"step"` — so nothing here has to be
told where in the run it is, and a test that changes the plan does not have to
re-count calls.

The world is a real `world.World` and the client a real
`client.ScriptedClient`; nothing in these tests contacts a server.

Coordinates in a scripted reply are the SHOWN axis (+y up), because that is what
the model writes (A §1.1).
"""

import re

from p3focus import client as client_mod

#: the page's own step: the state line carries the frame's step, and the world
#: step this page decides is the next one (A §1.3)
_STEP = re.compile(r'"step": (\d+)')


def page_step(page):
    """Which world step this page is deciding (A §1.3's numbering)."""
    return int(_STEP.search(page).group(1)) + 1


class Script:
    """A policy for `client.ScriptedClient` (A §5).

    `defaults` is one reply per round id, used whenever no override is queued.
    `plan` is `{(step, round): [reply, …]}`, popped in order. `log` keeps
    `(step, round, reply, page)` for every call, so a test can read back what
    was asked as well as what was answered.
    """

    def __init__(self, defaults, plan=None):
        self.defaults = dict(defaults)
        self.plan = {key: list(value) for key, value in (plan or {}).items()}
        self.round = None
        self.log = []

    def expect(self, round_id):
        """The controller's announcement of the round this call answers."""
        self.round = round_id

    def __call__(self, messages):
        page = messages[-1]["content"]
        step = page_step(page)
        queue = self.plan.get((step, self.round))
        reply = queue.pop(0) if queue else self.defaults[self.round]
        self.log.append((step, self.round, reply, page))
        return reply

    def pages(self, round_id=None, step=None):
        """The pages this script was shown, filtered."""
        return [page for s, r, _, page in self.log
                if (round_id is None or r == round_id) and (step is None or s == step)]

    def rounds(self):
        """`(step, round)` for every call, in call order."""
        return [(s, r) for s, r, _, _ in self.log]


class ScriptedClient(client_mod.ScriptedClient):
    """`client.ScriptedClient` with the round hook A §5's file needs, the same
    one `run.ScriptedRunClient` has."""

    def __init__(self, script, server="scripted:tests"):
        super().__init__(script)
        self.script = script
        self.server = server

    def set_round(self, round_id):
        self.script.expect(round_id)


# -- the replies the plans are built from -----------------------------------

def r1_no(why="the list as it stands is what I mean"):
    return '{"why": "%s", "maintain": "no"}' % why


def r1_ops(*ops, why="something I intend has no entry"):
    return '{"why": "%s", "maintain": "yes", "ops": [%s]}' % (why, ", ".join(ops))


def op_add(name, until, when=None, why=None):
    parts = [f'"op": "add", "name": "{name}"']
    if when is not None:
        parts.append(f'"when": "{when}"')
    parts.append(f'"until": "{until}"')
    if why is not None:
        parts.append(f'"why": "{why}"')
    return "{%s}" % ", ".join(parts)


def op_delete(entry_id):
    return '{"op": "delete", "id": "%s"}' % entry_id


def op_edit(entry_id, **fields):
    inner = ", ".join(f'"{k}": "{v}"' for k, v in fields.items())
    return '{"op": "edit", "id": "%s", %s}' % (entry_id, inner)


def r1_5(confirm):
    return '{"delete": %s}' % ("true" if confirm else "false")


def r2(entry_id, why="it is the one my next steps are for"):
    return '{"why": "%s", "focus": "%s"}' % (why, entry_id)


def r3(target=None, candidates=(), need="get there", why="it is the way", **_ignored):
    """R3's reply (A §3.1): the old round one's four keys. `do=` is accepted and
    ignored so older plans still read."""
    cand = ", ".join(f"[{c[0]}, {c[1]}]" for c in candidates)
    tgt = "null" if target is None else f"[{target[0]}, {target[1]}]"
    return '{"need": "%s", "candidates": [%s], "target": %s, "why": "%s"}' % (need, cand, tgt, why)


def r4(action, intent="going on"):
    return '{"action": "%s", "intent": "%s"}' % (action, intent)


def flat(action, intent="going on", ops=(), destination=None):
    dest = "null" if destination is None else f"[{destination[0]}, {destination[1]}]"
    return ('{"action": "%s", "intent": "%s", "ops": [%s], "destination": %s}'
            % (action, intent, ", ".join(ops), dest))
