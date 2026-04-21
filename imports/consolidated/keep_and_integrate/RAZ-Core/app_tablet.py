"""
RAZ Tablet entrypoint.
Bootstraps app.py in touch-optimized tablet mode.
"""

import os

# Must be set before importing app.py so mode constants are computed correctly.
os.environ["RAZ_TABLET_MODE"] = "1"

from app import main


if __name__ == "__main__":
    main()
