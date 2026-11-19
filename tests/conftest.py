from pathlib import Path
import sys

# Scripts are intentionally runnable directly from the research checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
