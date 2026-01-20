import win32gui
import win32con

def hide_window_from_taskbar(window_title):
    """
    通过窗口标题隐藏指定窗口在任务栏的显示。
    window_title: 窗口标题栏的完整或部分文字
    """
    # 查找窗口句柄
    hwnd = win32gui.FindWindow(None, window_title)
    if hwnd:
        # 修改窗口的扩展样式，添加工具窗口属性
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        new_style = ex_style | win32con.WS_EX_TOOLWINDOW
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
        # 刷新显示
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        # print(f"已成功隐藏窗口 '{window_title}' 在任务栏的图标。")
    else:
        print(f"未找到标题为 '{window_title}' 的窗口。")