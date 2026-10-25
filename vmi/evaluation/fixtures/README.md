# Annotated evaluation input

`demo-v2.2.json.gz` is the synthetic seed-12 match used to annotate the 30
questions in `question_set.py`. It is benchmark input, not a claim that the
latest generator produces this historical score or timeline.

- Original generator: **2.2.0**, schema **2.0**.
- Source repository commit: `92b5ecfd6a6496e726ffd4b20d09c9602ee91187`.
- Source: `vmi/generator/match.py`, unchanged dependencies from that commit.
- Score: 2–1; 2,431 event records. Includes crowd, match state and truth
  keyframes so replay still delivers the original observed inputs at 20Hz.
- SHA-256 of the compressed bytes:
  `04d9e2119d9adf5a56ed87cb6cf1d6cd5e960160afea8dc5c7d1368d1e351572`.
- Original VMI synthetic data; repository MIT license, no real match footage.

Reproduce from a clean checkout at the source commit, with Python 3.12:

```python
from dataclasses import asdict
import gzip, json
from pathlib import Path
from vmi.generator.match import generate_match

raw = json.dumps(asdict(generate_match(12)), separators=(",", ":"), ensure_ascii=False).encode()
Path("demo-v2.2.json.gz").write_bytes(gzip.compress(raw, mtime=0))
```

Compare decompressed JSON when gzip/zlib implementations differ. The loader
checks the committed compressed bytes. Updating the benchmark requires updating
the question annotations and re-evaluating model candidates; a generator bump
must not silently change benchmark meaning. No model evaluation result is
claimed by freezing these inputs.
