import soundcard as sc
import numpy as np
import cv2
import time
import warnings

# 忽略 soundcard 的 RuntimeWarning (例如 data discontinuity)
warnings.filterwarnings("ignore", category=RuntimeWarning, module="soundcard.mediafoundation")

# ==============================================================================
#                               自定义参数配置区域
# ==============================================================================

# 频谱参数
NUM_BUCKETS = 10           # 频谱桶数量 (左右分为10个)
NUM_LEVELS = 10            # 每个桶的高低层次数量 (高度分为10层)

# 颜色设置 (OpenCV 使用 BGR 格式)
# 颜色可以是固定值，也可以是 (Level 0 -> Level 9) 的渐变
COLOR_LOW_LEVEL = (0, 255, 0)     # 低音量颜色 (绿色)
COLOR_HIGH_LEVEL = (0, 0, 255)    # 高音量颜色 (红色)
COLOR_INACTIVE_BLOCK = (40, 40, 40) # 未被点亮的块颜色

# 音频处理参数
# 每帧录音耗时约：1024/44100≈0.0231024/44100≈0.023 秒 (23ms)。
SAMPLE_RATE = 44100        # 采样率 (Hz)
FFT_SIZE = 1024            # FFT窗口大小 (样本数), 越小刷新越快，但频率分辨率越低
GAIN_FACTOR = 50.0         # 增益系数，用于调整视觉灵敏度 (根据系统音量调整)
SMOOTHING_FACTOR = 0.5     # 平滑系数 (0.0 - 1.0), 越大越平滑，反应越慢

# 频率范围 (Hz)
MIN_FREQ = 20
MAX_FREQ = 14000           # 大部分音乐能量集中在16k以下

# ==============================================================================

class SpectrumAnalyzer:
    def __init__(self, sample_rate=SAMPLE_RATE, fft_size=FFT_SIZE, 
                 num_buckets=NUM_BUCKETS, min_freq=MIN_FREQ, max_freq=MAX_FREQ,
                 gain=GAIN_FACTOR, smoothing=SMOOTHING_FACTOR):
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.num_buckets = num_buckets
        self.gain = gain
        self.smoothing = smoothing
        
        self.mic = self._get_loopback_mic()
        if self.mic is None:
            raise RuntimeError("Can not find a loopback microphone. Please ensure your system supports audio loopback and that the necessary drivers are installed.")
             
        # 预先生成 fft 频率轴
        self.freqs = np.fft.rfftfreq(self.fft_size, 1.0 / self.sample_rate)
        
        # 定义 Log 刻度的频率桶边界
        self.bucket_boundaries = np.logspace(np.log10(min_freq), np.log10(max_freq), self.num_buckets + 1)
        
        # 找到这些边界对应在 FFT 结果数组中的索引
        self.bucket_indices = []
        for i in range(self.num_buckets):
            start_freq = self.bucket_boundaries[i]
            end_freq = self.bucket_boundaries[i+1]
            idx_start = np.searchsorted(self.freqs, start_freq)
            idx_end = np.searchsorted(self.freqs, end_freq)
            if idx_start == idx_end:
                idx_end += 1
            self.bucket_indices.append((idx_start, idx_end))
            
        self.prev_bucket_values = np.zeros(self.num_buckets)
        
        # 频率补偿曲线：削弱低频，大幅增强高频
        # 音乐频谱能量通常随频率增加而下降(粉红噪声特性)，因此需要对高频进行显著补偿
        # 这里使用对数增长曲线，范围从 0.5 (低频削弱一半) 到 10.0 (高频放大10倍)
        self.freq_compensation = np.logspace(np.log10(0.25), np.log10(20.0), self.num_buckets)

    def _get_loopback_mic(self):
        try:
            default_speaker = sc.default_speaker()
            print(f"detect Loopback device successfully")
            return sc.get_microphone(id=str(default_speaker.name), include_loopback=True)
        except Exception:
            try:
                mics = sc.all_microphones(include_loopback=True)
                for m in mics:
                    if m.isloopback:
                        print(f"exception fallback: find Loopback device")
                        return m
            except Exception:
                pass
        return None

    def start_listening(self):
        return self.mic.recorder(samplerate=self.sample_rate, blocksize=self.fft_size)

    def process_frame(self, audio_data):
        # 转为单声道
        if audio_data.shape[1] > 1:
            audio_mono = np.mean(audio_data, axis=1)
        else:
            audio_mono = audio_data.flatten()
            
        # FFT
        windowed_data = audio_mono * np.hanning(len(audio_mono))
        fft_result = np.fft.rfft(windowed_data)
        fft_magnitude = np.abs(fft_result) / self.fft_size

        # 映射到桶
        current_bucket_values = np.zeros(self.num_buckets)
        for i in range(self.num_buckets):
            idx_start, idx_end = self.bucket_indices[i]
            if idx_start >= len(fft_magnitude):
                continue
            real_end = min(idx_end, len(fft_magnitude))
            if real_end > idx_start:
                val = np.mean(fft_magnitude[idx_start:real_end])
                current_bucket_values[i] = val
        
        # 应用频率补偿曲线
        if hasattr(self, 'freq_compensation'):
            current_bucket_values *= self.freq_compensation

        # 增益和平滑
        current_bucket_values *= self.gain
        current_bucket_values = self.prev_bucket_values * self.smoothing + current_bucket_values * (1.0 - self.smoothing)
        self.prev_bucket_values = current_bucket_values
        
        return current_bucket_values
    
    @staticmethod
    def get_cover_theme_color(cover_img):
        """
        从封面图片中提取主色调，作为频谱颜色的基础。
        优化逻辑：优先提取高饱和度、高亮度的颜色，并强制提升亮度，
        确保在变暗的封面背景（尤其下三分之一区域）上能清晰显示歌词和UI。
        """
        if cover_img is None:
            return COLOR_LOW_LEVEL, COLOR_HIGH_LEVEL
        
        # 1. 缩小图片以加快处理 (使用 64x64 足够提取颜色特征)
        h, w = cover_img.shape[:2]
        scale = 64.0 / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        if new_w <= 0 or new_h <= 0:
             return COLOR_LOW_LEVEL, COLOR_HIGH_LEVEL
        
        small_img = cv2.resize(cover_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # 2. 转换为 HSV 空间处理 (Hue, Saturation, Value)
        hsv_img = cv2.cvtColor(small_img, cv2.COLOR_BGR2HSV)
        pixels = hsv_img.reshape(-1, 3)
        
        # 3. 筛选有效像素
        # 剔除过暗的像素 (V < 40)，这些在暗背景下无法提供对比度
        valid_mask = pixels[:, 2] > 40
        valid_pixels = pixels[valid_mask]
        
        if len(valid_pixels) == 0:
            # 如果全是黑的，返回高亮白色
            return (180, 180, 180), (255, 255, 255)

        # 4. 颜色评分机制 (Vibrancy Score)
        # 我们希望找到既有色彩(Saturation高)又比较亮(Value高)的颜色
        # Score = S * 1.5 + V * 1.0 (权重可调，偏重色彩)
        s_vals = valid_pixels[:, 1].astype(float)
        v_vals = valid_pixels[:, 2].astype(float)
        scores = s_vals * 1.5 + v_vals
        
        # 5. 取分数最高的前 10% 像素的平均值作为基准色
        top_k = max(1, int(len(valid_pixels) * 0.1))
        # 获取分数最高的索引
        top_indices = np.argsort(scores)[-top_k:]
        top_pixels = valid_pixels[top_indices]
        
        avg_h = np.mean(top_pixels[:, 0])
        avg_s = np.mean(top_pixels[:, 1])
        avg_v = np.mean(top_pixels[:, 2])
        
        # 6. 生成最终颜色
        # 判断封面下1/3区域的亮度，决定文字/UI是深色还是浅色
        start_y = int(new_h * 2 / 3)
        bottom_area = hsv_img[start_y:, :, 2]
        if bottom_area.size > 0:
            avg_bottom_v = np.mean(bottom_area)
        else:
            avg_bottom_v = 0
            
        # 根据背景亮度，在原主题色亮度基础上进行偏移
        # 背景越亮，主题色越暗；背景越暗，主题色越亮
        # 限制在 [180, 255] 之间，确保足够亮以看清
        final_v = np.clip(avg_v + 30, 150, 255)
            
        # 调整饱和度 (Saturation)
        # 如果由于封面本身就是黑白或低饱和度导致 avg_s 很低，
        # 则保持低饱和度(白色/灰色)，否则强行增加饱和度会产生杂色。
        # 如果有一定色彩(>20)，则限制在一个舒适的区间(60-200)，避免过于刺眼或太淡。
        final_s = avg_s
        if final_s < 20: 
            final_s = 0     # 认为是黑白/灰色系，直接使用纯白/灰
        else:
            final_s = np.clip(final_s, 60, 200) # 保持色彩鲜艳但不过分
        
        # 构建 High Color (用于歌词、频谱高位)
        high_hsv = np.array([[[avg_h, final_s, final_v]]], dtype=np.uint8)
        high_bgr = cv2.cvtColor(high_hsv, cv2.COLOR_HSV2BGR)[0][0]
        high_color = tuple(map(int, high_bgr))
        
        # 构建 Low Color (用于频谱低位，稍微暗一点或淡一点)
        # 这里的 Low Color 也可以通过降低亮度来实现
        low_v = final_v * 0.75
        low_hsv = np.array([[[avg_h, final_s, low_v]]], dtype=np.uint8)
        low_bgr = cv2.cvtColor(low_hsv, cv2.COLOR_HSV2BGR)[0][0]
        low_color = tuple(map(int, low_bgr))
        
        return low_color, high_color

    def draw_spectrum(self, frame, bucket_values, music_screen_instance):
        """在帧底部绘制频谱图"""
        if bucket_values is None:
            return frame
        
        # 频谱区域尺寸
        spec_h = int(music_screen_instance.monitor_true_height / 6)
        spec_w = music_screen_instance.monitor_true_width
        start_y = music_screen_instance.monitor_true_height - spec_h

        # 获取 封面低高主题色
        color_low, color_high = music_screen_instance.cover_theme_color
        if color_low is None or color_high is None:
            color_low, color_high = COLOR_LOW_LEVEL, COLOR_HIGH_LEVEL
        
        # 布局参数 (根据全屏宽度适当调整)
        PADDING_X = 50
        PADDING_Y = 20
        # 适当增大间距
        BUCKET_SPACING = 20
        # NUM_BUCKETS 从 utils 导入
        LEVEL_SPACING = 4
        
        # 绘图区域尺寸
        draw_w = spec_w - 2 * PADDING_X
        draw_h = spec_h - 2 * PADDING_Y
        
        block_width = (draw_w - (NUM_BUCKETS - 1) * BUCKET_SPACING) / NUM_BUCKETS
        block_height = (draw_h - (NUM_LEVELS - 1) * LEVEL_SPACING) / NUM_LEVELS
        
        # 颜色计算函数
        def get_color(level_idx, max_levels):
            ratio = level_idx / max((max_levels - 1), 1)
            b = int(color_low[0] * (1 - ratio) + color_high[0] * ratio)
            g = int(color_low[1] * (1 - ratio) + color_high[1] * ratio)
            r = int(color_low[2] * (1 - ratio) + color_high[2] * ratio)
            return (b, g, r)

        for i in range(NUM_BUCKETS):
            amplitude = np.clip(bucket_values[i], 0.0, 1.0)
            active_levels = int(amplitude * NUM_LEVELS)
            
            x_start = int(PADDING_X + i * (block_width + BUCKET_SPACING))
            x_end = int(x_start + block_width)

            for j in range(NUM_LEVELS):
                # j=0 是最底层，y轴向下增加
                # 在屏幕底部区域绘制
                y_end_local = spec_h - PADDING_Y - j * (block_height + LEVEL_SPACING)
                y_end = int(start_y + y_end_local)
                y_start = int(y_end - block_height)
                
                if j < active_levels:
                    # 激活块，颜色根据层级渐变
                    color = get_color(j, NUM_LEVELS)
                    cv2.rectangle(frame, (x_start, y_start), (x_end, y_end), color, -1)
        return frame

def main():
    try:
        analyzer = SpectrumAnalyzer()
        visualizer = SpectrumVisualizer()
        
        print(f"开始监听设备: {analyzer.mic.name}")
        print("按下 'q' 键退出程序...")
        
        with analyzer.start_listening() as recorder:
            while True:
                try:
                    audio_data = recorder.record(numframes=analyzer.fft_size)
                    bucket_values = analyzer.process_frame(audio_data)
                    key = visualizer.draw(bucket_values)
                    if key == ord('q'):
                        break
                except Exception as e:
                    print(f"处理出错: {e}")
                    time.sleep(1)
                    continue
                    
    except Exception as e:
        print(f"初始化失败: {e}")
    finally:
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

