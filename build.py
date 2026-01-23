# pyinstaller main.py --noconsole -y

import subprocess
import time
import os
import shutil
# 打包
# icon.ico 
subprocess.run([
    "pyinstaller",
    '--name=music_3d_cover',
    "main.py",
    "--noconsole",
    "-y",
    "--icon=assets/icon.ico",
])

target_dir = "dist/music_3d_cover"
# 配置文件
if os.path.exists(target_dir):
    shutil.copy("software_config.yaml", f"{target_dir}/software_config.yaml")
    print("配置文件复制成功！")
else:
    print(f"错误：等待超时，未找到目录 {target_dir}")
# 图标文件
if not os.path.exists(f"{target_dir}/assets"):
    os.makedirs(f"{target_dir}/assets", exist_ok=True)
if os.path.exists(target_dir):
    shutil.copy("assets/icon.ico", f"{target_dir}/assets/icon.ico")
    print("图标文件复制成功！")
else:
    print(f"错误：等待超时，未找到目录 {target_dir}")