"""CodeBuddy 平台内部实现包。

本包内的所有模块均为实现细节，不应被 ``src.platforms.codebuddy.adapter``
之外的模块直接导入。对外发布的稳定接口全部经由
:mod:`src.platforms.codebuddy.util` 门面再导出。
"""

from __future__ import annotations
