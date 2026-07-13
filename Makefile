.PHONY: install test check sample serve

install:
	python -m pip install -e .

test:
	python -m unittest discover -s tests -v

check:
	python -m compileall -q src tests examples
	python -m unittest discover -s tests -v

sample:
	python examples/generate_sample.py
	unified-indicator analyze --symbol AAPL --asset-class stock --input examples/sample_ohlcv.csv

serve:
	unified-indicator serve --host 127.0.0.1 --port 8080
