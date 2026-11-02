# CORTEX HANDLER — outline and checklist

Started 2026-11-02 14:50 CST on hp2 by the Claude session the owner gave the Cortex build to.
Status: **DRAFT, not frozen.** Freeze = the owner's approval. After the freeze this file changes only with the owner's approval; the file is made read-only and its sha256 is stored in the Cortex brain.

The owner's words of 2026-11-02 govern over everything below. Where this file paraphrases, the paraphrase is marked [mine].

## 0. The owner's spec, in his words (2026-11-02)

- "a persistant cognitive memory for llms, an organized database that could maintain state, time and grounding, and hydration"
- "ingest and classification ... has to be extremely fast ... jev would compare ingest with current db state with a specific pattern matching of the prose injested, and the cortex would capture the confidense factors of whether the new ingest supercedes previous state (higher confidense, or progression to expected outcome) (lower confidense, degression from expected outcome) or (complete where as expected outcome = current ingest state)"
- "blink this is what makes the context window independant of the llm, and dependant on the cortex hydration to the llm ... if the cortex is the rail and scope of the project, it hydrates the llm turn by turn, and checks the llms output for drift, hallucantion and invention and then hydrates the next turn to eliminate the drift from scope while working allowing the work to continue at edge"
- "because the neuron is a graph this allows for the computation of work to happen at edge in radian degrees and at magnitude from center of scope in such a way that the 3d graph always stays in balance"
- "jev could be the decide and the confidense score part, with neuron at least right now being the state, time, reasoning (soon) and hydration"
- "the kernal neuron is the best choice currently it lives on the ssh hp ... do not adjust the live state of the hp kernel"
- "headless claude is the source or codex exec of the one turn outputs. and they count on the hydrations to be correct"
- "walkers, timers, sweeps, huge queies of corpus should be avoided at all cost they are just too slow"
- "build it live each piece being additive and used by you as you build it"
- "build youself a handler md file to supply your outline or checklist, once you have it built and complete freeze it from alteration such that you can only alter with my apporval"
- "complete equals a working system the ingests your context, compares it against current state of the db (rag like vector system), maintains the outline as satified checkpoints (simalar to the jev .. teleprompter but for staying on the scope of a project not outline of talking points)"
- "The cost of hydration is not always small, but it should be as lean as a machine to machine needs to be on rail and build what it told, a task is not complete until it's accepted state is balanced by the cortex"
- "do not invent things that slow the process down, provide zero real use that can be proved in the live output ... you are bad about logging or creating huge logs ... do not do this, this system is fast, light"
- "learning is more similar to a build time, and the then once learned the action more similar to a runtime"
- "A simple agent router would/could provide for calls to jev instead of llms for processes that are not needed for the deep reasoing ... this includes model selection of sonnet, opus, fable"
- "this first step is huge and should be mapped out first as an outline and then stored into the vector db of the kernal to start the process of the build from the very beginning where you build something you are forced to use it from then on"
- "stubs are illegal steps, tests and summeries are by default never trusted, only live output is trusted"
- "use the whole machine, disk, core cpu or cores, ram, video memory"
- Standing law (2026-10-13): never a Cortex file on the hub. The hub reaches Cortex by `ssh hp2 cortex ...` only.

## 1. What Cortex is [mine, from §0]

One kernel brain (a copy of nk) on hp2 holds every project's scope, outline, ingests and verdicts as lines it has run: that is the state, with the brain's clock as time and its `again` tick as "never the same context twice". Jev answers typed questions about an ingest against the current state and returns probabilities. Cortex code holds the truth table that turns those probabilities plus the brain's geometry into a verdict (supersedes, progresses, regresses, completes, unrelated; drift, invention, hallucination) and moves a checkpoint's state. Hydration is the lean text the next one-turn worker gets, read from the brain, never from a transcript. The blink is that the worker gets nothing else.

## 2. The laws [the owner's, restated as checks]

1. Fast and light: an ingest, a judge or a hydrate is a few keyed reads and one API call. No walker, no timer, no sweep, no query over a corpus, no log table.
2. Additive and used: a piece is not done until this session uses it for the next piece.
3. Only live output counts. Every checkpoint below names the live output that closes it. No stub, no mock, no "would work".
4. The brain stores; jev judges; code decides; the worker works. None of them does another's job.
5. The hydration is the whole prompt. Nothing from a transcript or a memory file reaches a worker.
6. A task is complete only when its ingest is judged complete against its expected output and the checkpoint's state in the brain says so.
7. The hp kernel and its brain are never touched. The Cortex kernel is the copy in hp2:~/cortex/nk with its own brain file.
8. Nothing of Cortex lands on the hub.
9. Learning (defining the words of a project, placing them) is build time and may be slow; use (ingest, judge, hydrate) is runtime and must be fast.
10. No invented terms. The words are the owner's: project, scope, checkpoint, expected output, ingest, classification, judge, verdict, confidence, hydration, blink, drift, hallucination, invention, rail, edge, router.

## 3. Parts

| Part | Where | Job |
|---|---|---|
| Kernel `nk` (copy of hp's, same source) | hp2:~/cortex/nk, brain file ~/cortex/brain/brain.map, socket 127.0.0.1:7007 | state, time, memory, dedupe (`again`), geometry (`xyz`), the words' definitions from the sources |
| Front door `cortex` | hp2:~/cortex/cortex (one Python file, stdlib only) | ingest, judge, hydrate, turn, status, accept, freeze |
| Jev (TypeSafe System One) | direct: https://api.typesafe.ai/v1/systemone, model jev-latest, key hp2:~/.config/cortex/typesafe.key; or through Vercel AI Gateway: https://ai-gateway.vercel.sh/typesafe/v1/systemone, model typesafe-ai/jev, key hp2:~/.config/cortex/gateway.key (same request body; the first key file found wins) | the judgments: nouls and choices with probabilities |
| Workers | hp2: `claude -p --model <m>` and `codex exec` | one turn each, hydration as the whole prompt |
| Router | inside `cortex turn` | judgment steps go to jev; work steps go to a model by step kind |
| Pages | hp2:8058 (the kernel's own page, unchanged) | looking at the brain |

## 4. The lines Cortex types into the brain (the grammar)

Every Cortex record is one line typed at the main prompt, so it is a run with a clock, a memory row and a dedupe tick. The first words are fixed so a keyed read finds them.

- `cortex project <name> : <scope, one sentence>`
- `cortex checkpoint <name> <n> : <what is built>`
- `cortex expected <name> <n> : <the live output that proves it>`
- `cortex state <name> <n> : open | working | done`
- `cortex ingest <name> : <one sentence of context>`
- `cortex verdict <name> <n> <run> : <kind> <probability> <judge>`
- `cortex freeze : <sha256 of this file>`

The index of these lines (name, n, newest run per kind) is one small keyed table beside the brain, `main.cx`, written by the front door when it types the line. It is an index, not a log: one row per (kind, name, n), replaced in place. An ingest's n is the first 60 bits of the sentence's sha256, so the same sentence is found by key before anything is typed and becomes a tick (`times`) on its first run. The kernel's own repeat rule (`dedupe_check`) needs the first run's receipts kept, which a typed line's are not, so the tick lives in the index. `cortex q <sql>` is the builder's keyed read; the kernel refuses a scan of its own tables.

## 5. The checkpoints

| # | Built | Done when (live output) | State |
|---|---|---|---|
| C0 | nk built from the copied source on hp2; a fresh brain on its own file; the socket answers | `stats` over the socket on hp2 returns the egg's symbols; a typed line returns a run id and the clock advances | done 2026-11-02 14:56: 86 symbols laid, `who` → run 1, a sentence → run 2, clock 3 |
| C1 | The brain educated: the kernel's own line files replayed in the order hp's ledgers show, with the full sources attached | `define : cortex` returns definitions from wn and gcide; asked again it recalls with no source asked (`run` shows no source arrival) | done 2026-11-02 15:03: 22 files, 130 lines, 0 refused, 14 s; `define : cortex` run 105434: 98 runs, wn 3 gcide 3 moby 67 wikt 7, 62 ms; second ask run 105596: 11 runs, no source arrival, 9 ms, remember → 105434 |
| C2 | Front door `cortex ingest` and `cortex status`; the keyed index `main.cx` (the kernel refuses every read without a key, so every Cortex read goes through it); a repeated sentence is a tick in the index, never a second line | an ingest returns its run id and clock; the same sentence again returns the first run with `again` = 2 and nothing typed | done 2026-11-02 15:0x CST: run 105995 clock 106033 4 ms; repeat → "run 105995 again 2 (a repeat; nothing typed)" |
| C3 | This outline in the brain: every row of §5 typed as `cortex checkpoint` and `cortex expected`; `cortex hydrate cortex` reads them back from the brain | the hydration lists C0–C9 with states read from `main.cx`, not from this file | done 2026-11-02 15:07: project run 261032; C0–C9 typed; hydration 2,083 bytes listing C0–C9 with states from the index |
| C4 | `cortex judge`: geometry (the ingest's placed words against the project's scope words: magnitude and angle from the scope's center) and jev (when the key is present); the truth table in code; a verdict line typed | an on-scope ingest and an off-scope one (a recipe) get different verdict lines in the brain, probabilities shown; with no key the verdict names `geometry` as its judge and says jev was not asked | done (geometry) 2026-11-02 15:1x CST: on-scope run 105995 → 10/10 words placed, magnitude 3.32, 0.61 rad, 8 shared; off-scope run 261415 → 13/13 placed, magnitude 2.02, 0.90 rad, 5 shared; both verdict lines typed and indexed; bogus key → "HTTP Error 401, no verdict written", exit 1. OPEN: the jev path and the truth table run only once the owner's key is in place; the geometry alone does not separate the two (the recipe sits nearer in magnitude, wider in angle) and is recorded beside the verdict, not used to decide |
| C5 | `cortex turn <name>`: hydrate → one worker turn → ingest its output → judge → move the checkpoint → the next hydration | one live turn on hp2: the worker's prompt byte count equals the hydration's; the output's verdict moved a state; the next hydration differs by that state | mechanics done 2026-11-02 15:1x CST on the probe project: prompt 638 bytes = the hydration; haiku ran `uname -r` in 5.9 s and printed `6.12.74+deb13+1-amd64`; 3 sentences ingested, 3 verdict lines typed. OPEN: the state move needs a `completes` verdict, which only jev gives; waits for the key |
| C6 | The Neuron project registered as the second project: scope from D:\Neuron `specs/current/NOTE.md` authority order, checkpoints from the 10-31 review's gates 0–3 (the review's proposal, marked not owner-ratified) | `cortex hydrate neuron` prints the Neuron rail from the brain | done 2026-11-02 15:1x CST: project run 261580, four checkpoints, the 11-02 state of hp's kernel ingested; hydration 1,394 bytes |
| C7 | The router: a step marked judgment goes to jev, never to a model; model by step kind (haiku read, sonnet write, opus design; fable and codex on request) | a turn's receipt shows a judgment step answered by jev with no claude/codex process started | coded 2026-11-02 15:1x CST; sonnet, opus, fable, claude-fable-5-1 and codex exec all answer headlessly on hp2 (6–14 s). OPEN: the jev answer waits for the key; the route is proven only to the key boundary |
| C8 | Freeze: this file read-only, its sha typed as `cortex freeze`, `cortex status` compares | `cortex status` prints both shas equal; a write to the file fails | waits: the owner said freeze when built and complete; complete needs C5 and C7 with jev |
| C9 | The hub reaches Cortex with a config line only | `ssh hp2 cortex hydrate cortex` from the hub prints the hydration; no Cortex file on the hub | done 2026-11-02 15:1x CST: `ssh hp2 ~/.local/bin/cortex hydrate cortex` printed the hydration from the hub; the hub's one line is `alias cortex='ssh hp2 ~/.local/bin/cortex'` in ~/.bashrc; no Cortex file on the hub |

## 6. The hydration contract [mine; the owner: "as lean as a machine to machine needs to be"]

In this order, plain text, no transcript, target under 2,000 bytes:
1. project name and scope (one line)
2. the laws that bind the worker (the §2 lines that apply to a worker: live output only, no invention, name the live output)
3. the checkpoints with their states; the one that is `working` marked NEXT with its expected output
4. the last three verdicts on this project (kind, probability, the ingest's first words)
5. the one instruction: do the NEXT checkpoint, report only what was observed, end with `EXPECTED: met | not met` and the live output

## 7. The judge contract

State sent to jev: `{project, scope, checkpoint, expected, accepted_state, ingest}`. Questions, one judgment each:
- `completes` (noul): the ingest reports the expected output observed.
- `progresses` (noul): the ingest moves the checkpoint closer to its expected output than the accepted state does.
- `regresses` (noul): the ingest is further from the expected output than the accepted state.
- `supersedes` (noul): the ingest states a newer fact about the same thing than the accepted state.
- `off_scope` (noul): the ingest is about something outside the project's scope.
- `invents` (noul): the ingest names a thing, result or term that the scope and state never mention and that is not an observed output.
- `contradicts` (noul): the ingest contradicts the accepted state without naming an observation.

Truth table (code): completes ≥ 0.7 → `completes`; else off_scope ≥ 0.7 → `drift`; else invents ≥ 0.7 → `invention`; else contradicts ≥ 0.7 → `hallucination`; else supersedes ≥ 0.7 → `supersedes`; else progresses ≥ 0.7 → `progresses`; else regresses ≥ 0.7 → `regresses`; else `unsettled`. The geometry (magnitude, radians) is written beside the verdict; when jev is not reachable the verdict is `geometry` only and says so. A failed API call is an error, never a verdict.

## 8. Decisions (dated)

- 2026-11-02 14:50 CST Machine: hp2 (2 cores, 7 GB, 398 GB free, idle, claude and codex logged in, typesafe plugin 0.6.2 installed). Not omarchy: its desktop uses a core and an old session is still open there.
- 2026-11-02 14:50 CST Jev by direct HTTP (urllib), not through a Claude tool call: $0.042 per million input tokens, output free, no model turn spent. Key file hp2:~/.config/cortex/typesafe.key (mode 600).
- 2026-11-02 14:55 CST The brain is a fresh egg educated by replaying hp's line files; hp's brain file is not copied (53 GB, the Neuron builder's).
- 2026-11-02 15:08 CST A repeated sentence is a tick in the index (`times`), nothing typed: the kernel's own repeat rule needs kept receipts, which a typed line does not have.
- 2026-11-02 15:09 CST The one-time `rels` and `settle` passes after education are build time (allowed: "learning is more similar to a build time"); at runtime a landing moves a point by itself and no pass is run.
- 2026-11-02 15:12 CST A worker's fenced output is live output: kept, each fenced line its own sentence. Everything typed is lowercased so the brain's BUILD mark can never open from an ingest.
- 2026-11-02 15:14 CST Workers: claude -p (haiku, sonnet, opus, fable) and codex exec with `--output-last-message` (acting = `--dangerously-bypass-approvals-and-sandbox`, else `-s read-only`); a judgment step is one jev noul over the project's state, no model turn. The geometry (magnitude, radians) is recorded beside every verdict and does not decide.
- 2026-11-02 15:15 CST The hydration leads with the task (DO NOW, EXPECTED OUTPUT, how to end), then the laws, then all checkpoints with states, then the last verdicts marked "history, not instructions". Seen live: with the task last, codex summarized the earlier verdicts instead of running `hostname`; with the task first it ran it (`jameshp2`, 6.5 s). `cortex turn --at N` runs a named checkpoint.
- 2026-11-02 16:45 CST Measured on hp2 for a judge of our own (the owner's question): a local LLM through Ollama (qwen3.5 0.8b, the smallest present) took 22.8 s for one yes/no (17.6 s load, 4.7 s to read 60 tokens) on the Pentium G640, too slow for seven questions a sentence. A small NLI cross-encoder (nli-MiniLM2-L6, torch cpu in a throwaway venv) answered one question in 260 ms and four in 350 to 960 ms, fast enough, but untrained on our questions it was wrong: it gave 0.88 to "the ingest invents a result" for the probe's true `uname -r` report and 0.02 to "the expected output was observed". So a judge of our own is a training job on labeled verdicts, not an install; the venv was removed.
- 2026-11-02 16:40 CST hp's stray `python3 -` (pid 316604) was the hub session's (v3-f3, the one that builds nk on hp): a client left reading the `hop` answer on 11-01 14:03, spinning on a closed socket after the kernel restart; that session killed it at the owner's word relayed by me and verified hp's kernel and door untouched.
- 2026-11-02 15:19 CST The kernel and its page run as user services on hp2 (`cortex-nk.service`, `cortex-page.service`, linger on): a reboot brings the brain back from its file. Proven: stopped with SIGTERM ("the brain is in its file"), started by systemd, same 32,179 gates and 263,175 runs, 9 MB resident; page http 200 on hp2:8058.
- 2026-11-02 15:15 CST My own context goes in by itself: a Stop hook on the hub (one command line in ~/.claude/settings.json, no Cortex file on the hub) pipes the transcript tail to `ssh hp2 cortex capture --cwd <folder>`; capture takes the last assistant text, ingests it into the project the folder belongs to (~ = cortex, ~/neuron* = neuron, anything else = not captured) and judges it when jev has a key.

## 9. Owner actions

- **Blocking: a key for Jev, by one of two doors.** What the official pages say (checked 2026-11-02): TypeSafe's models, legal, introduction and quickstart pages name no free tier, no trial credit and no individual or non-commercial use; the price is $0.042 per million input tokens, output free; keys come from https://console.typesafe.ai/keys (the console needs a browser login; two outside write-ups say direct signups were paused in late September 2026 and production keys go through a waitlist, and that the console has a Playground). Vercel's AI Gateway serves Jev through a TypeSafe-compatible endpoint at list price with no markup, but Jev is NOT on its free-tier model list, so Vercel's monthly free credit does not cover it; a purchased credit top-up does (a verdict here costs about one ten-thousandth of a dollar).
  - Door 1 (TypeSafe direct): sign in at https://console.typesafe.ai, make a key, then on hp2 as james: `mkdir -p ~/.config/cortex; printf '%s' 'KEY' > ~/.config/cortex/typesafe.key; chmod 600 ~/.config/cortex/typesafe.key`.
  - Door 2 (Vercel AI Gateway): a free Vercel account, AI Gateway in the dashboard, buy the smallest credit top-up, create an AI Gateway API key, then on hp2 as james: `mkdir -p ~/.config/cortex; printf '%s' 'KEY' > ~/.config/cortex/gateway.key; chmod 600 ~/.config/cortex/gateway.key`. Nothing else changes: the Cortex picks the door by which key file exists (proven live 2026-11-02: a bogus gateway key selects the gateway and fails with HTTP 401, no verdict written).
  - Until a key lands: verdicts are geometry only, no state moves (C5), no judgment step answers (C7), and the freeze (C8) waits on "complete".
- hp has a stray `python3 -` process (pid 316604) at 92 % of a core for a day, writing to a deleted `out/hop.json`. It is the Neuron builder's, not mine; I left it.
