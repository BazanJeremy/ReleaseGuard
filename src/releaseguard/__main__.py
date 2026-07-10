"""Allow ``python -m releaseguard`` as an alias for the console script."""

import sys

from releaseguard.cli import main

sys.exit(main())
