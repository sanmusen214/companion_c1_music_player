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
NUM_BUCKETS = 20           # 频谱桶数量 (左右分为10个)
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
        self.freq_compensation = np.logspace(np.log10(0.33), np.log10(30.0), self.num_buckets)

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

        # 4. 改为选择出现次数最多的颜色 (Dominant Color)
        # 使用 K-Means 聚类，K=5，取最大的簇的中心作为主色
        data = np.float32(valid_pixels)
        
        # 聚类数量
        n_clusters = 5
        if len(data) < n_clusters:
             n_clusters = len(data)
             
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        flags = cv2.KMEANS_RANDOM_CENTERS
        
        # 聚类
        compactness, labels, centers = cv2.kmeans(data, n_clusters, None, criteria, 10, flags)
        
        # 5. 找到包含像素最多的簇
        unique_labels, counts = np.unique(labels, return_counts=True)
        dominant_label = unique_labels[np.argmax(counts)]
        
        dominant_color = centers[dominant_label]
        
        avg_h = dominant_color[0]
        avg_s = dominant_color[1]
        avg_v = dominant_color[2]
        
        # 6. 生成最终颜色
        # 判断封面下1/3区域的亮度，决定文字/UI是深色还是浅色
        start_y = int(new_h * 2 / 3)
        avg_bottom_h = np.mean(hsv_img[start_y:, :, 0])
        avg_bottom_s = np.mean(hsv_img[start_y:, :, 1])
        avg_bottom_v = np.mean(hsv_img[start_y:, :, 2])
            
        # 处理 h, 定义final_h
        # h代表色相，范围是0-179
        # 我们希望在色相上有一定的对比度，避免过于接近背景色
        # 如果 avg_bottom_h 很低，说明封面整体较暗，我们可以适当调整
        final_h = avg_h
        
        # 处理 s，定义final_s
        # 饱和度过低会导致颜色过于灰暗，我们可以设置一个最小饱和度
        final_s = np.clip(avg_s + 100, 50, 255)  # 最小饱和度为50，确保颜色不至于过于灰暗

        # 处理 v，定义final_v
        # 亮度过低会导致颜色在暗背景上难以辨识，我们可以根据背景的亮暗调整亮度
        # 如果封面下部很暗，提升亮度以确保对比度
        final_v = np.clip(avg_v + 60, 50, 255)  # 最小亮度为50，确保颜色不至于过于暗淡

        # 生成的final hsv映射到high_color RGB
        # low_color 是 high_color RGB 降低亮度和饱和度的版本
        high_color_hsv = np.array([[[final_h, final_s, final_v]]], dtype=np.uint8)
        low_color_hsv = np.array([[[final_h, final_s * 0.9, final_v * 0.9]]], dtype=np.uint8)  # 低层颜色更暗更灰

        high_color = cv2.cvtColor(high_color_hsv, cv2.COLOR_HSV2BGR)[0][0]
        low_color = cv2.cvtColor(low_color_hsv, cv2.COLOR_HSV2BGR)[0][0]
        
        
        return low_color, high_color

    def draw_spectrum(self, frame, bucket_values, music_screen_instance):
        """在帧底部绘制频谱图 (优化版)"""
        if bucket_values is None:
            return frame
        
        # 频谱区域尺寸
        spec_h = int(music_screen_instance.monitor_true_height / 7)
        spec_w = music_screen_instance.monitor_true_width
        
        # 布局参数
        PADDING_X = 50
        PADDING_Y = 20
        BUCKET_SPACING = 20
        LEVEL_SPACING = 4
        
        # 绘图区域尺寸
        draw_w = spec_w - 2 * PADDING_X
        draw_h = spec_h - 2 * PADDING_Y
        
        # 计算块大小
        block_width = (draw_w - (NUM_BUCKETS - 1) * BUCKET_SPACING) / NUM_BUCKETS
        block_height = (draw_h - (NUM_LEVELS - 1) * LEVEL_SPACING) / NUM_LEVELS
        
        # 底部基准线 Y 坐标
        base_y = music_screen_instance.monitor_true_height - PADDING_Y

        # 获取颜色
        color_low, color_high = music_screen_instance.cover_theme_color
        if color_low is None or color_high is None:
            color_low, color_high = COLOR_LOW_LEVEL, COLOR_HIGH_LEVEL
            
        # 预计算颜色表 (避免循环内重复计算)
        colors = []
        for j in range(NUM_LEVELS):
            ratio = j / max((NUM_LEVELS - 1), 1)
            b = int(color_low[0] * (1 - ratio) + color_high[0] * ratio)
            g = int(color_low[1] * (1 - ratio) + color_high[1] * ratio)
            r = int(color_low[2] * (1 - ratio) + color_high[2] * ratio)
            colors.append((b, g, r))

        for i in range(NUM_BUCKETS):
            val = bucket_values[i]
            if val > 1.0: val = 1.0
            if val < 0.0: val = 0.0
            active_levels = int(val * NUM_LEVELS)
            
            if active_levels == 0:
                continue

            x_start = int(PADDING_X + i * (block_width + BUCKET_SPACING))
            x_end = int(x_start + block_width)

            for j in range(active_levels):
                # j=0 是最底层
                y_end = int(base_y - j * (block_height + LEVEL_SPACING))
                y_start = int(y_end - block_height)
                
                # 直接从表里查颜色
                color = colors[j]
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

