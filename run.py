import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from pri.paths import pin_environment
pin_environment()
from pri.app import main
raise SystemExit(main())
