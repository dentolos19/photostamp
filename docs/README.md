# Documentation Guidelines

Write documentation for the next agent or engineer. Keep each file short, factual, and current. Link to code instead of duplicating it.

## Root Files

- [`AGENTS.md`](../AGENTS.md): The index. Holds general instructions, commands, and links to the other documents. Read first, so keep it brief.

## Docs Folder

```text
docs/
|-- README.md
|-- decisions/
|   `-- 0001-<title>.md
|-- guides/
|   `-- <topic>.md
`-- plans/
    `-- <yyyy-mm-dd>-<title>.md
```

- `decisions/`: Architecture decision records. One decision per file, numbered in order with kebab-case titles.
- `guides/`: How-to documents for recurring tasks, such as setup, deployment, and runbooks.
- `plans/`: Specs and plans for work in progress. Delete when the work lands; record any lasting choice as a decision.

## Decisions

- Record a decision when choosing between options, adding or removing a dependency or service, changing architecture, data, or APIs, or deviating from these guidelines.
- Do not rewrite accepted decisions. Supersede them with a new record and update the old status to `Superseded by 0007`.
- Use the template below.

```markdown
# 0001. <Title>

- Status: Proposed | Accepted | Superseded by 0000
- Date: <yyyy-mm-dd>

## Context

The problem and constraints.

## Decision

What was chosen and the alternatives considered.

## Consequences

Trade-offs and follow-up work.
```

## Rules

- Put each document in one place only. Product goes in `PRODUCT.md`, design in `DESIGN.md`, decisions in `docs/decisions/`, how-tos in `docs/guides/`, and everything else is linked from `AGENTS.md`.
- Update the relevant document in the same change as the code it describes.
- Do not add other top-level documents or `docs/` folders without recording a decision.
