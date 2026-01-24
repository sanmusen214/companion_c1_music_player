# pyinstaller main.py --noconsole -y

import subprocess
import time
import os
import shutil
from utils.config import my_config
# 打包
target_name = "自由象限 C1 音乐副屏"
# icon.ico 
subprocess.run([
    "pyinstaller",
    f'--name={target_name}',
    "main.py",
    "--noconsole",
    "-y",
    "--icon=assets/icon.ico",
])

target_dir = f"dist/{target_name}"
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
# 音乐软件
# 找到配置项里的音乐软件路径
music_software_path = my_config.get('GetMusicStatus_position', '')
music_software_dir = os.path.dirname(music_software_path)
if os.path.exists(music_software_dir):
    dest_music_software_dir = os.path.join(target_dir, "music_info_software")
    shutil.copytree(music_software_dir, dest_music_software_dir)
    print("音乐软件文件复制成功！")
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
    print("配置文件更新成功！")
else:
    print(f"错误：未找到音乐软件目录 {music_software_dir}")