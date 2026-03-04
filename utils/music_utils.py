import requests
import subprocess
import threading
import queue
import time
from utils.config import my_config

class MusicInfoMonitor:
    """音乐信息监控器，负责运行外部程序并解析输出"""
    
    def __init__(self, platform):
        self.process = None
        self.is_running = False
        self.output_queue = queue.Queue()
        self.process_thread = None
        self.parser_thread = None
        self.music_platform = platform
        # 监控输出的 歌曲名字，艺术家，播放状态
        self.now_music_info = {
            "title": "",
            "artist": "",
            "playback_status": 1 # 1: 播放中, 0: 暂停
        }
        # 防止歌曲切换时播放状态来回切换，状态切换需要累计确认三次
        self.playback_confirm_count = 0
        self.playback_confirm_status = 1
        self.playback_confirm_max = 3
        
    def start_monitoring(self):
        """启动监控线程"""
        self.is_running = True
        
        # 启动进程监控线程 负责运行外部程序
        self.process_thread = threading.Thread(target=self._run_process)
        self.process_thread.start()
        
        # 启动输出解析线程 负责解析程序输出
        self.parser_thread = threading.Thread(target=self._parse_output)
        self.parser_thread.start()
        
    def stop_monitoring(self):
        """停止监控"""
        self.is_running = False
        if self.process:
            self.process.terminate()
            
    def _run_process(self):
        """运行外部程序并捕获输出[7,8](@ref)"""
        try:
            self.process = subprocess.Popen(
                [my_config.get("GetMusicStatus_position"), "--platform", self.music_platform],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # 实时读取输出[6](@ref)
            while self.is_running and self.process.poll() is None:
                line = self.process.stdout.readline()
                if line:
                    self.output_queue.put(line.strip())
                time.sleep(0.1)  # 避免过度占用CPU
                    
        except Exception as e:
            print(f"监控进程出错: {e}")
        finally:
            if self.process:
                self.process.terminate()
                
    def _parse_output(self):
        """解析程序输出并更新应用状态"""
        
        while self.is_running:
            try:
                # 非阻塞获取数据[7](@ref)
                line = self.output_queue.get(timeout=0.1)
                text = line.strip()
                if text in ["Playing", "Paused"]:
                    this_playback_status = self._parse_playback_status(text)
                    # 防抖处理 播放状态需要连续三次确认才更新
                    if this_playback_status != self.playback_confirm_status:
                        # 状态变化，重置计数
                        self.playback_confirm_status = this_playback_status
                        self.playback_confirm_count = 1
                    else:
                        # 状态相同，计数+1
                        self.playback_confirm_count = (self.playback_confirm_count + 1) % (self.playback_confirm_max + 1)
                        if self.playback_confirm_count >= self.playback_confirm_max:
                            playback_status = self.playback_confirm_status
                            self.now_music_info["playback_status"] = playback_status
                elif " - " in text:
                    music_info = self._parse_music_info(text)
                    self.now_music_info["title"] = music_info.get("title", "")
                    self.now_music_info["artist"] = music_info.get("artist", "")
                elif "None" in text:
                    # 清空当前音乐信息
                    self.now_music_info = {
                        "title": "",
                        "artist": "",
                        "playback_status": 1
                    }

            except queue.Empty:
                continue
            except Exception as e:
                print(f"解析输出时出错: {e}")
                
    def _parse_playback_status(self, status_line):
        """解析播放状态"""
        status_mapping = {
            "Playing": 1,    # 播放中
            "Paused": 0     # 暂停
        }
        status = status_line.strip()
        return status_mapping.get(status, status_mapping["Playing"])
    
    def _parse_music_info(self, music_line):
        """解析歌曲信息"""
        try:
            # 假设格式为: "歌曲名 - 艺术家"
            parts = music_line.split(' - ', 1)
            if len(parts) == 2:
                return {"title": parts[0].strip(), "artist": parts[1].strip()}
            else:
                # 如果不符合标准格式，整个字符串作为标题
                return {"title": music_line.strip(), "artist": "Unknown"}
        except:
            return {"title": "解析错误", "artist": "Unknown"}

import os
appdata_path = os.getenv('APPDATA')
cloud_webdata_path = os.path.join(appdata_path, '../Local/NetEase/CloudMusic/webdata/file')
# https://api.injahow.cn/meting/

def get_netease_id(music_info):
    keyword = f"{music_info.get('title', '')}-{music_info.get('artist', '')}"
    url = f"http://music.163.com/api/search/get/web?csrf_token=&hlpretag=&hlposttag=&s={keyword}&type=1&offset=0&total=true&limit=10"
    res = requests.get(url)
    if res.status_code != 200:
        return None
    result = res.json()
    if "result" not in result or "songs" not in result["result"] or len(result["result"]["songs"]) == 0:
        return None
    best_result = result["result"]["songs"][0]
    # 检查 名字 或 作者 是否匹配
    # if best_result["name"].lower() != music_info.get('title', '').lower():
    #     return None
    return best_result["id"]

def download_cover_image(song_id):
    url = f"https://api.injahow.cn/meting/?type=song&id={song_id}"
    res = requests.get(url)
    if res.status_code != 200:
        return None
    # 得到封面图接口链接
    picurl = res.json()[0]['pic']
    res = requests.get(picurl)
    if res.status_code != 200:
        return None
    # 得到最终封面图图片链接
    final_pic_url = res.url.split("?param")[0] + "?param=300y300"
    # 下载封面图
    res = requests.get(final_pic_url)
    if res.status_code != 200:
        return None
    picpath = os.path.join(my_config.app_data_dir, "cover.jpg")
    with open(picpath, "wb") as f:
        f.write(res.content)
    return picpath

def download_cover_image_from_keyword(music_info):
    try:
        song_id = get_netease_id(music_info)
        picpath = download_cover_image(song_id)
        print(f"Downloaded cover image to {picpath}")
        return picpath
    except Exception as e:
        print(f"下载封面图失败: {e}")
        return None