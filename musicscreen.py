import os

import cv2
import numpy as np
import threading
import time
from PIL import Image
import pystray
import sys
import webbrowser
from screeninfo import get_monitors
import traceback
import json

from utils import MusicPlayerGenerator, device_config, synthesize_fusion_frame, hide_window_from_taskbar, MusicCachePool, generate_cache_id, load_file2RGBImage, save_BGRimage2file,  download_cover_image_from_keyword, MusicInfoMonitor, my_i18n, my_config
from utils.music_freq_utils import SpectrumAnalyzer

class ScreenShowApp:
    """系统托盘和播放器窗口的主应用程序"""
    def __init__(self):
        # 显示器基本参数
        self.monitor_true_width = 1440
        self.monitor_true_height = 2560
        # 应用状态控制
        self.is_running = True # 应用主循环运行状态
        
        # 音乐平台配置
        self.current_platform = my_config.get("Music_platform", "netease")
        
        # 监控器
        self.music_monitor = MusicInfoMonitor(self.current_platform)
        self.music_monitor.start_monitoring()
        # 现在绘制的歌曲status的缓存id
        self.now_cache_id = ""
        # 缓存池
        self.tile_cache_pool = MusicCachePool(max_size=my_config.get("Cache_len", 10))
        # tile图片生成器
        self.global_frame_generator = MusicPlayerGenerator(
            my_config.get("Cover_intensity"),
            my_config.get("Background_intensity"),
            my_config.get("Word_intensity"),
        )
        # 现在合成tile图片内容（BGR 数组）
        self.img_content = None
        # 现在盖在频谱上的播放状态图标（播放/暂停），根据当前歌曲的播放状态生成并缓存两张图，切换状态时直接加载对应的图片
        self.music_control_img_playing = None
        self.music_control_img_paused = None
        threading.Thread(target=self._load_playback_status_images, daemon=True).start()
        # 现在音乐 cover 图片主题色 ((B, G, R),(B, G, R))，作为频谱颜色的基础
        self.cover_theme_color = (None, None)
        # 创建OpenCV窗口名字
        self.window_name = "music3d c1 image"
        self.initialize_cv_window()
        # 启动系统托盘图标
        self.setup_tray_icon()
        
        # 初始化频谱分析器
        try:
            self.spectrum_analyzer = SpectrumAnalyzer()
        except Exception as e:
            print(f"Warning: Spectrum Analyzer init failed: {e}, {traceback.format_exc()}")
            self.spectrum_analyzer = None
        
    def update_music_platform(self, icon, item):
        """更新音乐平台的回调函数"""
        platform_name = str(item)
        if platform_name == self.current_platform:
            return

        print(f"Switching music platform to: {platform_name}")
        self.current_platform = platform_name
        
        # 更新配置并保存
        my_config.set("Music_platform", platform_name)
        my_config.save_config()
        
        # 重启监控器
        print("Stopping current monitor...")
        self.music_monitor.stop_monitoring()
        # 在新线程中重新启动，避免阻塞托盘
        threading.Thread(target=self._restart_monitor_process, args=(platform_name,), daemon=True).start()

    def _load_playback_status_images(self):
        """加载播放状态图标，如果没有的话，生成"""
        control_img_folder = os.path.join(my_config.app_data_dir, "control_ui")
        os.makedirs(control_img_folder, exist_ok=True)
        playing_path = os.path.join(control_img_folder, "1.png")
        paused_path = os.path.join(control_img_folder, "0.png")
        device_config_path = os.path.join(control_img_folder, "device_config.json")
        # 如果设备配置有变化，或者图标文件不存在，则重新生成
        need_generate = False
        if not os.path.exists(playing_path) or not os.path.exists(paused_path):
            print("Playback status icon images not found, need to generate")
            need_generate = True
        else:
            def _check_config_same(saved_config, current_config):
                keys_to_check = ["obliquity", "lineNumber", "deviation"]
                for key in keys_to_check:
                    if saved_config.get(key) != current_config.get(key):
                        return False
                return True
            try:
                with open(device_config_path, "r") as f:
                    saved_device_config = json.load(f)
                if not _check_config_same(saved_device_config, device_config):
                    print("Device config changed, need to regenerate playback status icons")
                    need_generate = True
            except Exception as e:
                print(f"Error checking device config for playback icons: {e}, {traceback.format_exc()}")
                need_generate = True
        # 根据需要生成的结果，决定是加载还是生成
        if not need_generate:
            # 直接加载
            self.music_control_img_playing = np.array(load_file2RGBImage(playing_path))[:,:,::-1] # 转成BGR
            self.music_control_img_paused = np.array(load_file2RGBImage(paused_path))[:,:,::-1] # 转成BGR
            print("Loaded playback status icons from cache")
        else:
            # 生成播放状态图标
            print("Generating playback status icons...")
            playing_img = self.global_frame_generator.generate_music_playback_icon_images(is_playing=True)
            paused_img = self.global_frame_generator.generate_music_playback_icon_images(is_playing=False)
            # 转交织图 保存
            playing_img = synthesize_fusion_frame(playing_img, device_config)
            self.music_control_img_playing = playing_img
            save_BGRimage2file(playing_img, playing_path)

            paused_img = synthesize_fusion_frame(paused_img, device_config)
            self.music_control_img_paused = paused_img
            save_BGRimage2file(paused_img, paused_path)
            try:
                with open(device_config_path, "w") as f:
                    json.dump({
                        "obliquity": device_config['obliquity'],
                        "lineNumber": device_config['lineNumber'],
                        "deviation": device_config['deviation']
                    }, f)
                print("Saved current device config for playback icons")
            except Exception as e:
                print(f"Error saving device config for playback icons: {e}, {traceback.format_exc()}")


    def _restart_monitor_process(self, platform_name):
        time.sleep(0.5) # 等待线程清理
        print(f"Starting monitor for {platform_name}...")
        self.music_monitor = MusicInfoMonitor(platform_name)
        self.music_monitor.start_monitoring()

    def setup_tray_icon(self):
        """创建系统托盘图标和菜单"""
        # 创建托盘图标图像
        image = Image.open("assets/icon.ico")
        
        # 音乐平台列表
        platforms = [
            "netease", "qq", "kugou", "kuwo", "soda", "spotify", "apple", 
            "ayna", "potplayer", "foobar", "lx", "huahua", "musicfree", 
            "bq", "aimp", "youtube", "miebo", "yesplay", "cider"
        ]
        
        # 创建平台选择子菜单项
        # 注意：这里需要通过闭包捕获 platform_name，或者直接用 lambda item: ... 
        # 但 checked需要比较 item 和 self.current_platform
        
        def on_click(icon, item):
            self.update_music_platform(icon, item)

        platform_items = []
        for p in platforms:
            platform_items.append(pystray.MenuItem(
                p, 
                on_click, 
                checked=lambda item: str(item) == self.current_platform,
                radio=True
            ))
            
        platform_menu = pystray.Menu(*platform_items)

        # 创建主菜单项
        menu_items = [
            pystray.MenuItem(f'{my_i18n.get("C1_music_screen")} v{my_config.version}', None, enabled=False),
            # 添加子菜单
            pystray.MenuItem(my_i18n.get("music_platform"), platform_menu),
            pystray.MenuItem('GitHub: sanmusen214', lambda: webbrowser.open("https://github.com/sanmusen214")),
            pystray.MenuItem(my_i18n.get("quit_button"), self.quit_action)
        ]
        
        # 创建托盘图标
        self.icon = pystray.Icon("music3d c1", image, "music3d c1 app", menu=pystray.Menu(*menu_items))
        
        # 在单独线程中运行托盘图标
        self.tray_thread = threading.Thread(target=self.icon.run, daemon=True)
        self.tray_thread.start()
    
    def initialize_cv_window(self):
        # 获取所有监视器信息
        monitors = get_monitors()
        # Find monitor with resolution 1440x2560
        for monitor in monitors:
            if monitor.width == 1440 and monitor.height == 2560:
                # First create a window
                cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
                # Resize window to screen resolution
                cv2.resizeWindow(self.window_name, monitor.width, monitor.height)
                # Move to top-left corner of target monitor
                cv2.moveWindow(self.window_name, monitor.x, monitor.y)
                # Set to fullscreen
                cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                # Hide from taskbar
                hide_window_from_taskbar(self.window_name)
                break
    
    def quit_action(self):
        """退出菜单项回调，应用生命周期结束必须调用"""
        self.is_running = False
        print("Stopping music monitor...")
        self.music_monitor.stop_monitoring()
        print("Stop icon...")
        self.icon.stop()
        time.sleep(1)  # 等待图标线程结束
        print("Destroying windows and exiting...")
        cv2.destroyWindow(self.window_name)
        cv2.waitKey(1)  # 确保窗口被销毁
        print("Application quit")
        sys.exit(0)

    def draw_image(self, frame, pic_content):
        """在帧上绘制图片"""
        # 加载图片
        img = pic_content
        if img is None:
            return frame
        # Image 转 np
        img = np.array(img)
        img_h, img_w = img.shape[:2]

        if img_w == self.monitor_true_width and img_h == self.monitor_true_height:
            frame = img
        else:
            print(f"Warning: Image size {img_w}x{img_h} does not match monitor size {self.monitor_true_width}x{self.monitor_true_height}. Skip")
        return frame
    
    def generate_image(self):
        """重新生成当前歌曲的播放器tile和fusion图片"""
        # 1. 尝试从api下载封面图到本地cover.jpg
        music_info = self.music_monitor.now_music_info.copy()
        cover_path = download_cover_image_from_keyword(music_info)
        if cover_path is None:
            print("Failed to download cover image, using default cover")
        else:
            music_info["cover_path"] = cover_path
        # 生成新的tile图片，并进行fusion处理
        # print(f"Get new music cover: {music_info}")
        tile_image = self.global_frame_generator.generate_full_canvas(music_info)
        final_fusion_image = synthesize_fusion_frame(tile_image, device_config)
        # 更新fusion图片到当前显示内容
        self.img_content = final_fusion_image
        # 同步主题色
        self.cover_theme_color = SpectrumAnalyzer.get_cover_theme_color(self.img_content)
        # 将final_tile_image加入缓存池
        self.tile_cache_pool.add_key(generate_cache_id(music_info), final_fusion_image)
        print(f"Generated new tile image")
        # time.sleep(0.1)
        # 此外再将 反着的播放状态 缓存一份，方便切换播放状态时快速加载
        # music_info["playback_status"] = 0 if music_info.get('playback_status', 1) == 1 else 1
        # tile_image = self.global_frame_generator.generate_full_canvas(music_info)
        # final_fusion_image = synthesize_fusion_frame(tile_image, device_config)
        # self.tile_cache_pool.add_key(generate_cache_id(music_info), final_fusion_image)
        # print(f"Also cached toggled playback status image for music: {music_info.get('title', '')} - {music_info.get('artist', '')}")
        
        
    
    def on_music_updated(self, music_cache_id):
        """当音乐state发生更新时"""
        self.now_cache_id = music_cache_id
        # 如果缓存池中已有该fusion后的图片，则直接加载
        if self.tile_cache_pool.has_key(music_cache_id):
            print(f"Load tile image from cache: {music_cache_id}")
            cache_file_path = self.tile_cache_pool.get_cache_file_path(music_cache_id)
            RGB_image = load_file2RGBImage(cache_file_path)
            # 提取Image的RGB数组转换成 BGR，更新到 self.img_content
            self.img_content = np.array(RGB_image)[:,:,::-1]
            # 同步主题色
            self.cover_theme_color = SpectrumAnalyzer.get_cover_theme_color(self.img_content)
        else:
            # 重新生成图片（generate_image内将新图片加入缓存池）
            # 用新的线程运行 global_frame_generator.generate_full_canvas(music_info)
            gen_thread = threading.Thread(target=self.generate_image)
            gen_thread.start()


    def run(self):
        """主运行循环"""
        print("Starting main loop...")
        self.img_content = None
        with self.spectrum_analyzer.start_listening() as recorder:
            while self.is_running:
                # 获取当前播放歌曲(封面先不获取)
                music_info = self.music_monitor.now_music_info.copy()
                music_cache_id = generate_cache_id(music_info)
                if music_cache_id != self.now_cache_id and music_info.get("title", "") != "": # 歌曲信息有变化且不为空
                    print(f"Music changed, cache_id: {music_cache_id}")
                    self.on_music_updated(music_cache_id)

                # ==========================

                # 创建黑色背景 (注意 numpy shape 是 height, width)
                frame = np.zeros((self.monitor_true_height, self.monitor_true_width, 3), dtype=np.uint8)
                
                # 绘制图片
                frame = self.draw_image(frame, self.img_content)

                # 绘制频谱
                audio_data = recorder.record(numframes=self.spectrum_analyzer.fft_size)
                bucket_values = self.spectrum_analyzer.process_frame(audio_data)
                if bucket_values is not None:
                    try:
                        frame = self.spectrum_analyzer.draw_spectrum(frame, bucket_values, self)
                    except Exception as e:
                        print(f"Draw spectrum error: {e}, {traceback.format_exc()}")

                # 绘制播放状态图标
                if music_info.get("playback_status", 1) == 1: # 播放中
                    control_img = self.music_control_img_playing
                else:
                    control_img = self.music_control_img_paused
                if control_img is not None:
                    # 将 control_img 叠加到 frame 上，所有黑色像素(0,0,0)视为透明
                    mask = np.all(control_img == [0, 0, 0], axis=-1) # 黑色像素的掩码
                    frame[~mask] = control_img[~mask] # 仅替换非黑色像素
                
                
                # ---------------------
                # 显示帧 反转显示
                cv2.imshow(self.window_name, frame)

                # 处理键盘输入，刷新图像缓冲区
                # 减少等待时间以提高刷新率 (10ms)
                key = cv2.waitKey(10) & 0xFF
                
                time.sleep(0.001)