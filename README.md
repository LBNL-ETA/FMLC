# FMLC
[![UnitTests](https://github.com/LBNL-ETA/FMLC/actions/workflows/unit-test.yml/badge.svg)](https://github.com/LBNL-ETA/FMLC/actions/workflows/unit-test.yml)
[![Syntax](https://github.com/LBNL-ETA/FMLC/actions/workflows/syntax-test.yml/badge.svg)](https://github.com/LBNL-ETA/FMLC/actions/workflows/syntax-test.yml)

#### Framework for Multi Layer Control (FMLC)
-------------------------------------------------------------------------

The Framework for Multi Layer Control (FMLC) is designed to support the development of complex control applications, including microgrid control, building automation, energy management, and electric vehicle fleet aggregation. Such control applications typically require the interaction of multiple modules such as gathering data, processing data, making control decisions, and pushing control setpoints. The FMLC is designed to handle the required parallelization, timing and triggering, data logging, and errors of multiple controller modules.

## General
This package is developed as a framework/backend for multi-layer and multi-time domain control. One example application is advanced control based on [Model Predictive Control](https://en.wikipedia.org/wiki/Model_predictive_control) (MPC) where different sub-modules (e.g., weather forecast, energy management, real-time control), with different time constants, have to be coordinated. This framework allows parallelization using the `multiprocessing` module in Python.

*Please note that the FMLC package and especially the examples are still under development. Please open an issue for specific questions*

## Getting Started
The following link permits users to clone the source directory containing the [FMLC](https://github.com/LBNL-ETA/FMLC) package which can be installed with `pip install .`.

The documentation for the [BaseClass](https://github.com/LBNL-ETA/FMLC/blob/master/documentation/baseclass.md) contains a details on how to use `baseclasses.py` to create controller objects. The [StackedClass](https://github.com/LBNL-ETA/FMLC/blob/master/documentation/stackedclasses.md) is the higher-level abstraction found in `stackedclasses.py` which handles parallelization, timing and triggering, data logging, and error handling of multiple baseclass modules.

## Example
To illustrate and test the FMLC functionality, each module executes some tests  when called as `main`. The `python triggering.py` command provides an example of the interal triggering of modules, while the `python baseclasses.py` command provides a simple example of a single controller. A complete example can be found [here](https://github.com/LBNL-ETA/FMLC/blob/master/examples/Test.ipynb).

Another practical example Jupyter notebook that illustrated the operation as a microgrid controller can be found [here](https://github.com/LBNL-ETA/FMLC/tree/master/examples/MicroGridController.ipynb). It is based on the [Distributed Optimal and Predictive Energy Resources](https://github.com/LBNL-ETA/DOPER) (DOPER) and includes a full controller stack and demonstrates the handling of three different time domains:
* Day-ahead control: invoked once per day as complex model
* Supervisory energy management: invoked every 5 minutes with a 24 hour horizon
* Fast-acting control: invoked every second with an hourly horizon

Please note that in order to work properly on Windows, the notebook must be exported to Python code.

## License
Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019, The Regents of the University of California, through Lawrence Berkeley National Laboratory (subject to receipt of any required approvals from the U.S. Dept. of Energy).  All rights reserved.

If you have questions about your rights to use or distribute this software, please contact Berkeley Lab's Intellectual Property Office at IPO@lbl.gov.

NOTICE.  This Software was developed under funding from the U.S. Department of Energy and the U.S. Government consequently retains certain rights.  As such, the U.S. Government has been granted for itself and others acting on its behalf a paid-up, nonexclusive, irrevocable, worldwide license in the Software to reproduce, distribute copies to the public, prepare derivative works, and perform publicly and display publicly, and to permit other to do so.

## Cite
To cite the FMLC package, please use:

*Gehbauer, Christoph, Müller, J., Swenson, T. and Vrettos, E. 2019. Photovoltaic and Behind-the-Meter Battery Storage: Advanced Smart Inverter Controls and Field Demonstration. California Energy Commission.*
