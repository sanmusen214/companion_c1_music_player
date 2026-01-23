import os
import yaml

class ConfigManager:
    """配置管理器类"""
    
    def __init__(self, config_path: str = 'config.yaml'):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self):
        """
        安全加载YAML配置文件[4,8](@ref)
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)  # 使用safe_load避免安全风险[4,8](@ref)
                if config is None:
                    return {}
                print(f"配置文件加载成功: {self.config_path}")
                print(f"Music Status Position: {config.get('GetMusicStatus_position')}")
                return config
        except yaml.YAMLError as e:
            print(f"YAML解析错误: {e}")
            return {}
        except Exception as e:
            print(f"读取配置文件时出错: {e}")
            return {}
    
    def get(self, key, default = None):
        """
        获取配置值[4,5](@ref)
        """
        return self.config.get(key, default)

my_config = ConfigManager('software_config.yaml')