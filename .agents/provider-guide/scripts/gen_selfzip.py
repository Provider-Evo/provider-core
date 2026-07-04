from __future__ import annotations

"""生成自包含压缩包。"""

from _zip_common import make_zip
from common import get_version


def main() -> None:
    version = get_version().lstrip('v')
    make_zip('provider-{}-self.zip'.format(version), ['logs', '.backup', '.tmp'], patch_autoupdate=True, include_git=True)


if __name__ == '__main__':
    main()
