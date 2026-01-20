import os
from PIL import Image, ImageDraw
from .image_save_load import save_BGRimage2file
import base64
import hashlib
# 缓存缓存池
def simple_hash(s):
    """简单的base64 hash函数"""
    hash_object = hashlib.md5(s.encode('utf-8'))
    hash_bytes = hash_object.digest()
    hash_b64 = base64.urlsafe_b64encode(hash_bytes).decode('utf-8').rstrip('=')
    return hash_b64

def generate_cache_id(name_or_dict, artist=None, playback_status=None):
    """生成音乐的tile的唯一ID"""
    # 如果 name_or_dict 是字典，则提取所需字段
    if isinstance(name_or_dict, dict) and artist is None and playback_status is None:
        name = name_or_dict.get('title', '')
        artist = name_or_dict.get('artist', '')
        playback_status = name_or_dict.get('playback_status', 1)
    else:
        name = name_or_dict
    return f"{simple_hash(name)}{simple_hash(artist)}{playback_status}"
    
class MusicCachePool:
    """
    FIFO 音乐缓存池，同步管理多个音乐tile图片的缓存字典和文件，超过最大数量时删除老的缓存
    """
    def __init__(self, max_size=30):
        self.cache_dict = {} # 3.8后的 dict 有顺序键特性，可以用作FIFO
        self.read_folder_path = "cache_data/"
        self.file_extension = ".png"
        self.max_size = max_size
        self.initialize()
    
    def initialize(self):
        """读取缓存文件夹，初始化缓存池，所有png图片文件名作为缓存ID"""
        os.makedirs(self.read_folder_path, exist_ok=True)
        
        for filename in os.listdir(self.read_folder_path):
            if filename.endswith(self.file_extension):
                # 去掉文件扩展名
                cache_id = os.path.splitext(filename)[0]
                self.cache_dict[cache_id] = None  # 初始时缓存对象为None

    def get_cache_file_path(self, cache_id):
        """根据缓存ID获取对应的缓存文件路径"""
        return os.path.join(self.read_folder_path, f"{cache_id}{self.file_extension}")

    def add_key(self, cache_id, cache_file:Image):
        """添加新的缓存ID到缓存池，cache_file为BGR格式的numpy array图片"""
        if len(self.cache_dict) >= self.max_size:
            # 删除多余的 n 个最老缓存
            need_remove = len(self.cache_dict) - self.max_size + 1
            for delete_key in list(self.cache_dict.keys())[:need_remove]:
                # 删除最老的缓存ID
                del self.cache_dict[delete_key]
                # 同时删除对应的缓存文件
                cache_file_path = self.get_cache_file_path(delete_key)
                if os.path.exists(cache_file_path):
                    os.remove(cache_file_path)
        
        if not self.has_key(cache_id):
            # 添加新的缓存ID
            self.cache_dict[cache_id] = None
            # 创建对应的缓存文件
            cache_file_path = self.get_cache_file_path(cache_id)
            save_BGRimage2file(cache_file, cache_file_path)
    
    def has_key(self, cache_id):
        """检查缓存池中是否存在该缓存ID"""
        return cache_id in self.cache_dict
    
    def clear_cache(self):
        """清理所有缓存"""
        self.cache_dict.clear()

if __name__ == "__main__":
    print(generate_cache_id("ウルトラマンメビウス", "ArtistName", "Playing"))  # 示例调用