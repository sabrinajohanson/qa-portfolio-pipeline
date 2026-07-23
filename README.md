# qa-portfolio-pipeline

Orchestrates the CI/CD pipelines of all 5 portfolio repositories in sequential phases, triggered by a single manual dispatch. Demonstrates multi-repository pipeline design with phased execution, cost-aware AI test triggering, and consolidated reporting with Teams notifications.

**[View the live Consolidated Dashboard](https://sabrinajohanson.github.io/qa-portfolio-pipeline/)**, aggregating the latest test results across all 5 repositories.

## Tech Stack

- GitHub Actions
- [`the-actions-org/workflow-dispatch@v4`](https://github.com/the-actions-org/workflow-dispatch) (remote workflow triggering with wait-for-completion)
- Python (dashboard generation, Teams notification)
- Microsoft Teams (Workflows/webhook notifications)

## How It Works

This repository contains no application code of its own. It's a single orchestrator workflow (`orchestrator.yml`) that, when manually triggered, runs the CI pipelines of the other 5 portfolio repositories in two phases, then builds a consolidated dashboard and sends a Teams notification.

**Phase 1: Traditional QA (parallel)**
- `calculator-playwright`
- `saucedemo-playwright`
- `restful-booker-restassured`

These three run at the same time, since they're independent of each other and of the AI repositories.

**Phase 2: AI QA (parallel, mock only)**
- `llm-test-case-generator` (`ci-mock.yml`)
- `llm-as-judge` (`ci-mock.yml`)

Phase 2 only starts after every repository in Phase 1 has completed. It deliberately triggers only the mock CI workflows of the AI repositories, never the live ones, so running the full orchestrator never spends real OpenAI API tokens. The live workflows remain a separate, manually-triggered decision made independently in each AI repository.

**Consolidated Dashboard**

After all 5 repositories finish, the orchestrator downloads the `results.json` summary produced by each repository's CI (via `actions/download-artifact@v5`, across repositories), aggregates them, and publishes a single dashboard via GitHub Pages, showing total/passed/failed/skipped counts, an overall pass rate, and a per-repository breakdown with links to each repository and its individual Allure Report. When a repository has failing tests, the exact test name and a cleaned-up error message are listed inline.

**Teams Notification**

After generating the dashboard, the orchestrator sends a summary to a Microsoft Teams channel via an incoming webhook:
- If all tests pass, the message shows a per-repository pass percentage (e.g. "calculator-playwright: 100% (23/23)").
- If any test fails, the message lists each failing test by name, along with a rule-based classification: failures whose error message matches infrastructure/flakiness-related keywords (timeout, connection errors, element-not-found, etc.) are flagged as a likely **automation issue**; everything else is flagged as a likely **functional issue** (a possible product bug). This is a simple heuristic, not a definitive diagnosis, it's meant to speed up initial triage, not replace it.

## Running It

1. Go to the **Actions** tab of this repository.
2. Select **Portfolio Pipeline Orchestrator**.
3. Click **Run workflow**.

Each job in the Actions tab shows the live status of its corresponding repository's CI run, since the action polls the remote workflow until completion. Once finished, the updated dashboard is available at the link above, and a summary is posted to the configured Teams channel.

## Architecture Decisions

**Why a fine-grained Personal Access Token instead of the default `GITHUB_TOKEN`:** the automatic `GITHUB_TOKEN` a workflow receives is scoped only to the repository it runs in. Triggering a `workflow_dispatch` event, and downloading artifacts, in a different repository requires a token with access across repositories. A fine-grained PAT, scoped only to these 5 repositories with "Actions: Read and write" permission, was chosen over a classic PAT to follow the principle of least privilege: if it were ever compromised, the damage is limited to triggering workflows and reading artifacts in exactly these 5 repositories, nothing else.

**Why `workflow_dispatch` was added to every individual repository's CI workflow:** remotely triggering a workflow via the API requires that workflow to declare `workflow_dispatch` as one of its triggers. This was added alongside the existing `push`/`pull_request` triggers in all 5 repositories, so each CI continues to run automatically on every push, in addition to being triggerable remotely by this orchestrator.

**Why phases instead of running all 5 in parallel:** phased execution mirrors how a real-world pipeline would be structured when later stages depend on earlier ones succeeding (for example, only running expensive AI evaluation after core application tests pass). Even though these 5 repositories don't have a strict technical dependency on each other today, the phased design demonstrates the same pattern that would apply if, for example, Phase 2 needed an artifact produced by Phase 1.

**Why explicit per-repository jobs instead of a matrix strategy:** an earlier version of this workflow used `strategy: matrix` to dispatch the repositories within each phase. However, job outputs from a matrix strategy are unreliable when multiple matrix combinations run in parallel, only one combination's output value survives, the rest are lost. Since the consolidated dashboard job needs the exact run ID of each of the 5 individual CI runs, each repository is dispatched from its own explicit job, each declaring its own `run-id` output.

**Why `continue-on-error: true` on each dispatch step:** by default, if a triggered repository's CI fails, the dispatch action reports that as a failure of its own step, which would cascade and block every downstream job, including the consolidated dashboard and the Teams notification, exactly the moment a report is most needed. Each dispatch step tolerates failure at the GitHub Actions level, and lets the dashboard and notification logic interpret real pass/fail status from each repository's own `results.json` instead.

**Why Teams notifications were tested against webhook.site instead of a real Teams channel:** setting this up coincided with Microsoft's retirement of classic Office 365 Connectors in Teams (completed May 2026); the replacement (Workflows, powered by Power Automate) requires a Microsoft 365 work/school account, which a personal Teams account doesn't have. The notification logic was built and validated against [webhook.site](https://webhook.site) (a generic webhook inspector), since it sends a plain HTTP POST with a JSON payload, identical to what a real Teams Workflows webhook expects. Pointing it at a real Teams channel later only requires swapping the `TEAMS_WEBHOOK_URL` secret, no code changes.

## Known Limitations

- **Run identification relies on the `workflow-id` output of the dispatch action**, which internally matches the triggered run by workflow name and timestamp, rather than a unique identifier passed at dispatch time. In practice, this means if a workflow in one of the 5 repositories is triggered manually (from within that repository) at the exact same moment the orchestrator dispatches it, there's a small chance the wrong run could be matched. This risk is negligible for this portfolio's usage pattern (the orchestrator is run standalone, not concurrently with manual runs), but a production-grade implementation would pass a unique `run-name` at dispatch time and have each target workflow echo it back, to guarantee the correct run is polled every time.
- The orchestrator has no retry logic: if a phase fails, the pipeline stops and must be re-run manually from the start, rather than resuming from the failed phase.
- Only the mock CI of the AI repositories is included in the orchestrator by design (see "How It Works"); triggering the live, real-API workflows remains a manual, cost-conscious decision made per repository.
- The automation-vs-functional failure classification is a simple keyword heuristic, not a definitive diagnosis. It's meant to speed up initial triage (pointing a human toward the more likely cause first), not to replace investigation of the actual failure.