# Troubleshooting

## Dashboard loads but metric cards and incident history are blank

This can happen after upgrading from the early Sprint 4 database, because that version used an older `incidents` table structure.

The current application handles this automatically at startup:

1. It detects the old table by the presence of `alert_id` and absence of `incident_id`.
2. It renames the old table to `incidents_legacy_<timestamp>_<suffix>`.
3. It creates the final `incidents` table.
4. It keeps the old records preserved in the legacy table rather than deleting them.

After pulling the fix, stop Uvicorn with `Control+C`, restart it, and refresh `/dashboard`.

## Verify the backend

```bash
pytest -q
uvicorn app.main:app --reload
```

Then open:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/dashboard`
- `http://127.0.0.1:8000/docs`

## Inspect preserved legacy tables

This is optional and only for local inspection:

```bash
sqlite3 data/opspilot.db '.tables'
```

Do not delete the legacy table until the hackathon submission and revision are complete.
