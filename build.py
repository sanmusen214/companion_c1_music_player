# pyinstaller main.py --noconsole -y

import subprocess
import time
import os
import shutil
# 打包
subprocess.run([
    "pyinstaller",
    '--name=music_3d_cover',
    "main.py",
    "--noconsole",
    "-y"
])

target_dir = "dist/music_3d_cover"

if os.path.exists(target_dir):
    shutil.copy("software_config.yaml", f"{target_dir}/software_config.yaml")
    print("配置文件复制成功！")
else:
    print(f"错误：等待超时，未找到目录 {target_dir}")