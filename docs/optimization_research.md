# Optimization Research: Consolidating Telegram Bot Services

## Overview
Currently, the `tg2book` project runs two separate Python processes (or containers) for the Telegram Bot and the Userbot listener. On a VDS with limited RAM (1GB), this overhead is significant.

## Current State Analysis
Based on `ps aux` and `docker ps` from the VDS:
- **Process 1 (`bot.py`)**: Consumes ~40MB RAM.
- **Process 2 (`userbot_listener.py`)**: Consumes ~56MB RAM.
- **Total Python Overhead**: ~100MB (excluding Docker daemon and other services).

### Redundancy Finding
The `bot.py` script already contains logic to initialize and run both the `bot_client` (Bot API) and `userbot_client` (MTProto) within a single `asyncio` event loop. Running a separate `userbot_listener.py` is redundant if `bot.py` is correctly configured.

## Hypotheses

### Hypothesis 1: Process Consolidation
By consolidating both clients into a single `bot.py` process, we can eliminate the overhead of one Python interpreter and the duplicate loading of shared libraries (Pyrogram, Pydantic, etc.).
- **Expected Gain**: ~40-60MB RAM savings.
- **Complexity**: Low. Requires ensuring all env vars are passed to a single container.

### Hypothesis 2: Docker Optimization
The current `docker-compose.yml` on the VDS seems to differ from the one in the repository, as `docker ps` shows a `tg2book-userbot` container which is not defined in the repo's compose file.
- **Action**: Align the VDS deployment with the repository's single-service architecture.

### Hypothesis 3: Go Rewrite (Long-term)
If memory usage remains above 50MB and becomes a bottleneck, a full rewrite in Go (using `gotd`) would reduce the footprint significantly.
- **Expected Footprint**: 10-20MB for the entire service.
- **Complexity**: High. Requires porting EPUB generation and Dropbox integration.

## Proposed Implementation Plan

### Phase 1: Near-term Optimization (Python)
1.  **Decommission Redundant Service**: Stop and remove the `tg2book-userbot` container.
2.  **Verify `bot.py` configuration**: Ensure `API_ID`, `API_HASH`, and `USERBOT_SESSION_STRING` are correctly set in the environment for the main `tg2book` service.
3.  **Single Entrypoint**: Use `start.sh` (which calls `bot.py`) as the only entrypoint.
4.  **Logging Tune-up**: Disable `DEBUG` logging for Pyrogram in production to further reduce memory and CPU overhead.

### Phase 2: Performance Monitoring
- Monitor RAM usage after consolidation.
- Check swap usage (currently at 210MB) to see if it decreases.

### Phase 3: Architectural Decision (Go)
- If RAM issues persist, evaluate a Go rewrite for the `bot` and `userbot` logic, keeping the EPUB logic as a separate microservice if porting it is too expensive, or porting it fully for maximum efficiency.

## Conclusion
Consolidating into a single process is the most efficient "quick win". It reduces the system's memory pressure by ~5-6% of total VDS RAM without requiring any code changes, just deployment adjustments.
