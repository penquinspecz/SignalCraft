# Job Briefs v1

You are generating concise, guardrailed job briefs for a shortlist of roles.

Inputs:
- Ranked job fields (title, score, role_band, fit_signals, risk_signals, jd_text)
- Candidate profile (skills/roles)

Output (JSON):
- why_fit: 3-5 bullets grounded in job fields
- gaps: 2-4 bullets about missing/weak areas
- interview_focus: 3-5 bullets
- resume_tweaks: 3-5 bullets

Rules:
- No hallucinations. Use only provided fields.
- Keep language concise and actionable.
- Deterministic output (no randomness).
