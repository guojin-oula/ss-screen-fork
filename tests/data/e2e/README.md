# Stage 1--11 CI fixture

This directory contains a tiny, synthetic rock-salt example for
`tests/test_e2e_pipeline.py`. It is a software-contract fixture, not a research
dataset and not evidence for any CaS/CaSe/CaTe scientific conclusion.

The test runs the real lightweight CLI path for composition screening,
environment matching, gap task export/validation, pair enumeration, random SQS
generation, mixing enthalpy, and Stage 11 recommendation. External or expensive
boundaries are deterministic substitutes:

- `gap_evidence.csv` stands in for returned high-fidelity calculations;
- the test builds compatible Stage 7 relaxation records without loading MACE;
- the test builds minimal Stage 9 and Stage 10 summary rows without running
  Phonopy, Materials Project queries, or a competing-phase calculation.

Every generated artifact is written under pytest's temporary directory. The
fixture needs no network, API key, GPU, model checkpoint, DFT code, or AiiDA
profile.
