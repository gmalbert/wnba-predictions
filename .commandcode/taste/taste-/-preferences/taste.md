# Taste / Preferences
- Builds web/data apps with Streamlit (prefers Streamlit over other web frameworks for these projects). Confidence: 0.7
- Expects the agent to read all markdown files in the project's `docs/` folder before starting implementation. Confidence: 0.8
- Points the agent to an existing reference repo (e.g., `nba-predictions`) to follow for conventions when building a similar/porting project. Confidence: 0.8
- Prefers the agent to run long builds autonomously without interruptions (e.g., "I'm going to bed") and expects the agent to proactively check for pending approval gates/blockers before starting unattended work. Confidence: 0.8
- Wants complete, comprehensive implementation ("implement everything in this repo") rather than a scoped-down subset delivered piecemeal. Confidence: 0.7
- Prefers auto-accept permission mode for large builds so installs, file writes, and script runs proceed without approval prompts. Confidence: 0.7
- Comfortable with the agent committing progress to git during a build rather than waiting to ask first. Confidence: 0.6
