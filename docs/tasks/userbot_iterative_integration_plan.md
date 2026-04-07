# TG2Book Userbot Iterative Integration Plan

## Goal

Extend the current working project in `/home/spec/tg2book` with a minimal, reliable userbot-based channel ingestion flow while preserving the existing pipeline:

`Telegram message -> EPUB generation -> Dropbox upload -> PocketBook delivery`

The implementation must proceed in small, verifiable steps. At each step we must know:
- what behavior is currently protected by tests,
- what new behavior is being introduced,
- how we confirm that the old Dropbox delivery path still works.

## Current Code Reality

This plan is based on the current repository state, not on the failed experimental repo.

### What exists now

- `bot.py` contains the main bot built on `python-telegram-bot`.
- The current bot already supports two working entry paths:
  - forwarded text/caption messages -> EPUB -> Dropbox -> summary reply,
  - uploaded `.epub` documents -> Telegram reply + Dropbox upload.
- `epub_functions.py` contains EPUB generation.
- `dropbox_module.py` contains Dropbox upload logic.
- `test_bot.py` contains unit-style tests with mocks.

### What does not exist now

- No userbot in the current repo.
- No persistent storage for monitored channels.
- No end-to-end or black-box tests that validate the Dropbox upload payload using the current repo architecture.
- No test seam for injecting a channel post directly into the existing conversion pipeline.

### Architectural constraint

The failed repo in `/home/spec/work/tg2book` contains useful ideas, but it also introduced a larger refactor and a framework shift. We should not port it wholesale.

## Pareto Recommendation

The most efficient path is **not** to rewrite the current bot around a new architecture.

The most efficient path is:
- keep the current `python-telegram-bot` bot behavior intact,
- extract the existing “text to EPUB to Dropbox to summary” logic into a reusable internal method,
- add a small userbot sidecar that feeds channel messages into that same internal pipeline,
- add channel storage and admin commands only after the core pipeline is protected by tests.

This gives the best risk/reward ratio:
- minimal surface area of change,
- maximum reuse of already working code,
- simpler regression detection.

## Delivery Strategy

We will work in phases. A phase is complete only if:
- code is implemented,
- the new tests for that phase pass,
- previously protected Dropbox behavior still passes.

## Phase 0. Baseline and Safety Net

### Objective

Freeze current behavior with stronger tests before any userbot work starts.

### Why this phase comes first

Right now the project has unit tests, but it does not have a robust black-box safety net for the most important behavior: successful Dropbox delivery of generated EPUB files.

If we change the message flow without improving this protection first, we will not know whether we broke the main product value.

### Work items

1. Audit the current test suite in `test_bot.py` and classify tests into:
   - current bot command behavior,
   - forwarded-message conversion behavior,
   - direct EPUB upload behavior,
   - Dropbox-related behavior.
2. Add black-box style integration tests for the current repo architecture.
3. Add at least these baseline tests:
   - text message -> generated EPUB bytes are uploaded to Dropbox,
   - uploaded EPUB document -> exact file bytes are uploaded to Dropbox,
   - failure in Dropbox upload does not crash the bot silently and produces observable error behavior.
4. Keep external network mocked at HTTP boundary only.
5. Avoid mocking internal EPUB generation when the purpose of the test is pipeline validation.

### Expected output

A new test module, likely under `tests/`, that proves the current Dropbox delivery path still works.

### Exit criteria

- We can say with confidence that the current Dropbox path is protected.
- We have a red/green baseline before any architectural changes.

## Phase 1. Introduce an Internal Processing Seam

### Objective

Refactor the current bot minimally so that both manual forwarded messages and future channel posts can use the same internal processing path.

### Why this is the right next step

Today the conversion and Dropbox logic is embedded inside `TelegramToEpub.handle_message()` in `bot.py`. That makes later userbot integration harder and encourages duplication.

The first internal refactor should create a shared seam without changing user-visible behavior.

### Work items

1. Extract the current text-processing flow into an internal method, for example:
   - `_process_text_to_dropbox(...)`, or
   - `_build_and_upload_epub(...)`.
2. The extracted method should accept explicit inputs such as:
   - raw text,
   - source name,
   - source link,
   - reply target or summary target,
   - whether the source message should be deleted afterward.
3. Keep current `handle_message()` behavior unchanged from the user perspective.
4. Add focused tests for the extracted method.

### Exit criteria

- No visible regression in current bot behavior.
- The core pipeline becomes callable from another future source, not only from forwarded bot messages.

## Phase 2. Add Channel Registry Storage

### Objective

Implement persistent storage for the list of monitored channels.

### Recommendation

Use a tiny SQLite-backed module instead of environment variables or ad hoc files.

Reasoning:
- channel membership is state, not config,
- add/remove operations should survive restart,
- SQLite is enough and keeps complexity low.

### Work items

1. Add a small module such as `channel_registry.py` or `userbot_db.py`.
2. Implement operations:
   - `init_db()`
   - `add_channel(identifier)`
   - `remove_channel(identifier)`
   - `get_channels()`
3. Decide what identifiers we store.

### Storage recommendation

Store normalized channel identifiers as strings. Support:
- public usernames like `testchannel`,
- numeric channel IDs like `-100...`.

Do not over-engineer the schema in the first iteration.

### Tests

Add tests for:
- add new channel,
- reject duplicate add,
- remove existing channel,
- remove unknown channel,
- list channels in stable order.

### Safety check

Run the Phase 0 baseline tests after storage is added, even though storage does not touch Dropbox directly.

### Exit criteria

- Channel registry persists across process restarts.
- Storage layer is independently tested.
- Existing Dropbox pipeline still passes baseline checks.

## Phase 3. Add Admin Commands for Channel Management

### Objective

Allow explicit management of monitored channels from Telegram.

### Scope for first iteration

Support only the minimal command set:
- `/add_channel <channel>`
- `/del_channel <channel>`
- `/list_channels`

### Architectural recommendation

Keep these commands in the existing main bot.

Reasoning:
- the bot already has a direct chat with the operator,
- no need for a separate admin UI,
- lower operational complexity.

### Access control

Introduce an admin gate before these commands are active.

### Minimal configuration needed

Add `ADMIN_ID` to environment/config handling.

### Work items

1. Define how configuration is loaded.
2. Add command handlers to `bot.py` or a small adjacent module.
3. Wire the handlers to the storage layer.
4. Return clear Russian-language success and error messages.

### Tests

Add tests for:
- admin can add channel,
- admin can delete channel,
- admin can list channels,
- non-admin cannot mutate channel list,
- invalid command arguments are rejected.

### Safety check

Run all previous Dropbox baseline tests again.

### Exit criteria

- Channels can be managed from the bot chat.
- Unauthorized users cannot change the registry.
- No regression in current bot behavior.

## Phase 4. Add a Mock Channel Injection Path

### Objective

Simulate channel ingestion before introducing a real Telegram userbot session.

### Why this is better than starting with a real channel

A mock ingestion seam lets us validate the architecture locally and deterministically before any Telegram account/session complexity is added.

This is a better Pareto step than jumping directly to a real userbot:
- faster feedback,
- no dependency on Telegram account state,
- easier to debug.

### Recommended approach

Do not create a fake full Telegram service.

Instead, add a small internal method such as:
- `enqueue_channel_post(...)`, or
- `process_channel_post(...)`

Then test it using plain Python objects/mocks.

### Work items

1. Define a minimal internal representation of an ingested channel post:
   - text,
   - source name,
   - source username or numeric ID,
   - post link if available.
2. Route this representation into the shared processing seam created in Phase 1.
3. Add tests that simulate:
   - a valid channel post with text,
   - a channel post without text that should be skipped,
   - a monitored channel post producing Dropbox upload and summary delivery.

### Terminology note

In implementation and tests, use “mock channel post” or “simulated channel update”, not a broad “mock channel”. The object being mocked is the incoming post/update, not Telegram itself.

### Safety check

Run all Phase 0 baseline tests after this phase.

### Exit criteria

- We can prove that channel-originated content can reuse the existing processing path.
- No real Telegram user account is required yet.

## Phase 5. Introduce the Real Userbot Listener

### Objective

Add a real userbot that listens to selected channels and forwards eligible posts into the shared pipeline.

### Minimal architecture

Use the current bot as the user-facing bot, and add a separate userbot listener component.

Recommended shape for iteration one:
- keep `python-telegram-bot` for the main bot,
- add a separate userbot client process/component,
- deliver channel posts into the shared application code in-process if practical,
- otherwise run both under one async process only if the operational model stays simple.

### Important architectural choice

Do not replace the main bot framework just to add userbot support.

That would create excessive migration risk. The userbot should be an additive component, not a rewrite trigger.

### Work items

1. Choose the userbot library deliberately.
2. Add minimal configuration for:
   - `API_ID`
   - `API_HASH`
   - session storage or session string
3. Build a userbot startup path.
4. On each incoming channel post:
   - check whether the channel is registered,
   - extract text or caption,
   - build source metadata,
   - call the shared processing seam.
5. Start with one supported happy path only:
   - text posts from a public or known test channel.

### Recommendation on libraries

Do not decide this phase from habit. Compare options against the current project needs:
- session stability,
- async compatibility,
- channel update handling,
- operational simplicity.

If one library clearly minimizes glue code and operational fragility, prefer it even if it differs from the failed prototype.

### Tests

Add local tests around:
- filtering monitored vs unmonitored channel messages,
- building source metadata from incoming userbot messages,
- skipping empty posts,
- routing qualifying posts into the shared pipeline.

### Safety check

Phase 0 Dropbox baseline must still pass unchanged.

### Exit criteria

- A real userbot session can listen to one configured channel.
- One real post can flow through to Dropbox successfully.
- Existing manual forwarding flow remains intact.

## Phase 6. Controlled Real-Channel Validation

### Objective

Validate the first real channel end-to-end under controlled conditions.

### Recommended rollout order

1. Personal test channel.
2. Wife’s channel, if easier operationally.
3. One real target channel after confidence is established.

This order is safer than starting with a third-party production channel because it reduces ambiguity during debugging.

### Manual validation checklist

For one known test post, verify:
- userbot sees the post,
- channel filter accepts it,
- text enters the shared processing seam,
- EPUB is generated,
- Dropbox upload succeeds,
- file reaches PocketBook destination,
- summary/notification path behaves as expected.

### Observability requirement

Before this phase, add enough logging to answer:
- did the userbot receive the update,
- did filtering reject it,
- did EPUB generation fail,
- did Dropbox upload fail.

### Exit criteria

- One real channel works end-to-end.
- Failure points are visible in logs.

## Phase 7. Remove Temporary Mock-Only Scaffolding

### Objective

Remove any temporary test-only scaffolding that is no longer needed after real userbot validation.

### Guidance

Do not remove useful internal seams that improve testability.

Remove only scaffolding that exists solely for transitional experimentation.

### Exit criteria

- The production path stays clean.
- Tests remain stable and meaningful.

## Phase 8. Harden for Ongoing Use

### Objective

Make the first iteration robust enough for everyday use.

### Work items

1. Add restart-safe startup checks.
2. Improve logging around userbot session issues.
3. Decide how to handle duplicate channel posts.
4. Decide whether edited channel posts should be ignored or reprocessed.
5. Decide whether media-only posts are out of scope for iteration one.

### Recommended non-goals for iteration one

To keep scope under control, defer these unless they are required immediately:
- media extraction from channel posts,
- complex deduplication,
- batching multiple posts into one EPUB,
- historical backfill,
- broad rewrite of the bot architecture.

## Proposed File-Level Evolution

This is the most likely minimal shape, assuming we preserve the current codebase style:

- `bot.py`
  - keep existing bot handlers,
  - extract shared processing seam,
  - later add admin commands or thin wiring to them.
- `dropbox_module.py`
  - keep existing Dropbox logic stable; adjust only if tests reveal a defect.
- `epub_functions.py`
  - keep stable except for bug fixes needed by baseline tests.
- `channel_registry.py` or `userbot_db.py`
  - new persistent storage for monitored channels.
- `userbot_listener.py` or similar
  - new additive component for real channel ingestion.
- `tests/`
  - add black-box Dropbox pipeline tests,
  - add storage tests,
  - add channel-ingestion tests.

## Validation Matrix Per Phase

For every phase after Phase 0, run at least:

1. Existing unit tests.
2. New tests introduced in that phase.
3. Dropbox baseline tests from Phase 0.

If a phase changes message routing logic, also run:
4. Manual smoke check for the current forwarded-message path.

## Risks and Mitigations

### Risk: rewriting too much too early
Mitigation: keep the current main bot architecture and add only small seams.

### Risk: Dropbox path regresses silently
Mitigation: add black-box pipeline tests before userbot work.

### Risk: userbot complexity dominates the project
Mitigation: introduce mock/simulated channel ingestion before real Telegram session handling.

### Risk: config sprawl and fragile startup
Mitigation: add new environment variables only when the phase actually needs them.

### Risk: mixed responsibilities inside `bot.py`
Mitigation: extract shared logic incrementally instead of forcing a full module split immediately.

## Recommended First Implementation Slice

The best first implementation slice is:

1. Add black-box Dropbox pipeline tests for the current repo.
2. Extract a shared internal processing method from `handle_message()`.
3. Add persistent channel registry with tests.

This slice provides the highest leverage:
- it strengthens the current product,
- it creates the seam needed for userbot integration,
- it does not yet depend on Telegram userbot sessions.

## Definition of Success for Iteration One

Iteration one is successful if all of the following are true:

- Manual forwarded-message workflow still works.
- Dropbox delivery is protected by black-box tests.
- Channels can be added and removed safely.
- A simulated channel post can reuse the real EPUB + Dropbox pipeline.
- One real channel can be connected and verified end-to-end.

## Notes for Implementation Discipline

- Prefer additive changes over framework replacement.
- Avoid importing large chunks from `/home/spec/work/tg2book` without re-justifying each piece.
- Every phase should leave the system in a deployable state.
- If a step cannot be validated locally, write down the exact missing prerequisite before proceeding.
