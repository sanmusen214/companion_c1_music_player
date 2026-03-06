# pyinstaller main.py --noconsole -y

import subprocess
import time
import os
import shutil
from utils.config import my_config
# 打包
target_name = my_config.target_name
# icon.ico 
subprocess.run([
    "pyinstaller",
    f"{target_name}.spec",
    "-y"
])

target_dir = f"dist/{target_name}"
# 配置文件
if os.path.exists(target_dir):
    shutil.copy("software_config.yaml", f"{target_dir}/software_config.yaml")
    print("Config file copied successfully!")
else:
    print(f"Error: Timeout waiting, directory {target_dir} not found")
# 图标文件
if not os.path.exists(f"{target_dir}/assets"):
    os.makedirs(f"{target_dir}/assets", exist_ok=True)
if os.path.exists(target_dir):
    shutil.copy("assets/icon.ico", f"{target_dir}/assets/icon.ico")
    print("Icon file copied successfully!")
else:
    print(f"Error: Timeout waiting, directory {target_dir} not found")
# 创建 cache_data 目录
cache_data_dir = os.path.join(target_dir, "cache_data")
os.makedirs(cache_data_dir, exist_ok=True)
# 音乐软件
# 找到配置项里的音乐软件路径
music_software_path = my_config.get('GetMusicStatus_position', '')
music_software_dir = os.path.dirname(music_software_path)
if os.path.exists(music_software_dir):
    dest_music_software_dir = os.path.join(target_dir, "music_info_software")
    shutil.copytree(music_software_dir, dest_music_software_dir)
    print("Music software copied successfully!")
    # 修改配置文件中的GetMusicStatus_position的路径为相对路径到music_info_software目录下的GetMusicStatus.exe
    new_music_software_path = os.path.join("music_info_software", os.path.basename(music_software_path))
    # my_config.set('GetMusicStatus_position', new_music_software_path)
    # 读取配置文件的内容
    now_yaml_content = None
    with open('software_config.yaml', 'r', encoding='utf-8') as f:
        now_yaml_content = f.read()
    # 替换路径
    # 找到 有GetMusicStatus_position: 开头的行，并替换其后的路径
    now_yaml_content_lines = now_yaml_content.splitlines()
    for i in range(len(now_yaml_content_lines)):
        line = now_yaml_content_lines[i]
        if line.strip().startswith('GetMusicStatus_position:'):
            # 替换该行
            now_yaml_content_lines[i] = f'GetMusicStatus_position: {new_music_software_path}'
    # 保存修改后的配置文件
    with open(f'{target_dir}/software_config.yaml', 'w', encoding='utf-8') as f:
        f.write('\n'.join(now_yaml_content_lines))
    print("Configuration file updated successfully!")
else:
    print(f"Error: Music software directory {music_software_dir} not found")