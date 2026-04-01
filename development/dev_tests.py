import os
import sys

root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(root, '..', 'test'))

from test_query_control import test_sampletime, test_normal
from test_query_control import test_stuckControllerSingle, test_stuckControllerMultiple

# test_sampletime()

# test_normal()

# test_stuckControllerSingle()

test_stuckControllerMultiple()