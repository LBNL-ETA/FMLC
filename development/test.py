import os
import time
import multiprocessing as mp
from multiprocessing.managers import BaseManager

class ctrl(object):
    def __init__(self):
        print('init')
    def test(self):
        print('test')
    def do_step(self, x, t):
        time.sleep(t)
        print(os.getpid(), x)

def ctrl_worker(ctrl, x, t):
    print(ctrl, x, t)
    ctrl.test()
    #ctrl.do_step(x, t)
    
if __name__ == '__main__':
    BaseManager.register('controller1', ctrl)
    #BaseManager.register('controller2', ctrl)

    manager = BaseManager()
    manager.start()
    
    ctrl_1 = manager.controller1()
    #ctrl_2 = manager.controller2()
    
    mp.Process(target=ctrl_worker, args=[ctrl_1, 'This is controller 1.', 10]).start()
    #mp.Process(target=ctrl_worker, args=[ctrl_2, 'This is controller 2.', 0]).start()
    