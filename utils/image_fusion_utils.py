import numpy as np
import os
import json
from Cryptodome.Cipher import AES
import cv2
import base64
from hashlib import md5
import cv2
import numpy as np
import os


def unpad(data):
    """AES解密后的数据去填充"""
    return data[:-(data[-1] if type(data[-1]) == int else ord(data[-1]))]

def bytes_to_key(data, salt, output=48):
    """从密码和盐生成AES密钥和IV"""
    assert len(salt) == 8, f"Salt length must be 8, got {len(salt)}"
    data += salt
    key = md5(data).digest()
    final_key = key
    while len(final_key) < output:
        key = md5(key + data).digest()
        final_key += key
    return final_key[:output]

def decrypt_device_config(encrypted_config: str, passphrase: bytes) -> dict:
    """解密设备配置"""
    encrypted = base64.b64decode(encrypted_config)
    assert encrypted[0:8] == b"Salted__", "Invalid encrypted data (missing Salted__ header)"
    salt = encrypted[8:16]
    key_iv = bytes_to_key(passphrase, salt, 32 + 16)
    key = key_iv[:32]
    iv = key_iv[32:]
    aes = AES.new(key, AES.MODE_CBC, iv)
    pt = unpad(aes.decrypt(encrypted[16:]))
    return json.loads(pt.decode('utf-8'))


def get_uv_from_choice(x, y, choice_float, imgs_count_x, imgs_count_y):
    """对应 GLSL 中的 get_uv_from_choice 逻辑"""
    imgs_count_all = imgs_count_x * imgs_count_y
    choice = np.floor(choice_float * imgs_count_all)
    
    # 逻辑：从右往左，从下往上 (根据代码中的注释和计算)
    choice_vec_x = imgs_count_x - 1.0 - np.mod(choice, imgs_count_x)
    choice_vec_y = np.floor(choice / imgs_count_x)
    
    # 归一化 UV 坐标
    u = (choice_vec_x + x) / imgs_count_x
    v = (choice_vec_y + y) / imgs_count_y
    return u, v

def synthesize_fusion_frame(quilt_image, config):
    """ 根据 quilt 图片(BGR array)和设备参数合成最终的 fusion 图片(BGR array) """
    # BGR image 转 np， 范围 [0, 1]
    quilt_np = np.array(quilt_image).astype(np.float32) / 255.0

    q_h, q_w, _ = quilt_np.shape

    # 2. 设备参数 (从 config 读取)
    slope = config['obliquity']    # 倾斜度
    interval = config['lineNumber'] # 线数/间距
    x0 = config['deviation']       # 偏移量
    
    output_w, output_h = 1440, 2560
    imgs_count_x, imgs_count_y = 8.0, 5.0
    # 计时
    start_time = cv2.getTickCount()
    # 3. 创建输出画布
    fusion_frame = np.zeros((output_h, output_w, 3), dtype=np.float32)

    # 4. 模拟片元着色器采样过程
    # 生成输出网格的归一化坐标 [0, 1]
    yy, xx = np.mgrid[0:output_h, 0:output_w]
    pos_x = xx / (output_w - 1)
    pos_y = 1.0 - (yy / (output_h - 1)) # 注意着色器中 (1 - pos.y)

    # 计算 RGB 三个通道的 bias 重采样逻辑
    for channel_idx in range(3): # 0:R, 1:G, 2:B
        bias = float(channel_idx)
        
        # GLSL: float x1 = (pos.x * _OutputSizeX + 0.5 + (1-pos.y) * _OutputSizeY * _Slope) * 3.0 + bias;
        # 对应代码中 get_choice_float 逻辑
        pixel_x = pos_x * output_w + 0.5
        pixel_y = (1.0 - pos_y) * output_h + 0.5
        
        x1 = (pixel_x + pixel_y * slope) * 3.0 + bias
        x_local = np.mod(x1 + x0, interval)
        choice_float = x_local / interval
        
        # 获取采样 UV
        u, v = get_uv_from_choice(pos_x, pos_y, choice_float, imgs_count_x, imgs_count_y)
        
        # 映射回 quilt 图片的像素索引
        sample_x = (u * (q_w - 1)).astype(np.int32)
        sample_y = ((1.0 - v) * (q_h - 1)).astype(np.int32) # 图片坐标系 y 反转
        
        # 限制范围
        sample_x = np.clip(sample_x, 0, q_w - 1)
        sample_y = np.clip(sample_y, 0, q_h - 1)
        
        # 采样对应通道的值
        fusion_frame[:, :, channel_idx] = quilt_np[sample_y, sample_x, channel_idx]

    end_time = cv2.getTickCount()
    elapsed_time = (end_time - start_time) / cv2.getTickFrequency()
    # print(f"处理时间: {elapsed_time:.3f} 秒")
    # 5. 色彩空间转换与保存
    # BGR array 范围放缩回 [0, 255]
    result = (fusion_frame * 255.0).astype(np.uint8)
    # 输出的 fusion array 是 BGR 的
    return result

# 步骤1：读取并解密设备配置
KEYCODE = b"3f5e1a2b4c6d7e8f9a0b1c2d3e4f5a6b"
appdata_path = os.getenv('APPDATA')
openstage_path = os.path.join(appdata_path, 'OpenstageAI', 'deviceConfig.json')
with open(openstage_path, 'r', encoding='utf-8') as f:
    device_info = json.load(f)
encrypted_config = device_info['config']
decrypted_data = decrypt_device_config(encrypted_config, KEYCODE)
device_config = decrypted_data['config']