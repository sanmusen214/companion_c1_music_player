# 仿照 Meting API 获取网易云音乐封面 URL
# 给定一个网易云音乐的歌曲 ID，返回该歌曲的封面 URL

import requests
import hashlib
import base64
import json

def _encrypt_id(id_str):
    """
    网易云音乐 ID 加密算法 (仿 Meting)
    用于生成图片 URL 的 encrypted ID
    """
    magic = list('3go8&$8*3*3h0k(2)2')
    song_id = list(str(id_str))
    magic_len = len(magic)
    
    # 1. 字符异或处理
    # 使用 bytearray 存储处理后的字节数据，相当于 nodejs Buffer
    result_bytes = bytearray()
    for i, char in enumerate(song_id):
        # 取对应位置的 magic 字符
        magic_char = magic[i % magic_len]
        # 异或运算
        xor_val = ord(char) ^ ord(magic_char)
        # 存入 bytearray
        result_bytes.append(xor_val)
        
    # 2. MD5 哈希
    m = hashlib.md5()
    m.update(result_bytes)
    digest = m.digest()
    
    # 3. Base64 编码
    base64_str = base64.b64encode(digest).decode('utf-8')
    
    # 4. 替换特殊字符以适配 URL (仿 Meting 逻辑)
    result = base64_str.replace('/', '_').replace('+', '-')
    
    return result

def get_music_cover_url(song_id, size=300):
    """
    获取网易云音乐歌曲封面 URL
    :param song_id: 歌曲 ID (int or str)
    :param size: 图片尺寸 (默认 300x300)
    :return: 图片 URL (str) 或 None
    """
    try:
        # 1. 获取歌曲详情
        # 使用简单的 Web API 获取歌曲详情，无需复杂加密
        # 注意：这里为了简化，直接使用了 Web 接口，效果等同于 Meting 调用 song 接口
        api_url = f"http://music.163.com/api/song/detail/?id={song_id}&ids=[{song_id}]"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'http://music.163.com/'
        }
        
        res = requests.get(api_url, headers=headers, timeout=5)
        
        if res.status_code != 200:
            print(f"Failed to get song info: HTTP {res.status_code}")
            return None
            
        data = res.json()
        
        # 2. 解析 album 信息
        if 'songs' not in data or not data['songs']:
            print(f"Song {song_id} not found in Netease.")
            return None
            
        song_info = data['songs'][0]
        album_info = song_info.get('album', {})
        
        # 3. 提取 picId 或 picUrl
        pic_id = album_info.get('picId')
        pic_url = album_info.get('picUrl')
        
        # 优先使用 picId 通过算法生成 URL (模仿 Meting 的行为)
        if pic_id:
            encrypted_id = _encrypt_id(pic_id)
            return f"https://p3.music.126.net/{encrypted_id}/{pic_id}.jpg?param={size}y{size}"
            
        # 如果只有 picUrl，直接使用并添加尺寸参数
        if pic_url:
            return f"{pic_url}?param={size}y{size}"
            
        return None
        
    except Exception as e:
        print(f"Error getting cover url in get_music_cover_url: {e}")
        return None

if __name__ == "__main__":
    # 测试代码
    test_id = 35847388 # Hello - Adele
    url = get_music_cover_url(test_id)
    print(f"Cover URL for {test_id}: {url}")
