import numpy as np
from PIL import Image
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from .image_save_load import load_file2RGBImage
from utils.config import my_config

class MusicPlayerGenerator:
    """获取音乐并制作播放器页面，输出合成后的 Tile 图片"""
    def __init__(self, cover_intensity, background_intendisy, word_intensity):
        self.info = None
        # 平移强度系数：1.0 为标准值，增大则立体感/位移更强，减小则更平缓
        self.cover_intensity = cover_intensity
        self.background_intendisy = background_intendisy
        self.word_intensity = word_intensity
        
        self.canvas_w, self.canvas_h = 4320, 4800
        self.sub_w, self.sub_h = 540, 960
        self.rows, self.cols = 5, 8
        self.bg_scale_factor = 1.3
        # 图数据缓存
        self.cover_img_data = None
        self.blur_bg_data = None
        
        # 字体设置：黑体
        self.font_path = "simhei.ttf" 

    def _guided_filter(self, I, p, winSize, eps):
        """
        引导滤波实现[5,7](@ref)
        参数:
            I: 引导图像 (单通道，归一化到[0,1])
            p: 输入图像 (单通道，归一化到[0,1]) 
            winSize: 滤波窗口大小，如(16, 16)
            eps: 正则化参数
        """
        # 计算均值[5](@ref)
        mean_I = cv2.blur(I, winSize)
        mean_p = cv2.blur(p, winSize)
        mean_II = cv2.blur(I * I, winSize)
        mean_Ip = cv2.blur(I * p, winSize)
        
        # 计算方差和协方差[7](@ref)
        var_I = mean_II - mean_I * mean_I
        cov_Ip = mean_Ip - mean_I * mean_p
        
        # 计算系数a和b[7](@ref)
        a = cov_Ip / (var_I + eps)
        b = mean_p - a * mean_I
        
        # 对系数进行均值平滑[5](@ref)
        mean_a = cv2.blur(a, winSize)
        mean_b = cv2.blur(b, winSize)
        
        # 生成输出图像[7](@ref)
        q = mean_a * I + mean_b
        return q

    def _guided_filter_color(self, image, winSize=(45, 45), eps=0.01**2):
        """
        对彩色图像进行引导滤波[5](@ref)
        使用原图作为引导图，实现边缘保持的模糊效果
        """
        # 将图像转换为浮点型并归一化[5](@ref)
        if image.dtype != np.float32:
            image_0_1 = image.astype('float32') / 255.0
        else:
            image_0_1 = image
        
        # 分离通道并分别处理[5](@ref)
        b, g, r = cv2.split(image_0_1)
        
        # 对每个通道进行引导滤波（使用原通道作为引导图）[5](@ref)
        gf_b = self._guided_filter(b, b, winSize, eps)
        gf_g = self._guided_filter(g, g, winSize, eps)
        gf_r = self._guided_filter(r, r, winSize, eps)
        
        # 合并通道[5](@ref)
        filtered_image = cv2.merge([gf_b, gf_g, gf_r])
        
        # 转换回8位图像[5](@ref)
        filtered_image_8bit = (filtered_image * 255).astype('uint8')
        return filtered_image_8bit

    def _apply_guided_filter(self, pil_image, blur_amount):
        """
        使用引导滤波器实现背景虚化效果[5,7](@ref)
        替换原来的高斯模糊方法，提供更好的边缘保持特性
        """
        # 将PIL图像转换为OpenCV格式 (RGB -> BGR)
        cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        
        # 根据blur_amount调整引导滤波参数[5](@ref)
        # 窗口大小与模糊强度成正比，确保为奇数
        base_win_size = max(5, int(blur_amount * 2))
        win_size = (base_win_size | 1, base_win_size | 1)  # 确保为奇数
        
        # 正则化参数，控制平滑程度[7](@ref)
        eps = 0.01**2
        
        # 应用引导滤波[5](@ref)
        blurred_cv_image = self._guided_filter_color(cv_image, winSize=win_size, eps=eps)
        
        # 转换回PIL图像格式 (BGR -> RGB)
        blurred_pil_image = Image.fromarray(cv2.cvtColor(blurred_cv_image, cv2.COLOR_BGR2RGB))
        
        return blurred_pil_image

    def _draw_controls(self, draw, word_offset, color=(220, 220, 220, 200)):
        """绘制几何控制图标"""
        center_x = self.sub_w // 2 + word_offset
        center_y = my_config.get("Control_y_position_percent") * self.sub_h
        side = 50 # 按钮图标正方形边长
        s = side // 2
        pn_width = 40 # 上一首下一首按钮三角宽度
        pn_ar_w = side - pn_width # 上一首下一首按钮矩形宽度
        gap = 120 # 播放按钮与上一首下一首的间隔
        pause_w = 10 # 暂停按钮单个矩形宽度
        # 上一首
        lx = center_x - gap
        draw.polygon([(lx, center_y), (lx+pn_width, center_y-s), (lx+pn_width, center_y+s)], fill=color)
        draw.rectangle([lx-pn_ar_w, center_y-s, lx, center_y+s], fill=color)
        is_playing = self.info.get("playback_status", 0) == 1
        if is_playing:
            # 播放
            draw.polygon([(center_x-s, center_y-s), (center_x-s, center_y+s), (center_x+s, center_y)], fill=color)
        else:
            # 暂停
            draw.rectangle([center_x - s, center_y - s, center_x - s + pause_w, center_y + s], fill=color)
            draw.rectangle([center_x + s - pause_w, center_y - s, center_x + s, center_y + s], fill=color)
        # 下一首
        rx = center_x + gap
        draw.polygon([(rx, center_y), (rx-pn_width, center_y-s), (rx-pn_width, center_y+s)], fill=color)
        draw.rectangle([rx, center_y-s, rx+pn_ar_w, center_y+s], fill=color)

    def _draw_title(self, draw, word_offset):
        """绘制标题，自动适应宽度"""
        # --- 标题自适应逻辑开始 ---
        title = self.info.get('title', 'Unknown Title')
        max_width = int(self.sub_w * my_config.get("Max_title_width_percent"))  # 设置最大允许宽度为画布的 85%
        current_font_size = 100             # 初始字号
        min_font_size = 60                  # 最小允许字号
        
        # 1. 动态缩小字号
        temp_font = ImageFont.truetype(self.font_path, current_font_size)
        bbox = draw.textbbox((0, 0), title, font=temp_font)
        tw = bbox[2] - bbox[0]

        while tw > max_width and current_font_size > min_font_size:
            current_font_size -= 10
            temp_font = ImageFont.truetype(self.font_path, current_font_size)
            bbox = draw.textbbox((0, 0), title, font=temp_font)
            tw = bbox[2] - bbox[0]

        # 2. 如果缩小到最小字号还放不下，则进行截断
        if tw > max_width:
            while tw > max_width and len(title) > 1:
                title = title[:-1]
                bbox = draw.textbbox((0, 0), title + "...", font=temp_font)
                tw = bbox[2] - bbox[0]
            title = title + "..."

        # 3. 居中计算
        tx = (self.sub_w - tw) // 2 + word_offset
        text_color = (240, 240, 240)
        shadow_color = (40, 40, 40)
        
        y_position = int(my_config.get("Title_y_position_percent")*self.sub_h)
        # 绘制阴影和正文
        # draw.text((tx + 1, y_position+1), title, font=temp_font, fill=shadow_color)
        draw.text((tx, y_position), title, font=temp_font, fill=text_color)
        # --- 标题自适应逻辑结束 ---

    def _draw_cover(self, base_img, cover_img, fg_offset):
        """绘制封面图"""
        # 封面图
        cv_size_percent = my_config.get("Cover_size_percent")
        cw, ch = int(self.sub_w * cv_size_percent), int(self.sub_w * cv_size_percent)
        cover_res = cover_img.resize((cw, ch), Image.Resampling.LANCZOS)
        cover_x = (self.sub_w - cw) // 2 + fg_offset
        cover_y = 80
        # 创建一个比封面大 n 像素的模糊后的封面作为底层
        if my_config.get("Has_cover_blur_border"):
            added_size = 8
            cover_blur = cover_img.resize((cw + added_size, ch + added_size), Image.Resampling.LANCZOS)
            cover_blur = cover_blur.filter(ImageFilter.GaussianBlur(radius=15))
        # cover 和比cover大一圈的cover_blur 贴上
        base_img.paste(cover_blur, (cover_x - added_size // 2, cover_y - added_size // 2))
        base_img.paste(cover_res, (cover_x, cover_y))

    def _draw_background(self, bg_offset):
        """根据封面图绘制模糊背景"""
        # --- 1. 背景平移 (Crop 模式防露底) ---
        
        bg_scale = self.bg_scale_factor # 背景缩放比例
        bg_w, bg_h = int(self.sub_w * bg_scale), int(self.sub_h * bg_scale)
        bg = Image.fromarray(self.blur_bg_data)
        
        # 背景位移：k > 0 (右侧视角) 看到背景的右侧部分，即取样框向右移
        bg_shift = int(bg_offset)
        # 这里是裁剪部分移动方向，和图的假设移动方向相反
        left = (bg_w - self.sub_w) // 2 - bg_shift
        top = (bg_h - self.sub_h) // 2
        bg_final = bg.crop((left, top, left + self.sub_w, top + self.sub_h))
        draw = ImageDraw.Draw(bg_final)
        return bg_final, draw

    def create_view(self, n):
        """PIL 绘制第 n 个左右平移视角，输出BGR格式的numpy"""
        # 计算相对中心的偏移步数 (k)
        center_index = 20  # 中心视角索引
        k = n - center_index
        # 从self.cover_img_data拷贝封面图
        cover_img = Image.fromarray(self.cover_img_data)
            
        # --- 1. 背景绘制(此项必须第一个绘制) ---
        bg_final, draw = self._draw_background(int(k * self.background_intendisy))
        # --- 2. 前景 UI ---
        self._draw_cover(bg_final, cover_img, int(k * self.cover_intensity))
        word_offset = int(k * self.word_intensity)
        self._draw_title(draw, word_offset)
        self._draw_controls(draw, word_offset)
        # ===== 输出 =====
        # Image 绘图后的 RGB 转为 GBR 格式 numpy 输出
        view_cv = cv2.cvtColor(np.array(bg_final), cv2.COLOR_RGB2BGR)
        # 水平小像素平滑，减少色散
        # view_cv = cv2.GaussianBlur(view_cv, (3, 1), 0)
        return view_cv

    def generate_full_canvas(self, music_info):
        """合并 40 个平移视角，输出最终 Tile 大图的numpy (BGR格式)"""
        self.info = music_info
        full_canvas = np.zeros((self.canvas_h, self.canvas_w, 3), dtype=np.uint8)
        # 加载封面图
        if self.info is None or 'cover_path' not in self.info or self.info['cover_path'] is None:
            # 无封面图时使用默认灰色背景
            cover_img = Image.new("RGB", (500, 500), (100, 100, 100))
        else:
            cover_img = load_file2RGBImage(self.info['cover_path'])
        self.cover_img_data = np.array(cover_img)
        # 预先生成模糊化的背景图数据
        bg_scale = self.bg_scale_factor # 背景缩放比例
        bg_w, bg_h = int(self.sub_w * bg_scale), int(self.sub_h * bg_scale)
        # 拷贝一份封面图用于背景模糊处理
        _bg = cover_img.copy()
        _bg = _bg.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
        # 高斯模糊
        blur_bg = _bg.filter(ImageFilter.GaussianBlur(radius=my_config.get("Background_blur")))
        # 变暗处理
        enhancer = Image.new("RGB", (bg_w, bg_h), (30, 30, 30))
        blur_bg = Image.blend(blur_bg, enhancer, alpha=my_config.get("Background_dark_percent"))
        self.blur_bg_data = np.array(blur_bg)
        for idx in range(40):
            r, c = divmod(idx, 8) # 计算行和列 (5行8列)
            # print(f"Generating view {idx+1}/40...", end='\r')
            
            view_img = self.create_view(idx)
            
            y_s, x_s = r * self.sub_h, c * self.sub_w
            full_canvas[y_s : y_s + self.sub_h, x_s : x_s + self.sub_w] = view_img
            
        return full_canvas
