# qa-portfolio-pipeline

Orchestrates the CI/CD pipelines of all 5 portfolio repositories in sequential phases, triggered by a single manual dispatch. Demonstrates multi-repository pipeline design with phased execution and cost-aware AI test triggering.

## Tech Stack

- GitHub Actions
- [`the-actions-org/workflow-dispatch@v4`](https://github.com/the-actions-org/workflow-dispatch) (remote workflow triggering with wait-for-completion)

## How It Works

This repository contains no application code of its own. It's a single orchestrator workflow (`orchestrator.yml`) that, when manually triggered, runs the CI pipelines of the other 5 portfolio repositories in two phases:

**Phase 1: Traditional QA (parallel)**
- `calculator-playwright`
- `saucedemo-playwright`
- `restful-booker-restassured`

These three run at the same time, since they're independent of each other and of the AI repositories.

**Phase 2: AI QA (parallel, mock only)**
- `llm-test-case-generator` (`ci-mock.yml`)
- `llm-as-judge` (`ci-mock.yml`)

Phase 2 only starts after every repository in Phase 1 has completed. It deliberately triggers only the mock CI workflows of the AI repositories, never the live ones, so running the full orchestrator never spends real OpenAI API tokens. The live workflows remain a separate, manually-triggered decision made independently in each AI repository.

## Running It

1. Go to the **Actions** tab of this repository.
2. Select **Portfolio Pipeline Orchestrator**.
3. Click **Run workflow**.

Each matrix job in the Actions tab shows the live status of its corresponding repository's CI run, since the action polls the remote workflow until completion.

## Architecture Decisions

**Why a fine-grained Personal Access Token instead of the default `GITHUB_TOKEN`:** the automatic `GITHUB_TOKEN` a workflow receives is scoped only to the repository it runs in. Triggering a `workflow_dispatch` event in a different repository requires a token with access across repositories. A fine-grained PAT, scoped only to these 5 repositories with "Actions: Read and write" permission, was chosen over a classic PAT to follow the principle of least privilege: if it were ever compromised, the damage is limited to triggering workflows in exactly these 5 repositories, nothing else.

**Why `workflow_dispatch` was added to every individual repository's CI workflow:** remotely triggering a workflow via the API requires that workflow to declare `workflow_dispatch` as one of its triggers. This was added alongside the existing `push`/`pull_request` triggers in all 5 repositories, so each CI continues to run automatically on every push, in addition to being triggerable remotely by this orchestrator.

**Why phases instead of running all 5 in parallel:** phased execution mirrors how a real-world pipeline would be structured when later stages depend on earlier ones succeeding (for example, only running expensive AI evaluation after core application tests pass). Even though these 5 repositories don't have a strict technical dependency on each other today, the phased design demonstrates the same pattern that would apply if, for example, Phase 2 needed an artifact produced by Phase 1.

## Known Limitations

- **Run identification relies on the latest run of the target workflow**, matched by workflow name and timestamp, rather than a unique run identifier passed at dispatch time. In practice, this means if a workflow in one of the 5 repositories is triggered manually (from within that repository) at the exact same moment the orchestrator dispatches it, there's a small chance the orchestrator could poll the wrong run. This risk is negligible for this portfolio's usage pattern (the orchestrator is run standalone, not concurrently with manual runs), but a production-grade implementation would pass a unique `run-name` at dispatch time and have each target workflow echo it back, to guarantee the correct run is polled every time.
- The orchestrator has no retry logic: if a phase fails, the pipeline stops and must be re-run manually from the start, rather than resuming from the failed phase.
- Only the mock CI of the AI repositories is included in the orchestrator by design (see "How It Works"); triggering the live, real-API workflows remains a manual, cost-conscious decision made per repository.