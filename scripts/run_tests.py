"""Deterministic offline suite. Live KGM smoke checks are run separately."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

if __name__=='__main__':
    with patch('live_prices.urlopen',side_effect=OSError('offline test')):
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('tests'))
    sys.exit(not result.wasSuccessful())
