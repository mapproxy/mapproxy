from __future__ import absolute_import

import sys

PY2 = sys.version_info[0] == 2
PY3 = not PY2

if PY2:
    from itertools import (
        izip,
        izip_longest,
        imap,
        islice,
        chain,
        groupby,
        cycle,
    )

else:
    izip = zip
    imap = map
    from itertools import (
        zip_longest as izip_longest,
        islice,
        chain,
        groupby,
        cycle,
    )

