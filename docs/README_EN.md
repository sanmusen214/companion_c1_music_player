<img src="./imgs/picfuse.webp"/>

# companion_c1_music_player

<div align="center">
<a href="../README.md">[中文]</a> | [English]
</div>
<br/>

Music cover secondary screen display for Naked-eye 3D Freedom Quadrant C1 screen (Companion1).

Compatible music software: netease, qq, kugou, kuwo, soda, spotify, apple... (Refer to [NowPlayingService](https://github.com/Widdit/now-playing-service/blob/master/external_programs/AudioService/GetMusicStatus/Program.cs)). 
To detect a music platform, you need to start the software, then right-click the tray icon -> **Music Platform** to select the platform you want to detect; otherwise, it will fail to retrieve song information and display only a black screen.

# Usage

> Regardless of the method used to run the program, the computer must be a Windows 64-bit system and must have run [OpenStageAI](https://www.openstageai.com/download).

## Download from Releases

1. Download the compressed package from [Releases](https://github.com/sanmusen214/companion_c1_music_player/releases) and extract it.
2. Double-click the exe file to run. The configuration file is located in `AppData/Roaming/C1music/`.
3. Right-click the tray icon -> **Music Platform** to select the platform to detect; otherwise, it will fail to retrieve song information and display only a black screen.

## Run from Source Code (Development)

1. Please use a Python 3.10.x environment. Use `git clone https://github.com/sanmusen214/companion_c1_music_player.git` to clone this project, cd into the folder, and run `pip install -r requirements.txt` in the command line to install dependencies.
2. Download the `AudioService` folder from [NowPlayingService](https://github.com/Widdit/now-playing-service/tree/master/Assets/AudioService).
3. Modify the `GetMusicStatus_position` configuration item in the `software_config.yaml` file to point to the `GetMusicStatus.exe` file path inside the downloaded `AudioService` folder.
4. Execute `python main.py --dev` to run the project. The `--dev` parameter forces the application to read the configuration file from the current running directory.
5. Right-click the tray icon -> **Music Platform** to select the platform to detect; otherwise, it will fail to retrieve song information and display only a black screen.

# Multi-view Fusion

The `synthesize_fusion_frame` function in `utils/image_fusion_utils.py` can convert the input `quilt_np` (composed of images from different perspectives arranged in 5 rows and 8 columns. Starting from the first row, from left to right, these are perspective images observing the object in a counter-clockwise direction) into an optical flow synthesized image (height 2560, width 1440) based on the parsed screen configuration file (the parsing method can be found at the bottom of the same py file).

# Notice

OpenCV and Pillow interpret image channel orders differently. OpenCV reads/creates/saves images in BGR order, while Pillow does so in RGB order. If pixel channel conversion (`cvtColor`) is not used, ensure the image processing library matches the channel order of the image array data.

# Build (Development)

After installing pyinstaller, execute `python build.py --dev` (the `--dev` parameter forces the application to read the configuration file from the current running directory). The `dist` directory will contain the packaged program folder.

# Thanks

[NowPlayingService](https://github.com/Widdit/now-playing-service?tab=readme-ov-file): A component for displaying song titles in live broadcasts. It detects song information and progress currently playing on various music software and provides a query API interface. Suitable for OBS, Bilibili Link, and other live streaming software.
