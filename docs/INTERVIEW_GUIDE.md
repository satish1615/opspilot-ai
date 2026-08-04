# OpsPilot AI Interview Guide

## Project overview

**Q1. What problem does OpsPilot AI solve?**  
It standardises the first stage of incident triage. It receives monitoring or human incident data, validates it, recommends priority and routing, retrieves safe evidence, stores history, and keeps remediation under human control.

**Q2. What is the complete request flow?**  
Client → FastAPI route → Pydantic validation → analyzer → runbook and history retrieval → SQLAlchemy → SQLite → structured FastAPI response.

**Q3. Why did you build it incrementally?**  
Each sprint produced one testable capability, which reduced debugging risk and helped me understand and explain every component.

## FastAPI and APIs

**Q4. Why FastAPI?**  
It provides typed Python APIs, automatic validation integration, OpenAPI documentation, and strong developer productivity.

**Q5. What does Uvicorn do?**  
Uvicorn is the ASGI server that runs the FastAPI application and handles network requests.

**Q6. Why use POST for alerts?**  
The client creates a new incident-analysis record and sends a request body, so POST is appropriate.

**Q7. Why create `/health`?**  
It lets users or monitoring systems verify both application and database availability.

**Q8. Who creates the response?**  
The endpoint function returns Python data; FastAPI validates and serialises it into the HTTP response.

**Q9. What do 201, 404, 422, and 503 mean here?**  
201 means a record was created, 404 means the incident does not exist, 422 means validation rejected the input, and 503 means the database health check failed.

## Pydantic

**Q10. Why Pydantic?**  
It validates structure, types, lengths, ranges, and allowed values before business logic runs.

**Q11. What happens when validation fails?**  
FastAPI returns a structured 422 error and does not execute the endpoint's analysis or database logic.

**Q12. Why use Literal values?**  
They prevent inconsistent alert types, severities, priorities, and source types from entering the system.

## Analysis logic

**Q13. Is the analyzer an LLM?**  
No. The final release uses transparent deterministic rules so it runs without secrets and every decision can be explained.

**Q14. Why does SERVICE_DOWN use inverse comparison?**  
A lower health value represents failure, unlike CPU or memory where a higher value represents a breach.

**Q15. How is severity calculated?**  
For metric alerts it uses breach ratio and special service-down handling. Human incidents derive severity from P1-P4 priority.

**Q16. How is P1-P4 priority calculated for human incidents?**  
An impact-and-urgency matrix creates the starting priority, then affected-user count and workaround availability adjust it.

**Q17. What is the difference between severity and priority?**  
Severity describes technical seriousness; priority describes how urgently the business should respond after impact and urgency are considered.

**Q18. How is the assignment group recommended?**  
Explicit alert mappings or text keyword groups map the incident to areas such as Network Operations, IAM, Messaging, Database Operations, Infrastructure, or Application Support.

**Q19. What does confidence mean?**  
It is a bounded indicator of how strongly the available rules and keywords support the recommendation. It is not a probability guarantee.

## Retrieval and history

**Q20. Is the runbook feature RAG?**  
It is a lightweight deterministic retrieval layer, not vector-based RAG. It retrieves sanitised runbooks by transparent keyword overlap.

**Q21. How are similar incidents found?**  
The system compares title and description tokens and gives extra weight to matching categories.

**Q22. Why keep retrieval simple?**  
It makes the local demo reproducible, explainable, free of external dependencies, and safe to submit.

## Database

**Q23. What is SQLite?**  
A lightweight relational database stored in one local file.

**Q24. What is SQLAlchemy?**  
A Python toolkit and ORM used to define tables and perform database operations without writing every SQL statement manually.

**Q25. What is the difference between SQLAlchemy and SQLite?**  
SQLite stores the data; SQLAlchemy is the Python layer that communicates with the database.

**Q26. What is a primary key?**  
A unique column identifying one row; OpsPilot AI uses `incident_id`.

**Q27. Why call commit?**  
Commit makes the transaction permanent in the database.

**Q28. Why close sessions?**  
It releases database connections and resources. Context managers ensure closure even when errors occur.

**Q29. Why is PostgreSQL not used now?**  
SQLite is simpler for a local hackathon MVP. The configurable SQLAlchemy layer keeps a future migration possible, but PostgreSQL is not claimed as implemented.

## Testing

**Q30. What types of tests are included?**  
Unit tests verify analyzer rules; API integration tests use FastAPI TestClient and an isolated in-memory SQLite database.

**Q31. Why test threshold equality?**  
Boundary mistakes are common. The test documents that equality counts as a breach for standard metric alerts.

**Q32. Why reset the database for every API test?**  
It prevents one test's records from affecting another test, keeping the suite deterministic.

**Q33. What does GitHub Actions add?**  
It automatically installs dependencies and runs pytest on pull requests and main-branch pushes.

## Safety and production readiness

**Q34. Does the project automatically restart services?**  
No. It records a recommendation and an approval state but never executes operational changes.

**Q35. Why is human approval important?**  
Operational actions can affect availability and data. Human approval creates a clear safety and accountability boundary.

**Q36. What production features are missing?**  
Authentication, RBAC, Alembic migrations, PostgreSQL, secrets management, rate limiting, stronger audit logs, observability, high availability, and enterprise integrations.

**Q37. How did you protect confidential data?**  
The repository uses synthetic examples, ignores environment and database files, and excludes client names, credentials, production logs, hosts, and ticket details.

## Design decisions and learning

**Q38. What was the hardest design decision?**  
Balancing an ambitious AI vision with a small, truthful, testable model. I chose deterministic core behaviour and clearly separated future LLM work.

**Q39. What would you improve next?**  
Add authentication and roles, migrations, PostgreSQL, structured audit events, then an optional LLM adapter with schema validation and deterministic fallback.

**Q40. What did you personally learn?**  
I learned how API validation, analysis logic, database persistence, testing, documentation, Git workflows, and safe system design fit together in one end-to-end backend project.

## One-minute answer

“OpsPilot AI is a FastAPI-based incident-triage platform. It accepts monitoring alerts and human-created incidents, validates them with Pydantic, and applies transparent rules to recommend technical severity, P1-P4 priority, category, assignment group, probable cause, and a safe next action. It retrieves sanitised runbook evidence and similar incidents, stores everything in SQLite through SQLAlchemy, and exposes history, metrics, Swagger documentation, and a dashboard. A human can record remediation approval, but the system deliberately does not execute changes. I built it sprint by sprint and covered the important boundaries with pytest and GitHub Actions.”
