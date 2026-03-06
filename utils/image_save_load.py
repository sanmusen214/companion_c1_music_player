import numpy as np
import cv2
from PIL import Image
import os
import traceback

def load_file2RGBImage(path):
    """ 使用PIL加载图片并转换为RGB格式 """
    img = Image.open(path).convert("RGB")
    return img

def save_BGRimage2file(image_array: np.array, output_path: str):
    """ 保存 BGR 格式的 numpy array 图片到文件(文件图片为 RGB 格式) """
    # cv2.imwrite 不支持 Windows 下的中文路径，这里改用 imencode + open
    filename, ext = os.path.splitext(output_path)
    if not ext:
        ext = ".png"
        
    success, buffer = cv2.imencode(ext, image_array)
    if success:
        with open(output_path, "wb") as f:
            f.write(buffer)
        print(f"Image saved successfully: {output_path}")
    else:
        print(f"Error encoding image to {ext} format for saving to {output_path}, {traceback.format_exc()}")
    