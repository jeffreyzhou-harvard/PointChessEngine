# Model Adapter Protocol

This document defines a future adapter interface for automated model calls. It is documentation/scaffolding only. No real provider calls are implemented here.

## Future Interface

```python
complete(messages, tools=None, response_schema=None)
```

Adapter metadata:

- `model_name`
- `provider`
- token usage
- cost tracking
- latency tracking
- retry/error handling

## Responsibilities

A model adapter should:

- accept structured messages
- optionally expose tools
- optionally validate against a response schema
- return text or structured output
- record token usage
- estimate cost
- record latency
- handle retries and provider errors

## Non-Responsibilities

Model adapters do not:

- decide promotion
- bypass tests
- bypass code review
- directly write to canonical `main`

Champion mode evaluates outputs after candidate branches are created.
