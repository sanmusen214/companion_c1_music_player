from enum import Enum
import locale
from .config import my_config


class LangType(Enum):
    CN = "cn"
    EN = "en"

# 简单硬编码
lang_dict = {
    "C1_music_screen": {
        LangType.CN: "C1 音乐副屏",
        LangType.EN: "C1 Music Screen"
    },
    "music_platform": {
        LangType.CN: "音乐平台",
        LangType.EN: "Music Platform"
    },
    "quit_button": {
        LangType.CN: "退出",
        LangType.EN: "Quit"
    }
}


class I18nManager:
    """国际化管理器类"""
    def __init__(self, config_manager):
        self.config_manager = config_manager
        # 检测系统语言
        config_lang = self.config_manager.get('lang_type')
        if config_lang is not None and config_lang != "auto":
            # 从配置文件
            self.lang = LangType(config_lang)
        else:
            # 检测
            default_locale = locale.getdefaultlocale()
            # default_locale 格式示例：('zh_CN', 'cp936') 或 ('en_US', 'cp1252')
            lang_code = default_locale[0].split('_')[0] if default_locale else None
            if lang_code is not None and lang_code.lower() == 'zh':
                # 系统语言是中文，设置为中文
                self.lang = LangType.CN
            else:
                # 不是中文 或 无法检测到系统语言，设置为 英文
                self.lang = LangType.EN
        # 输出当前使用的语言，便于调试
        print(f"now lang is {LangType(self.lang).name}")
    
    def get(self, key):
        """
        获取国际化文本
        """
        return lang_dict.get(key, {}).get(self.lang, key)
        

my_i18n = I18nManager(my_config)