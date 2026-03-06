from musicscreen import ScreenShowApp
import traceback

if __name__ == "__main__":
    app = ScreenShowApp()
    try:
        # 运行应用
        app.run()
    except KeyboardInterrupt:
        app.quit_action()
    except Exception as e:
        print(f"Error {e} occurred: {traceback.format_exc()}")
        app.quit_action()