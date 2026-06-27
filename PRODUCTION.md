# Production Architecture & Scaling Plan

This document describes what I would change to take AIDA from a local Docker Compose setup to a production-grade deployment on AWS.

---

## Backend

The backend would run on **ECS Fargate behind an Application Load Balancer**. Fargate removes the need to manage EC2 instances and scales horizontally based on CPU/memory. The ALB handles TLS termination, health checks, and distributes traffic across tasks.

As scale increases, the document upload pipeline becomes the right thing to separate out. Uploading, chunking, embedding, and writing to Pinecone is slow and resource-intensive — it does not need to happen in the same process that serves chat requests. I would extract this into **Lambda functions behind API Gateway**: one Lambda to accept the file and write it to S3, and another triggered by the S3 event to do the chunking, embedding, and Pinecone upsert. This decouples upload latency from the main API, makes the pipeline independently scalable, and means a slow PDF does not block a chat request.

---

## Frontend

The frontend would be deployed as a static build on **S3 + CloudFront**. CloudFront handles global CDN distribution, HTTPS, and cache invalidation on each deployment. I would enable **WAF (Web Application Firewall)** on the CloudFront distribution to protect against common threats — SQL injection, XSS, and request flooding — without any application-level changes.

**Authentication** is currently a weak point — the user ID is just a string typed by the user and stored in localStorage. For production I would use **Clerk** (or a similar managed auth provider) to handle sign-up, login, session management, and token issuance. If Clerk is not acceptable for the use case, a custom implementation using JWT + refresh tokens backed by a database is also straightforward. The user ID in the backend would then be derived from a verified token claim rather than a user-supplied string.

For the **chat interface**, WebSockets are worth exploring at scale. The current SSE implementation works well for server-to-client streaming, but WebSockets would enable bidirectional communication — useful if I wanted to support features like server-initiated events (e.g. "your document has finished processing").

---

## Vector Database

Pinecone handles scaling well on its own — it is a managed service and the metadata filtering approach used here (user_id + visibility) works at scale without changes. I would keep Pinecone unless there was a specific requirement to self-host (data residency, cost at very high volume), in which case **pgvector on RDS** or **OpenSearch with k-NN** would be the fallback.

---

## Security & Infrastructure

- **Secrets**: All API keys (OpenRouter, Pinecone) would be stored in **AWS Secrets Manager** and injected at container/Lambda startup — never in environment files or Docker images.
- **Sessions**: Proper session management via Clerk or a custom JWT flow, replacing the current localStorage user ID pattern.
- **Retrieval caching**: If the application serves a specific closed group of users querying the same documents repeatedly, I would add a **cache layer on the retrieval side** (e.g. Redis / ElastiCache). Cache keys would be derived from the question embedding vector (approximate nearest-neighbour bucket) and per-user scope. Cache entries would have a **TTL-based invalidation** strategy — when a user uploads a new document, their cache entries are invalidated so they immediately get answers from the updated index.

---

## What I Would Add With More Time

- Token-aware chunking using `tiktoken` instead of character counting
- Reranking pass after Pinecone retrieval (Cohere Rerank or a cross-encoder)
- Evaluation pipeline using RAGAS to measure retrieval recall and answer faithfulness
- Prometheus metrics + Grafana dashboard (request rate, p95 latency, chunks retrieved per query)
- OpenTelemetry traces to visualise time spent in embed vs. Pinecone vs. LLM per request
- SQLite (or RDS) persistence for the document registry and chat history (currently lost on restart)
- Per-user rate limiting at the API Gateway level to prevent abuse
