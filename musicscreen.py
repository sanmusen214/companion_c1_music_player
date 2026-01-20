import cv2
import numpy as np
import threading
import time
from PIL import Image, ImageDraw
import pystray
import sys
import asyncio

from utils import get_media_info, MusicPlayerGenerator, device_config, synthesize_fusion_frame, hide_window_from_taskbar, MusicCachePool, generate_cache_id, load_file2RGBImage

class ScreenShowApp:
    """系统托盘和播放器窗口的主应用程序"""
    def __init__(self):
        # 显示器基本参数
        self.monitor_true_width = 1440
        self.monitor_true_height = 2560
        # 应用状态控制
        self.is_running = True # 应用主循环运行状态
        # 现在的歌曲缓存id
        self.now_cache_id = ""
        # 缓存池
        self.tile_cache_pool = MusicCachePool(max_size=50)
        # 现在合成tile图片内容（BGR 数组）
        self.img_content = None
        # tile图片生成器
        self.global_frame_generator = MusicPlayerGenerator(1.5, 2.5, 1.5)
        # 创建OpenCV窗口名字
        self.window_name = "music3dc1image"
        self.initialize_cv_window()
        # 启动系统托盘图标
        self.setup_tray_icon()
        
    def setup_tray_icon(self):
        """创建系统托盘图标和菜单"""
        # 创建托盘图标图像
        image = Image.new('RGB', (64, 64), (255, 255, 255))
        dc = ImageDraw.Draw(image)
        dc.rectangle([16, 16, 48, 48], fill=(0, 100, 200))
        
        # 创建菜单项
        menu_items = [
            pystray.MenuItem('退出', self.quit_action)
        ]
        
        # 创建托盘图标
        self.icon = pystray.Icon("music3dc1", image, "music3dc1 app", menu=pystray.Menu(*menu_items))
        
        # 在单独线程中运行托盘图标
        self.tray_thread = threading.Thread(target=self.icon.run, daemon=True)
        self.tray_thread.start()
    
    def initialize_cv_window(self):
        # 获取所有监视器信息
        from screeninfo import get_monitors
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
                hide_window_from_taskbar("music3dc1image")
                break
    
    def quit_action(self):
        """退出菜单项回调，应用生命周期结束必须调用"""
        self.is_running = False

        # print("Stop icon...")
        self.icon.stop()
        time.sleep(1)  # 等待图标线程结束
        # print("Destroying windows and exiting...")
        cv2.destroyWindow(self.window_name)
        cv2.waitKey(1)  # 确保窗口被销毁

        # print("Application quit")
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
            print(f"图片尺寸与显示器不匹配，跳过绘制")
            print(f"图片尺寸: {img_w}x{img_h}")
            print(f"显示器尺寸: {self.monitor_true_width}x{self.monitor_true_height}")
        return frame
    
    def generate_image(self):
        """重新生成当前歌曲的播放器tile和fusion图片"""
        time.sleep(0.5)  # 等待半秒，确保封面文件已更新
        music_info = asyncio.run(get_media_info(get_cover=True))
        # 生成新的tile图片，并进行fusion处理
        # print(f"Get new music cover: {music_info}")
        tile_image = self.global_frame_generator.generate_full_canvas(music_info)
        final_fusion_image = synthesize_fusion_frame(tile_image, device_config)
        # 更新fusion图片到当前显示内容
        self.img_content = final_fusion_image
        # 将final_tile_image加入缓存池
        self.tile_cache_pool.add_key(generate_cache_id(music_info), final_fusion_image)
        # 此外再将 反着的播放状态 缓存一份，方便切换播放状态时快速加载
        music_info["playback_status"] = 0 if music_info.get('playback_status', 1) == 1 else 1
        tile_image = self.global_frame_generator.generate_full_canvas(music_info)
        final_fusion_image = synthesize_fusion_frame(tile_image, device_config)
        self.tile_cache_pool.add_key(generate_cache_id(music_info), final_fusion_image)
        
        
    
    def on_music_updated(self, music_cache_id):
        """当音乐state发生更新时"""
        self.now_cache_id = music_cache_id
        # 如果缓存池中已有该fusion后的图片，则直接加载
        if self.tile_cache_pool.has_key(music_cache_id):
            # print(f"Load tile image from cache: {music_cache_id}")
            cache_file_path = self.tile_cache_pool.get_cache_file_path(music_cache_id)
            RGB_image = load_file2RGBImage(cache_file_path)
            # 提取Image的RGB数组转换成 BGR，更新到 self.img_content
            self.img_content = np.array(RGB_image)[:,:,::-1]
        else:
            # 重新生成图片（generate_image内将新图片加入缓存池）
            # 用新的线程运行 global_frame_generator.generate_full_canvas(music_info)
            gen_thread = threading.Thread(target=self.generate_image)
            gen_thread.start()


    def run(self):
        """主运行循环"""
        print("应用已启动, 快捷键: [ESC] 退出")
        self.img_content = None
        
        while self.is_running:
            # 创建黑色背景
            frame = np.zeros((self.monitor_true_width, self.monitor_true_height, 3), dtype=np.uint8)
            
            # # 更新进度（如果正在播放）
            # if self.music_is_playing:
            #     self.progress += self.speed
            #     if self.progress >= 100:
            #         self.progress = 0  # 循环回到0
            # 绘制进度条
            # frame = self.draw_progress_bar(frame, self.progress)

            # 绘制图片
            frame = self.draw_image(frame, self.img_content)

            # 获取当前播放歌曲(封面先不获取)
            music_info = asyncio.run(get_media_info(get_cover=False))
            music_cache_id = generate_cache_id(music_info)
            if music_cache_id != self.now_cache_id:
                self.on_music_updated(music_cache_id)
                
            
            # 显示帧 反转显示
            cv2.imshow(self.window_name, frame)
            
            # 处理键盘输入
            key = cv2.waitKey(100) & 0xFF
            if key == 27:  # ESC键退出
                self.quit_action()
                break
            
            time.sleep(0.1)  # 控制更新频率