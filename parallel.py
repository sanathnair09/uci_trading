import multiprocessing
import time


def print_current_time():
    current_time = time.ctime()
    print(f"Current time: {current_time}")


def run_multiple_instances(func, num_instances):
    processes = []

    # Create multiple processes and start them
    for _ in range(num_instances):
        process = multiprocessing.Process(target = func)
        process.start()
        processes.append(process)

    # Wait for all processes to complete
    for process in processes:
        process.join()


# Example function to be executed in parallel
def print_hello():
    print("Hello from parallel process!")


# Call the run_multiple_instances function
if __name__ == "__main__":
    run_multiple_instances(print_current_time, 5)
