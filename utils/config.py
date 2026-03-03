import os
import yaml

class ConfigManager:
    """配置管理器类"""
    
    def __init__(self, config_path: str = 'config.yaml'):
        self.version = "1.0.1"
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self):
        """
        安全加载YAML配置文件
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
                print(f"配置文件保存成功: {target_path}")
        except Exception as e:
            print(f"保存配置文件时出错: {e}")

my_config = ConfigManager('software_config.yaml')