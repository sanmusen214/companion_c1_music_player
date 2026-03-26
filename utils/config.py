import os
import yaml
import sys
import traceback

class ConfigManager:
    """配置管理器类"""
    
    def __init__(self):
        self.version = "1.1.2"
        # 目标软件名称，用于创建专门的AppData目录，避免权限问题和路径问题
        self.target_name = "C1music"
        # 在用户的AppData目录下创建一个专门的文件夹来存储配置文件，避免权限问题和路径问题
        self.app_data_dir = os.path.expandvars(r"%APPDATA%\{}".format(self.target_name))
        # 解析启动时的命令行参数，支持 --dev 模式，在当前目录下存储文件
        if '--dev' in sys.argv:
            print("Running in development mode, using local data directory")
            self.app_data_dir = os.getcwd()
        os.makedirs(self.app_data_dir, exist_ok=True)
        # 配置文件路径，放在AppData目录下，避免权限问题和路径问题
        self.config_path = os.path.join(self.app_data_dir, "software_config.yaml")
        self.config = self._load_config()
    
    def _load_config(self):
        """
        安全加载YAML配置文件
        """
        if not os.path.exists(self.config_path):
            # 将当前文件夹的 software_config.yaml 复制到 config_path 目录下，作为初始配置文件
            if not os.path.exists('software_config.yaml'):
                print(f"Error: Initial configuration file 'software_config.yaml' not found in current directory {os.getcwd()}")
                return {}
            else:
                try:
                    with open('software_config.yaml', 'r', encoding='utf-8') as src_file:
                        config_content = src_file.read()
                    with open(self.config_path, 'w', encoding='utf-8') as dst_file:
                        dst_file.write(config_content)
                    print(f"Initial configuration file copied to {self.config_path}")
                except Exception as e:
                    print(f"Error copying initial configuration file: {traceback.format_exc()}")
                    return {}
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)  # 使用safe_load避免安全风险[4,8](@ref)
                if config is None:
                    return {}
                print(f"Configuration loaded successfully from {self.config_path}")
                print(f"Music Status Position: {config.get('GetMusicStatus_position')}")
                return config
        except yaml.YAMLError as e:
            print(f"Error parsing YAML configuration file: {traceback.format_exc()}")
            return {}
        except Exception as e:
            print(f"Error loading configuration file: {traceback.format_exc()}")
            return {}
    
    def get(self, key, default = None):
        """
        获取配置值
        """
        return self.config.get(key, default)
    
    def set(self, key, value):
        """
        设置配置值
        """
        self.config[key] = value

    def save_config(self, target_path = None):
        """
        保存配置到YAML文件
        """
        if target_path is None:
            target_path = self.config_path
        try:
            # 在最后加一个 version 字段，方便查看当前配置版本
            self.config['version'] = self.version
            with open(target_path, 'w', encoding='utf-8') as file:
                # 使用sort_keys=False保持原有字典顺序
                yaml.dump(self.config, file, allow_unicode=True, sort_keys=False)
                print(f"Configuration saved successfully to {target_path}")
        except Exception as e:
            print(f"Error saving configuration file: {traceback.format_exc()}")

my_config = ConfigManager()