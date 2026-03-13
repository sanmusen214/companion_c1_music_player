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

    def draw_spectrum(self, frame, bucket_values, monitor_width, monitor_height):
        """在帧底部绘制频谱图"""
        if bucket_values is None:
            return frame
        
        # 频谱区域尺寸
        spec_h = int(monitor_height / 6)
        spec_w = monitor_width
        start_y = monitor_height - spec_h
        
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
            b = int(COLOR_LOW_LEVEL[0] * (1 - ratio) + COLOR_HIGH_LEVEL[0] * ratio)
            g = int(COLOR_LOW_LEVEL[1] * (1 - ratio) + COLOR_HIGH_LEVEL[1] * ratio)
            r = int(COLOR_LOW_LEVEL[2] * (1 - ratio) + COLOR_HIGH_LEVEL[2] * ratio)
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
                    color = get_color(j, NUM_LEVELS)
                    cv2.rectangle(frame, (x_start, y_start), (x_end, y_end), color, -1)
                else:
                    color = COLOR_INACTIVE_BLOCK
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

