import numpy as np
import cv2
from PIL import Image

def load_file2RGBImage(path):
    """ 使用PIL加载图片并转换为RGB格式 """
    img = Image.open(path).convert("RGB")
    return img

def save_BGRimage2file(image_array: np.array, output_path: str):
    """ 保存 BGR 格式的 numpy array 图片到文件(文件图片为 RGB 格式) """
    cv2.imwrite(output_path, image_array)
    