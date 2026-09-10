import sys
import os
from typing import cast

x = cast(int, "1")
print(sys.argv, os.name, x)
