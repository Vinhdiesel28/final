# Task-specific clarification for test selection

Personal questions such as "Tôi đi xét nghiệm gì bây giờ?" route to
`testing_guidance`, even when the form includes a complete prediction profile.
They first ask for purpose, symptoms and previous results. They never require
the user to already know HbA1c/glucose to ask about testing.

The response includes `clarification.questions` and `requested_fields`.
The web shows a follow-up form; its Continue button resends the original request
with `testing_context`. No server conversation history or patient data is stored
in the shared KB. A new question starts a new context.

API continuation example:

```json
{
  "question": "Tôi đi xét nghiệm gì bây giờ?",
  "mode": "multi",
  "testing_context": {
    "purpose": "first_screening",
    "symptoms": "không có",
    "prior_results": "chưa xét nghiệm"
  }
}
```

Purpose values: `first_screening`, `repeat_abnormal`, `followup`.
An unknown/absent value or empty response asks clarification again. The resumed
flow retrieves general evidence appropriate to the purpose; it does not generate
a personalized test order or silently run the diabetes model.

When generation is rejected, the final Critic challenges ReviewAgent to update
the response status. ExplanationAgent then returns a verified notice instead of
an unrelated source excerpt. Provider errors are `partial`; rejected evidence
without a model prediction is `insufficient_evidence`. Existing model scores and
review decisions are preserved. Verification checks failure/status consistency.

Unit checks: `python -m unittest discover -s tests -v`.
Browser check: `node tools/checks/check_testing_guidance.cjs` (Edge + bundled Playwright).
