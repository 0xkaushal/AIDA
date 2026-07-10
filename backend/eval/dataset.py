"""
Evaluation dataset for AIDA.

Each EvalCase represents one test scenario. The fields are:
  - question:          The question to ask the RAG system.
  - ground_truth:      A reference answer (used for answer relevance scoring).
  - key_facts:         Individual facts that MUST appear in a faithful answer
                       (used for context recall and faithfulness checks).
  - expected_sources:  Filenames that should appear in the retrieved sources.
                       Leave empty if you don't care about a specific file.
  - tags:              Optional labels for filtering runs (e.g. "factual", "multi-hop").

HOW TO EXTEND
-------------
Add EvalCase entries to DATASET below. Upload the corresponding documents to
Pinecone under the same user_id you use when running `run_eval.py`.

Documents must already be indexed in Pinecone before running eval — this
framework does NOT upload documents automatically.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class EvalCase:
    question: str
    ground_truth: str
    key_facts: List[str]
    expected_sources: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Dataset
# Edit this list to match documents you have indexed in your Pinecone instance.
# The placeholder cases below demonstrate the schema — replace with real ones.
# ---------------------------------------------------------------------------

DATASET: List[EvalCase] = [
    EvalCase(
        question="What is Satvik Kaushal's current role and company?",
        ground_truth="Satvik Kaushal is a Principal Software Engineer at Eli Lilly and Company, based in Bengaluru, India.",
        key_facts=[
            "Principal Software Engineer",
            "Eli Lilly",
        ],
        expected_sources=["Satvik_Kaushal.pdf"],
        tags=["factual", "experience"],
    ),
    EvalCase(
        question="What AI and agentic skills does Satvik have?",
        ground_truth="Satvik has skills in production LLM applications, agentic workflows, MCP (Model Context Protocol), RAG, Azure OpenAI, LangChain/LangGraph, prompt engineering, embeddings, and vector databases.",
        key_facts=[
            "LLM",
            "agentic",
            "MCP",
            "RAG",
            "Azure OpenAI",
        ],
        expected_sources=["Satvik_Kaushal.pdf"],
        tags=["factual", "skills"],
    ),
    EvalCase(
        question="What was the AIDA project and what impact did it have?",
        ground_truth="AIDA was an agentic AI drafting assistant using Azure OpenAI with multi-step reasoning and LLM-driven DOCX generation. It reduced Japanese PSR document turnaround from 3-4 weeks to 2-3 days. Satvik led a team of four full-stack engineers on this project and won the Lilly Innovator Award for it in 2025.",
        key_facts=[
            "AIDA",
            "Azure OpenAI",
            "3 - 4 weeks to 2 - 3 days",
            "Lilly Innovator Award",
        ],
        expected_sources=["Satvik_Kaushal.pdf"],
        tags=["factual", "impact"],
    ),
    EvalCase(
        question="What cloud platforms and infrastructure tools does Satvik work with?",
        ground_truth="Satvik works with AWS (Lambda, ECS Fargate, EKS, Glue, Step Functions, Athena, S3, API Gateway, CloudFront, DynamoDB, EventBridge, CloudFormation, SQS), Docker, Kubernetes, OpenShift, Terraform, and CI/CD pipelines.",
        key_facts=[
            "AWS",
            "Docker",
            "Kubernetes",
            "Terraform",
        ],
        expected_sources=["Satvik_Kaushal.pdf"],
        tags=["factual", "skills"],
    ),
    EvalCase(
        question="Where did Satvik study and what degree does he hold?",
        ground_truth="Satvik holds a B.Tech in Electronics & Communication Engineering from Raghu Engineering College (JNTU Kakinada), Visakhapatnam, completed in April 2019.",
        key_facts=[
            "B Tech",
            "Electronics",
            "Raghu Engineering College",
        ],
        expected_sources=["Satvik_Kaushal.pdf"],
        tags=["factual", "education"],
    ),
]
