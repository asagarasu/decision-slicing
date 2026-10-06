"""p3_focus — a crafter gridworld body running a chain of errands under four arms.

This package is the apparatus for a cognitive-control experiment: a single body
in a Crafter world (flat / chat / sliced / focus arms) carries out a short errand
chain while its world, pages and traces are recorded step for step. This module
is the world/substrate layer: the world itself, its coordinates, its per-step
records and the route hint. The page, gate and reader layers build on top of it.
"""
