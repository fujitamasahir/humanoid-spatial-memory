# H2 High-Frequency Dynamics Protocol v1 — CRN Test Amendment 3

Before starting the 936-episode primary matrix, add a twin-run unit test that
constructs two transition engines with the same public map, schedule, seed,
robot/object/pedestrian state, then verifies exact event and post-event object
state equality at every tested step. Model identity is absent from the engine
API and CRN key. This strengthens the requested model-independent transition
test; it changes no runtime code or experiment condition.

The already completed amended smoke and original-condition Uncertainty stage
remain bound to `binding_amendment_2.json` and runner source commit `5c7c012`.
The primary matrix will use `binding_amendment_3.json`, which binds the same
runtime implementation and includes the added test. No primary navigation
episode has run under amendment 2.
