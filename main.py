from musicscreen import ScreenShowApp

if __name__ == "__main__":
    app = ScreenShowApp()
    try:
        # 运行应用
        app.run()
    except KeyboardInterrupt:
        app.quit_action()
    except Exception as e:
        print(f"发生错误: {e}")
        app.quit_action()