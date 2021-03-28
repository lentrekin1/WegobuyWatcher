from app.main import app
import threading
import watcher

if __name__ == "__main__":
    watch_thread = threading.Thread(target=watcher.watch, args=())
    watch_thread.start()
    app.run(port=80)