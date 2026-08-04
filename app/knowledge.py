"""Small, sanitised runbook knowledge base for evidence-backed recommendations."""

from __future__ import annotations

RUNBOOKS: list[dict] = [
    {
        "runbook_id": "RB-CPU-001",
        "title": "High CPU investigation",
        "keywords": ["cpu", "load", "process", "latency", "slow"],
        "safe_first_steps": [
            "Identify the highest CPU-consuming processes.",
            "Compare the alert time with recent deployments or traffic changes.",
            "Check application logs before restarting any service.",
        ],
    },
    {
        "runbook_id": "RB-MEM-001",
        "title": "High memory investigation",
        "keywords": ["memory", "ram", "leak", "oom", "swap"],
        "safe_first_steps": [
            "Inspect memory-consuming processes and container limits.",
            "Check for out-of-memory events and recent application changes.",
            "Capture evidence before considering a controlled restart.",
        ],
    },
    {
        "runbook_id": "RB-DISK-001",
        "title": "Disk capacity investigation",
        "keywords": ["disk", "storage", "filesystem", "logs", "space"],
        "safe_first_steps": [
            "Identify the filesystem and directories consuming the most space.",
            "Verify log-retention and rotation settings.",
            "Do not delete files until ownership and retention requirements are confirmed.",
        ],
    },
    {
        "runbook_id": "RB-SVC-001",
        "title": "Service unavailable investigation",
        "keywords": ["service", "down", "unavailable", "crash", "timeout", "500"],
        "safe_first_steps": [
            "Confirm service health from more than one signal.",
            "Review service and dependency logs.",
            "Use an approved restart or rollback procedure only after impact is assessed.",
        ],
    },
    {
        "runbook_id": "RB-ACCESS-001",
        "title": "User access and authentication triage",
        "keywords": ["login", "password", "access", "authentication", "mfa", "account"],
        "safe_first_steps": [
            "Confirm the user identity and exact error message.",
            "Check account lock, password expiry, and identity-provider health.",
            "Never request or record the user's password.",
        ],
    },
    {
        "runbook_id": "RB-NET-001",
        "title": "VPN and network connectivity triage",
        "keywords": ["vpn", "network", "connectivity", "dns", "latency", "packet"],
        "safe_first_steps": [
            "Confirm whether the issue affects one user, a site, or multiple regions.",
            "Check VPN gateway, DNS, and network-health indicators.",
            "Collect timestamp and connection-error details for the resolver team.",
        ],
    },
    {
        "runbook_id": "RB-MSG-001",
        "title": "Email and messaging triage",
        "keywords": ["email", "outlook", "mailbox", "message", "smtp"],
        "safe_first_steps": [
            "Check service health and whether send, receive, or both are affected.",
            "Confirm scope across users and locations.",
            "Review queue or connector health without exposing message content.",
        ],
    },
]


def tokenise(text: str) -> set[str]:
    return {
        token.strip(".,:;!?()[]{}\"'").lower()
        for token in text.split()
        if len(token.strip(".,:;!?()[]{}\"'")) >= 3
    }


def retrieve_runbooks(text: str, limit: int = 2) -> list[dict]:
    """Return the most relevant approved runbooks using transparent keyword matching."""

    tokens = tokenise(text)
    ranked: list[tuple[int, dict, list[str]]] = []

    for runbook in RUNBOOKS:
        matched = sorted(tokens.intersection(runbook["keywords"]))
        if matched:
            ranked.append((len(matched), runbook, matched))

    ranked.sort(key=lambda item: (-item[0], item[1]["runbook_id"]))
    return [
        {
            "runbook_id": runbook["runbook_id"],
            "title": runbook["title"],
            "matched_keywords": matched,
            "safe_first_steps": runbook["safe_first_steps"],
        }
        for _, runbook, matched in ranked[:limit]
    ]
