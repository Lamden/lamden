#from cilantro_ee.logger import get_logger
#import pstats
#import cProfile
# import sys
#from io import StringIO
from multiprocessing import Process
# import os
from math import sqrt
from random import randint

# @profile_class
class Raghu:
    def __init__(self, task, cycles, run_in_subproc=False):
        assert hasattr(self, task), "Raghu has no task named {}".format(task)

        ##self.log = get_logger("Raghu")
        ##self.log.warning("Starting task {} with cycles {}".format(task, cycles))

        ##self.log.warning("starting {}...".format(task))

        if task == 'task_2':
            self.task_2(cycles)
        else:
            func = getattr(self, task)
            if run_in_subproc:
                p = Process(target=func, args=(cycles,))
                p.start()
                p.join()
            else:
                func(cycles)

        ##self.log.warning("done with {}!".format(task))

    def task_1(self, cycles):
        s = 0
        for i in range(cycles):
            s += i ** i
        #self.log.warning(s)

    def task_2(self, cycles):
        n = 0
        for i in range(cycles):
            n += (pow(-1, i)/(2*i + 1))
        n *= 4
        #self.log.warning(n)

    def task_3(self, cycles):
        s = 0
        for i in range(1, cycles + 1):
            s += 1/i
        #self.log.warning(s)

    @classmethod
    def class_task_1(cls, cycles):
        log = get_logger("Raghu")
        for i in range(cycles, 0, -1):
            if Raghu.is_prime(i):
                log.warning(i)
                return

    @classmethod
    def class_task_2(cls, cycles):
        log = get_logger("Raghu")
        while True:
            i = random.randint(0, cycles+1)
            if Raghu.is_prime(i):
                log.warning(i)
                return

    # @staticmethod
    @classmethod
    def is_prime(cls, num):
        if num < 2:
            return False
        for i in range(2, int(math.sqrt(num)) + 1):
            if num % i == 0:
                return False
        return True

if __name__== "__main__":

    # try:
    #     os.remove(os.getcwd()+'/'+STATS_FILE)
    # except:
    #     pass

    r = Raghu(task='task_1', cycles=42 ** 2, run_in_subproc=True)
    r = Raghu(task='task_2', cycles=10 ** 4, run_in_subproc=True)
    r = Raghu(task='task_3', cycles=10 ** 4, run_in_subproc=True)

#    r.task_2(cycles=9000)
#    r.task_2(cycles=2 ** 20)

#    r.task_3(cycles=1234)
#    r.task_3(cycles=4321)

#    Raghu.class_task_1(11 ** 13)
#    Raghu.class_task_2(2 ** 48)

    # output_stats(use_stdout=True)
