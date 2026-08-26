import time
from concurrent.futures import ThreadPoolExecutor

class controller_stack:
    def __init__(self, workers=15):
        self.executor = ThreadPoolExecutor(max_workers=workers)

    def query_control(self):
        # log 1
        st = time.time()
        self.executor.submit(self.log_to_csv)
        print('log1', round(time.time()-st, 1))
        # log 2
        st = time.time()
        self.executor.submit(self.save_and_clear)
        print('log2', round(time.time()-st, 1))
        # control
        for task in [1, 2]:
             self.executor.submit(controller_stack.run_controller_queue, self, task)

    def log_to_csv(self):
        time.sleep(5)
        print('Log done.')

    def save_and_clear(self):
        time.sleep(10)
        print('Save and clear done.')

    def run_controller_queue(self, task):
        tasks = {1: [5, 10],
                 2: [20]}
        timeout = 30

        print(tasks[task])
        for tt in tasks[task]:
            print(tt)
            p = self.executor.submit(self.do_control, tt)
            p.result(timeout)

    def do_control(self, tt):
        print(f'Start {tt}')
        st = time.time()
        time.sleep(tt)
        print(f'Finish {tt} after {round(time.time()-st, 1)}.')

if __name__ == '__main__':
    ctrl = controller_stack()
    ctrl.query_control()
    time.sleep(30)
    ctrl.executor.shutdown()
