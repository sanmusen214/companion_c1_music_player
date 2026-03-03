<img src="./docs/imgs/picfuse.webp"/>

# companion_c1_music_player

适用于裸眼3d自由象限c1屏 (Companion1) 的音乐封面副屏显示

兼容音乐软件：netease,qq,kugou,kuwo,soda,spotify,apple,ayna,potplayer,foobar,lx,huahua,musicfree,bq (参见 [NowPlayingService](https://github.com/Widdit/now-playing-service/blob/master/external_programs/AudioService/GetMusicStatus/Program.cs) 说明)

# 使用

1. 修改 software_config.yaml 内的 `Music_platform` 配置项目，使其为上述音乐软件参数名字之一
2. 运行方式
    1. 从本项目 releases 下载的压缩包解压后，找到 exe 文件直接双击运行。
    2. python 源码用户请使用 python=3.10 环境，命令行运行 `pip install -r requirements.txt` 安装依赖。然后从 [NowPlayingService](https://github.com/Widdit/now-playing-service/tree/master/Assets/AudioService) 下载 AudioService 文件夹内的文件，并修改配置文件 software_config.yaml 内的 `GetMusicStatus_position` 配置项目，使其指向下载下来的文件夹内的 `GetMusicStatus.exe`。最后执行 `python main.py` 运行本项目。

# 多视角融合

`utils/image_fusion_utils.py` 里的 `synthesize_fusion_frame` 能够将输入的 quilt_np (由5行8列不同视角的图像组成。从第一行开始从左到右依次是环绕被视物体逆时针方向观察的视角图像) 根据解析后的屏幕配置文件（解析方法在同py文件底部）转换为光流合成后的图像（高2560宽1440）

# 注意

OpenCv 和 Pillow 对图像通道解释顺序不同。OpenCV 以 BGR 顺序读取/创建/保存图像，Pillow 以 RGB 顺序读取/创建/保存图像，未使用像素通道转换 `cvtColor` 时，图片存取的库要与图像数组数据的通道顺序对应。

# 打包

安装 pyinstaller 后执行 `python build.py`

# Thanks

[NowPlayingService](https://github.com/Widdit/now-playing-service?tab=readme-ov-file): 直播歌曲歌名显示组件。检测各类音乐软件正在播放的歌曲信息以及进度条信息，提供查询 API 接口。适用于 OBS、直播姬等各类直播软件。