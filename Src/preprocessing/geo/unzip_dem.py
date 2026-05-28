# @Author  : ChaoQiezi
# @Time    : 2026/5/19
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: unzip_dem.py

"""
Extract GLO-30 DEM tar.gz files to dem/, slope/, aspect/ subdirectories.
Source: I:\DataHub\GLO-30_DEM\Tile*_DEM.tar.gz  → dem\Tile*_dem.tif
        I:\DataHub\GLO-30_DEM\Tile*_Viz.tar.gz  → slope\Tile*_slope.tif + aspect\Tile*_aspect.tif
"""

from glob import glob
import os
import shutil
import tarfile
import tempfile

# 解压配置
in_dir = r'I:\DataHub\GLO-30_DEM'

out_dirs = {
    'dem': os.path.join(in_dir, 'dem'),
    'slope': os.path.join(in_dir, 'slope'),
    'aspect': os.path.join(in_dir, 'aspect'),
}
for d in out_dirs.values():
    os.makedirs(d, exist_ok=True)

# --- DEM ---
dem_tars = sorted(glob(os.path.join(in_dir, '*_DEM.tar.gz')))
print(f'Found {len(dem_tars)} DEM tar.gz files.')

for dem_tar in dem_tars:
    tile_name = os.path.basename(dem_tar).replace('_DEM.tar.gz', '')
    out_path = os.path.join(out_dirs['dem'], f'{tile_name}_dem.tif')
    if os.path.exists(out_path):
        print(f'  {tile_name}_dem.tif exists, skip.')
        continue

    print(f'Extracting DEM: {tile_name} ...')
    with tempfile.TemporaryDirectory() as tmpdir:
        with tarfile.open(dem_tar, 'r:gz') as tar:
            tar.extractall(tmpdir)
        extracted = os.listdir(tmpdir)
        if len(extracted) != 1:
            print(f'  WARNING: expected 1 file, got {len(extracted)}: {extracted}')
        shutil.move(os.path.join(tmpdir, extracted[0]), out_path)
    print(f'  -> {out_path}')

# --- Viz (slope + aspect) ---
viz_tars = sorted(glob(os.path.join(in_dir, '*_Viz.tar.gz')))
print(f'\nFound {len(viz_tars)} Viz tar.gz files.')

for viz_tar in viz_tars:
    tile_name = os.path.basename(viz_tar).replace('_Viz.tar.gz', '')
    slope_out = os.path.join(out_dirs['slope'], f'{tile_name}_slope.tif')
    aspect_out = os.path.join(out_dirs['aspect'], f'{tile_name}_aspect.tif')

    if os.path.exists(slope_out) and os.path.exists(aspect_out):
        print(f'  {tile_name} slope/aspect exist, skip.')
        continue

    print(f'Extracting Viz: {tile_name} ...')
    with tempfile.TemporaryDirectory() as tmpdir:
        with tarfile.open(viz_tar, 'r:gz') as tar:
            tar.extractall(tmpdir)
        for f in os.listdir(tmpdir):
            src = os.path.join(tmpdir, f)
            if 'slope' in f:
                shutil.move(src, slope_out)
                print(f'  -> {slope_out}')
            elif 'aspect' in f:
                shutil.move(src, aspect_out)
                print(f'  -> {aspect_out}')
            else:
                print(f'  WARNING: unknown file {f}')

print('\nAll extractions completed.')
