# FMLC
#### Framework for Multi Layer Control in Python
-------------------------------------------------------------------------

This package is developed to serve as a framework for control applications (building automation, energy management, electric vehicle fleet aggregation, etc.). In particular, this framework is built to handle the parallelization, timing/triggering, data logging, and error handling of multiple controller modules.

## General
This package is developed as a framework/backend for multi-layer and multi-time domain controller. One example application are advanced controller based on [Model Predictive Control](https://en.wikipedia.org/wiki/Model_predictive_control) (MPC) where different sub-modules (i.e. weather forecast, energy management, real-time control), with different time constants, have to be coordinated. This framework allows parallelization using the `multiprocessing` module in Python. The FMLC package was tested under Python 2.7 (single and parallel structure) and Python 3.7 (only single structure).

*Please note that the FMLC package and especially the examples are still under development. Please open an issue for specific questions*

## Getting Started
The following link permits users to clone the source directory containing the [FMLC](https://github.com/LBNL-ETA/FMLC) package.

The package only depends on modules from the Python Standard Library.

## Example
To illustrate its functionality, the FMLC package ships with an example Jupyter notebook, which can be found [here](Examples).

[Test 1](Examples/Test1.ipynb) is a simple component test which also demonstrates the functionality of FMLC. Please note that in order to work properly on Windows, the notebook must be exported to Python code.

Another application example can be found [here](https://github.com/LBNL-ETA/DOPER) where FMLC is used to coordiante MPC controls on three differernt time domains:
* Day-ahead control: invoked once per day; complex model
* Supervisory energy management: invoked every 5 minutes with a 24 hour horizon
* Fast-acting control: invoked every second with an hourly horizon 

## License
Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019, The
Regents of the University of California, through Lawrence Berkeley National
Laboratory (subject to receipt of any required approvals from the U.S.
Dept. of Energy).  All rights reserved.

If you have questions about your rights to use or distribute this software,
please contact Berkeley Lab's Intellectual Property Office at
IPO@lbl.gov.

NOTICE.  This Software was developed under funding from the U.S. Department
of Energy and the U.S. Government consequently retains certain rights.  As
such, the U.S. Government has been granted for itself and others acting on
its behalf a paid-up, nonexclusive, irrevocable, worldwide license in the
Software to reproduce, distribute copies to the public, prepare derivative
works, and perform publicly and display publicly, and to permit other to do
so.

## Cite
To cite the FMLC package, please use:

*Gehbauer, Christoph, Müller, J., Swenson, T. and Vrettos, E. 2019. Photovoltaic and Behind-the-Meter Battery Storage: Advanced Smart Inverter Controls and Field Demonstration. California Energy Commission.*