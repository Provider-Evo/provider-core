from __future__ import annotations

"""生成快照压缩包。"""

from _zip_common import make_zip
from common import get_version


def main() -> None:
    version = get_version().lstrip('v')
    make_zip('provider-{}.zip'.format(version), ['logs', 'persist', 'data'])


if __name__ == '__main__':
    main()
