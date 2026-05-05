# @Author  : ChaoQiezi
# @Time    : 2026/4/30
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: run_pending_tasks.py

"""
线性运行四个河谷中尚未完成的 geo_analysis 任务。

执行顺序（考虑依赖关系）：
  1. Daduhe: ndvi_spatial_distribution_by_interannual.py  → 生成年际均值NDVI栅格
  2. Minjiang: ndvi_altitude_gradient.py                  → 补逐年 + 年际均值 高程梯度表
  3. Daduhe: ndvi_altitude_gradient.py                    → 补年际均值 高程梯度表
  4. Jinshajiang: ndvi_altitude_gradient.py               → 补逐年 + 年际均值 高程梯度表
  5. Yalongjiang: ndvi_altitude_gradient.py               → 补逐年 + 年际均值 高程梯度表
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = r"D:/Softwares/Anaconda3/envs/geo/python.exe"

SCRIPTS = [
    ROOT / "Daduhe/geo_analysis/ndvi_spatial_distribution_by_interannual.py",
    ROOT / "Minjiang/geo_analysis/ndvi_altitude_gradient.py",
    ROOT / "Daduhe/geo_analysis/ndvi_altitude_gradient.py",
    ROOT / "Jinshajiang/geo_analysis/ndvi_altitude_gradient.py",
    ROOT / "Yalongjiang/geo_analysis/ndvi_altitude_gradient.py",
]


if __name__ == "__main__":
    n_total = len(SCRIPTS)
    for i, script in enumerate(SCRIPTS, 1):
        print(f"\n{'=' * 60}")
        print(f"[{i}/{n_total}] Running: {script.name}")
        print(f"       Valley: {script.parent.parent.name}")
        print(f"{'=' * 60}")
        result = subprocess.run(
            [PYTHON, str(script)],
            cwd=str(script.parent),
        )
        if result.returncode != 0:
            print(f"[FAIL] {script.name} exited with code {result.returncode}")
        else:
            print(f"[OK] {script.name}")
    print(f"\n{'=' * 60}")
    print("All pending tasks completed.")
