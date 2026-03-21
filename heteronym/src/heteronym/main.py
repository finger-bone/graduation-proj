from heteronym.server import main_handler
import uvicorn
import multiprocessing

if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    uvicorn.run(main_handler, host="0.0.0.0", port=8000)
