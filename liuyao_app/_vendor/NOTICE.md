# 内置历法依赖

软件内置 `lunar_python 1.4.8`，作者 6tail，MIT 许可。用户无需联网下载或安装 Python 包。

- 原项目：https://github.com/6tail/lunar-python
- 发布页：https://pypi.org/project/lunar_python/1.4.8/
- 完整许可保存在 `lunar_python/LICENSE`。
- 原始发行包 SHA256、逐文件 SHA256 和测试来源保存在 `lunar_python_manifest.json`。
- 包源码按原样放入本软件的 `_vendor` 命名空间，未修改上游算法。

本软件仅使用公历时刻转年、月、日、时干支的方法，不调用该依赖中的吉凶、宜忌、神煞断语、八字命理和起运等功能。六神仍由本软件既有的日干排法计算。

软件历法约定为固定北京时间 UTC+08:00、立春交节时刻换年、节交接时刻换月、日柱零点换日。采用该库 `sect=2`：23:00—23:59 日柱仍是当天，时柱按次日子时计算；六神使用当前显示的日柱天干。标准时不校正真太阳时，也不采用历史夏令时。

这是当前软件的排盘约定，不声称原典已规定上述边界。传入时刻必须含时区；软件先转换成北京时间，再计算并保存原始时刻、转换时刻和具体约定。目前提供北京时间 1900—2100 年的四柱计算。没有实际起卦时间时保留缺失状态。

依据与核对：

- 官方干支接口：https://6tail.cn/calendar/lunar.ganzhi.html
- 官方八字流派说明：https://6tail.cn/calendar/lunar.bazi.html
- 官方四柱测试：https://github.com/6tail/lunar-python/blob/master/test/EightCharTest.py
- 官方交节测试：https://github.com/6tail/lunar-python/blob/master/test/JieQiTest.py
- 香港天文台 2024 年公历与农历日期对照表，仅用于独立核对立春日期：https://www.hko.gov.hk/tc/gts/time/calendar/pdf/files/2024.pdf

适配层测试包含已知四柱、UTC跨日、等价时区、23时和零点、节令交接秒、立春换年换月、无时间不补造、错误时间与日期范围。
