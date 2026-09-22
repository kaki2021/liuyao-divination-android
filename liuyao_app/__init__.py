"""Local web application built on the maintained domain foundation."""
from pathlib import Path
import sys

DOMAIN = Path(__file__).resolve().parents[1] / 'software_prep'
if str(DOMAIN) not in sys.path:
    sys.path.insert(0, str(DOMAIN))
