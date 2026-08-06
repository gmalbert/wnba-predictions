# Taste / Preferences
- Builds web/data apps with Streamlit (prefers Streamlit over other web frameworks for these projects). Confidence: 0.7
- Expects the agent to read all markdown files in the project's `docs/` folder before starting implementation. Confidence: 0.8
- Points the agent to an existing reference repo (e.g., `nba-predictions`) to follow for conventions when building a similar/porting project. Confidence: 0.8
- Prefers the agent to run long builds autonomously without interruptions (e.g., "I'm going to bed" / "I need to go to work") and expects the agent to proactively request all needed permissions upfront before starting unattended work, rather than interrupting later. Confidence: 0.95
- Wants complete, comprehensive implementation ("implement everything in this repo"; "i will expect a completed repo when I get home") rather than a scoped-down subset delivered piecemeal. Confidence: 0.85
- Expects the agent to verify all Python files compile (py_compile) before delivery. Confidence: 0.9
- Expects the Streamlit site to be verified via a Playwright browser test (boots and renders) before delivery. Confidence: 0.9
- Prefers auto-accept permission mode for large builds so installs, file writes, and script runs proceed without approval prompts. Confidence: 0.7
- Comfortable with the agent committing progress to git during a build rather than waiting to ask first. Confidence: 0.6
