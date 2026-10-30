# DISAM Domain Routing

Apply this file **only when DISAM context is active**.

Supported adapters:
- human_wellness
- cosmetics
- medical_device
- agriculture
- animal_nutrition
- food_application
- research_only

Routing priority:
1. Explicit product regulatory category or authorization in current source material.
2. User-selected `domain_adapter`.
3. DISAM product taxonomy.
4. Category evidence from source documents.
5. Model inference.

If confidence is insufficient and the choice would materially change regulatory treatment, evidence interpretation, or external claims, return:

```yaml
routing:
  requires_human_input: true
  confidence: low
  reason: "domain ambiguity changes downstream compliance treatment"
```

Never silently reuse rules from another domain. Food/supplement, cosmetic, medical-device, agriculture, animal-nutrition, and food-application claims have separate regulatory contexts.
