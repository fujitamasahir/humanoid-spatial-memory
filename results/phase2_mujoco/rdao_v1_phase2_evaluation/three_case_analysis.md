# Three diagnostic RDAO cases

These are development cases, not an independent validation sample. Step divergence establishes temporal ordering only; no intervention replay was used to claim causation.

## case_A — phase1.5-v0.4-BPRIME-1:fit:R:80000003, schedule 1

RDAO: success=True, steps=71, observations=14, safety interventions=0, blocked attempts=0.
RDAO observation steps: [0, 8, 15, 18, 28, 30, 38, 40, 44, 48, 56, 64, 67, 69].
Versus periodic: first observation-timing difference at step 4; first position/heading/action difference at step 13; baseline success=True at 72 steps.
Versus uncertainty: first observation-timing difference at step 5; first position/heading/action difference at step 14; baseline success=False at 80 steps.
The RDAO timeline and observation-time route/memory snapshots show what the scheduler estimated and what the authorized 3D observation changed. These traces do not by themselves establish the intervention as the cause of an outcome difference.

## case_B — phase1.5-v0.4-BPRIME-1:fit:R:80000007, schedule 0

RDAO: success=True, steps=50, observations=11, safety interventions=0, blocked attempts=0.
RDAO observation steps: [0, 2, 4, 8, 12, 19, 24, 27, 35, 40, 50].
Versus periodic: first observation-timing difference at step 2; first position/heading/action difference at step 3; baseline success=True at 71 steps.
Versus uncertainty: first observation-timing difference at step 2; first position/heading/action difference at step 3; baseline success=True at 31 steps.
The RDAO timeline and observation-time route/memory snapshots show what the scheduler estimated and what the authorized 3D observation changed. These traces do not by themselves establish the intervention as the cause of an outcome difference.

## case_C — phase1.5-v0.4-BPRIME-1:fit:R:80000021, schedule 1

RDAO: success=True, steps=33, observations=5, safety interventions=5, blocked attempts=0.
RDAO observation steps: [0, 5, 14, 23, 32].
Versus periodic: first observation-timing difference at step 4; first position/heading/action difference at step 8; baseline success=True at 35 steps.
Versus uncertainty: first observation-timing difference at step 9; first position/heading/action difference at step 14; baseline success=True at 74 steps.
The RDAO timeline and observation-time route/memory snapshots show what the scheduler estimated and what the authorized 3D observation changed. These traces do not by themselves establish the intervention as the cause of an outcome difference.
