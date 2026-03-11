#!/bin/bash
# Build custom fine-tuned Ollama models from Modelfiles.
# Run from the project root: bash training/create_models.sh

set -e

echo "Building financial-extractor model..."
ollama create financial-extractor -f training/modelfiles/Modelfile.extractor

echo ""
echo "Done. Update config/config.py to use the new models:"
echo "  DATA_EXTRACTOR_MODEL = \"financial-extractor\""
echo "  VALIDATOR_MODEL = \"financial-extractor\""
echo ""
echo "Then run tests to verify:"
echo "  python -m pytest tests/ -v"
