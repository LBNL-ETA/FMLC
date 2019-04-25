#! /usr/bin/env python

import time

class triggering(object):
    def __init__(self, ts):
        self.ts = ts
        self.initialize_all_trigger() 

    def initialize_all_trigger(self):
        now = time.time()
        self.trigger = {}
        for k in self.ts.keys():
            self.trigger[k] = self.get_trigger(now, self.ts[k], mode='prev', integer=self.ts[k]>1)

    def refresh_trigger(self, k, now):
        self.trigger[k] = self.get_trigger(now, self.ts[k], mode='next', integer=self.ts[k]>1)

    def get_trigger(self, t, ts, mode='next', integer=True):
        trigger = round(t/ts)*ts
        if integer: trigger = int(trigger)
        if mode == 'next': trigger = trigger + ts
        elif mode == 'prev': trigger = trigger + ts
        return trigger