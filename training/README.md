# Fine-Tuning Guide

Fine-tuning improves agent accuracy on financial terminology and structured JSON output.

## Approach

Fine-tuning is done via Ollama's Modelfile system, which wraps a base model with a custom system prompt and example conversations. This does not require GPU clusters — it runs on the same hardware as the rest of the system.

## Directory Structure

```
training/
├── README.md                    # This file
├── data/
│   ├── extraction_examples.jsonl  # Training data for data extractor
│   ├── trend_examples.jsonl       # Training data for trend analyzer
│   └── sentiment_examples.jsonl   # Training data for sentiment analyzer
├── modelfiles/
│   ├── Modelfile.extractor        # Ollama Modelfile for data extractor
│   └── Modelfile.analyzer         # Ollama Modelfile for trend/sentiment
└── create_models.sh               # Script to build custom Ollama models
```

## Training Data Format

Each `.jsonl` file contains one example per line in this format:

```json
{"prompt": "Extract financial data from: Revenue was $5.2M in Q4 2024, up 12% YoY.", "response": "{\"company\": \"Unknown\", \"period\": \"Q4 2024\", \"metrics\": {\"revenue\": {\"value\": 5200000, \"unit\": \"USD\", \"period\": \"Q4 2024\"}, \"growth_rates\": {\"revenue_yoy\": \"12%\"}}, \"raw_figures\": [{\"label\": \"Revenue\", \"value\": \"5,200,000\", \"context\": \"Q4 2024\"}], \"notes\": \"\"}"}
```

Key: the `response` field must be valid JSON matching the exact schema the agent is expected to return.

## Steps to Fine-Tune

1. **Collect examples** — add 50–200 examples to the relevant `.jsonl` file.
   More is better; focus on the output schema being consistent.

2. **Create the Modelfile**:
   ```
   FROM phi3:mini
   SYSTEM """You are a financial data extraction specialist..."""
   ```
   See `modelfiles/Modelfile.extractor` for the full template.

3. **Build the custom model**:
   ```bash
   ollama create financial-extractor -f training/modelfiles/Modelfile.extractor
   ```

4. **Update config** to use the new model:
   ```python
   # config/config.py
   DATA_EXTRACTOR_MODEL = "financial-extractor"
   ```

5. **Test** with:
   ```bash
   python -m pytest tests/test_agents.py -v
   ```

## Tips

- Start with the data extractor — it has the most rigid output schema and benefits most from fine-tuning.
- Prioritize examples where the base model produces wrong JSON structure.
- Include negative examples (documents with no financial data) so the model learns to return null values rather than hallucinate.
