"""Builds a consolidated Teams notification from the results.json of all
5 repositories, classifying any failures as likely automation or functional
issues using simple keyword-based rules."""

import json
import os
import urllib.request

REPOS = [
    "calculator-playwright",
    "saucedemo-playwright",
    "restful-booker-restassured",
    "llm-test-case-generator",
    "llm-as-judge",
]

WEBHOOK_URL = os.environ["TEAMS_WEBHOOK_URL"]
RUN_URL = f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"

AUTOMATION_KEYWORDS = [
    "timeout", "timed out", "connection", "econnrefused", "net::err",
    "no such element", "element not found", "stale element",
    "waiting for selector", "socket hang up", "dns", "certificate",
    "refused", "unreachable",
]


def classify_failure(error_message: str) -> str:
    lowered = error_message.lower()
    for keyword in AUTOMATION_KEYWORDS:
        if keyword in lowered:
            return "Automation issue (infra/flakiness suspected)"
    return "Functional issue (possible product bug)"


def load_results():
    results = []
    for repo in REPOS:
        path = os.path.join("results", repo, "results.json")
        with open(path, "r", encoding="utf-8") as f:
            results.append(json.load(f))
    return results


def build_message(results):
    total = sum(r["total"] for r in results)
    passed = sum(r["passed"] for r in results)
    failed = sum(r["failed"] for r in results)
    pass_rate = round((passed / total) * 100, 1) if total else 0

    all_failures = []
    for r in results:
        for failure in r.get("failures", []):
            all_failures.append({
                "repo": r["repo"],
                "name": failure["name"],
                "classification": classify_failure(failure.get("error_message", "")),
            })

    if failed == 0:
        title = "🟢 QA Portfolio - All repositories passing"
        theme_color = "2EB67D"
        text = "\n\n".join(
            f"**{r['repo']}**: 100% ({r['passed']}/{r['total']})" for r in results
        )
    else:
        title = f"🔴 QA Portfolio - {failed} test(s) failing"
        theme_color = "E01E5A"
        text = "\n\n".join(
            f"**{f['repo']}** - `{f['name']}`\n{f['classification']}" for f in all_failures
        )

    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "summary": "QA Portfolio consolidated test results",
        "themeColor": theme_color,
        "title": title,
        "sections": [
            {
                "facts": [
                    {"name": "Total", "value": str(total)},
                    {"name": "Passed", "value": str(passed)},
                    {"name": "Failed", "value": str(failed)},
                    {"name": "Pass rate", "value": f"{pass_rate}%"},
                ],
                "text": text,
            }
        ],
        "potentialAction": [
            {
                "@type": "OpenUri",
                "name": "View orchestrator run",
                "targets": [{"os": "default", "uri": RUN_URL}],
            }
        ],
    }
    return payload


def main():
    results = load_results()
    payload = build_message(results)

    request = urllib.request.Request(
        WEBHOOK_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        print(f"Teams notification sent, status: {response.status}")


if __name__ == "__main__":
    main()