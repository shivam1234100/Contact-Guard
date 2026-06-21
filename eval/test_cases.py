"""The six evaluation scenarios. Each row points at a sample contract and the
JSON file in ``eval/expected/`` holding its expected labels.

  1. Clean contract        -> low risk, fast-track approval path
  2. Risky contract        -> high/critical risk, multiple redlines
  3. Borderline contract   -> medium risk, senior review + human interrupt fires
  4. Missing clauses       -> critical gaps detected
  5. Prompt injection      -> blocked; risk NOT downgraded by the injected text
  6. Malformed input       -> graceful failure, pipeline does not crash
"""

CASES = [
    ("clean_msa.txt", "Clean MSA — standard terms", "clean_msa.json"),
    ("risky_saas.txt", "Risky SaaS — unlimited liability", "risky_saas.json"),
    ("borderline_nda.txt", "Borderline NDA — liability at 2x fees", "borderline_nda.json"),
    ("missing_clauses.txt", "Missing critical clauses", "missing_clauses.json"),
    ("injection_contract.txt", "Prompt injection in a clause", "injection_contract.json"),
    ("malformed.txt", "Malformed / corrupt upload", "malformed.json"),
]
