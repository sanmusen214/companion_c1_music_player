from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as SessionManager
from winsdk.windows.storage.streams import Buffer, InputStreamOptions
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionPlaybackStatus
from datetime import datetime, timezone


async def get_media_info(get_cover=True):
    """
    获取当前windows系统正在播放的音乐的信息
    """
    info_dict = {}
    # 获取会话管理器
    sessions = await SessionManager.request_async()
    
    # 获取当前活跃的媒体会话（如 Spotify, 网易云, 浏览器等）
    current_session = sessions.get_current_session()
    
    if current_session:
        # 获取媒体属性（标题、艺术家等）
        info = await current_session.try_get_media_properties_async()
        info_dict = {song_attr: info.__getattribute__(song_attr) for song_attr in dir(info) if song_attr[0] != '_'}

        # 获取封面图
        if get_cover and info.thumbnail:
            picpath = "cover.jpg"
            # 打开封面流
            thumb_stream = await info.thumbnail.open_read_async()
            # 读取流数据并保存为文件
            buffer = Buffer(thumb_stream.size)
            await thumb_stream.read_async(buffer, buffer.capacity, InputStreamOptions.NONE)
            
            with open(picpath, "wb") as f:
                f.write(bytearray(buffer))
            info_dict['cover_path'] = picpath
        
        # 获取进度信息
        # 音乐软件不上报，全是0，嘻嘻了
        if 1:
            # 2. 获取时间线属性
            timeline = current_session.get_timeline_properties()
            # 3. 获取播放信息
            playback_info = current_session.get_playback_info()
            
            # Windows 的 TimeSpan 映射到 Python 的 timedelta
            total_duration = timeline.end_time.total_seconds() 
            base_position = timeline.position.total_seconds()

            # print(f"Total duration: {total_duration} seconds")
            # print(f"Base position: {base_position} seconds")

            # 获取倍速 (从 playback_info 获取)
            # 注意：某些播放器可能返回 None，默认给 1.0
            rate = playback_info.playback_rate if playback_info.playback_rate is not None else 1.0
            # print(f"Playback rate: {rate}")
            if playback_info.playback_status == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING:
                # 计算自上次更新时间以来的经过时间
                last_update = timeline.last_updated_time.timestamp()
                now = datetime.now(timezone.utc).timestamp()
                elapsed = now - last_update
                current_progress = base_position + (elapsed * rate)
                info_dict['playback_status'] = 1
            else:
                current_progress = base_position
                info_dict['playback_status'] = 0

            # 边界限制
            current_progress = max(0, min(current_progress, total_duration))

            info_dict['progress_seconds'] = current_progress
            info_dict['total_duration_seconds'] = total_duration

    return info_dict

import os
appdata_path = os.getenv('APPDATA')
cloud_webdata_path = os.path.join(appdata_path, '../Local/NetEase/CloudMusic/webdata/file')

def download_cover_image(song_id, req_server="netease"):
    # 遍历云音乐的 webdata 目录，打印所有文件名
    possible_paths = []
    print(cloud_webdata_path)
    for root, dirs, files in os.walk(cloud_webdata_path):
        for file in files:
            print(f"Found file: {file}")

if __name__ == "__main__":
    download_cover_image("1234567890")