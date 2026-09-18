import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend" / "src"))

from utils.short_code import generate_short_code

def test_short_code_length():
    assert len(generate_short_code()) == 6

def test_short_code_is_different():
    assert generate_short_code() != generate_short_code()
