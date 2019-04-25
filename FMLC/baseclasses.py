#! /usr/bin/env python

import abc
import warnings

class eFMU(object):
    __metaclass__  = abc.ABCMeta
    
    def __init__(self):
        self.input = {}     
        self.output = {}      
    def do_step(self, inputs={}):
        self.set_inputs(inputs)
        return self.compute()
    def get_model_variables(self):
        return self.input.keys()
    def set_real(self, name, value):
        self.input[name] = value
    def set_inputs(self, inputs):
        all_keys = list(self.input.keys())
        for k, v in inputs.items():
            if k in all_keys:
                self.set_real(k, v)
                all_keys.remove(k)
            else:
                raise KeyError('{} not in input list.'.format(k))
        if len(all_keys) > 0:
            warnings.warn('Not all input specified, but continue step. Missing keys:{}'.format(all_keys), Warning)
    @abc.abstractmethod
    def compute(self):
        ''' Mathod to compute the output '''
    def get_output(self, keys=[]):
        if keys == []:
            return self.output
        else:
            out = {}
            for k in keys:
                if k in self.output.keys():
                    out[k] = self.output[k]
                else:
                    raise KeyError('{} not in output list.'.format(k))
            return out
    def get_input(self, keys=[]):
        if keys == []:
            return self.input
        else:
            out = {}
            for k in keys:
                if k in self.input.keys():
                    out[k] = self.input[k]
                else:
                    raise KeyError('{} not in input list.'.format(k))
            return out
    def update_storage(self, data, init=False):
        if init:
            self.storage = data
        else:
            for k in data.keys():
                if type(data[k]) == type({}):
                    self.storage[k].update(data[k])
                elif type(data[k]) in [type(0), type(0.0), type('')]:
                    self.storage[k] = data[k]
    def get_var(self, name):
        exec('x = self.'+name)
        return x