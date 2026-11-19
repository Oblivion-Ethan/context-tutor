.PHONY: test demo serve

PYTHON ?= python3

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

serve:
	PYTHONPATH=src $(PYTHON) -m context_tutor --data-dir data --profile profiles/english_weak.json serve

demo:
	PYTHONPATH=src $(PYTHON) -m context_tutor --data-dir data --profile profiles/english_weak.json init
	PYTHONPATH=src $(PYTHON) -m context_tutor --data-dir data --profile profiles/english_weak.json ingest examples/article.txt --title "Context matters"
	PYTHONPATH=src $(PYTHON) -m context_tutor --data-dir data --profile profiles/english_weak.json stats
	PYTHONPATH=src $(PYTHON) -m context_tutor --data-dir data --profile profiles/english_weak.json enrich --adapter mock
	PYTHONPATH=src $(PYTHON) -m context_tutor --data-dir data --profile profiles/english_weak.json review --limit 2 --show-answer
