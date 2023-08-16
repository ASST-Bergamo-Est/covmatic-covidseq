# CovidSeq protocol for Opentrons OT2

> [!WARNING]
> This package is meant to be directly used only by an informed developer audience.

> [!WARNING]
> This package is under active development and is not meant to be used for any other purpose.

> [!IMPORTANT]
> This package is part of an integrated system. You can find the full documentation
> of the system here: https://asst-bergamo-est.github.io/covmatic-covidseq-guide/


## Table of Contents
* [Introduction](#introduction)
* [Installation](#installation)
* [Setup](#setup)
* [Calibration](#calibration)
* [Execution](#execution)
* [Development](#development)
* [Testing](#testing)
* [Publish](#publish)

## Introduction

This 
Here you can find protocols to execute the Illumina CovidSeq library preparation on the pipetting robot Opentrons OT2.
The system is divided in these part:
1. OT1 "Reagent" used for reagent store and mix preparation; equipped with single channel P300 and P1000 pipettes.
2. OT2 "Library preparation": used to work on samples to prepare the library; equipped with multichannel P20 and P300 pipettes.

Between OT1 and OT2 there is a robotic arm: an Automata Eva robot. This robot has to bring plates back and forth between OT1 and OT2.

Source code is on [ASST Bergamo Est repository](https://github.com/ASST-Bergamo-Est/covmatic-covidseq)


## Installation

You can [install the Covmatic-Covidseq via `pip`](https://pypi.org/project/covmatic-covidseq) on two Opentrons OT2 robot:
1. log in the robot via *ssh*
2. install the package with
   ```
   py -m pip install covmatic-covidseq
   ```

## Setup
To set up the Covmatic-covidseq system you need first to create a configuration directory on each of the OT2:
1. log in the robot via *ssh* or with a Jupyter terminal
2. create the config directory:
   ```
   mkdir /var/lib/jupyter/notebooks/config
   ``` 
3. create the config file:
   ```
   vi /var/lib/jupyter/notebooks/config/config.json
   ```
   In this file you need at least two parameters regarding the *Covmatic Robotmanager* instance which the OT2 should talk to; 
   change the host IP addres to the address of the Robotmanager instance:
   ```
   {
    "robot_manager_host": "192.168.1.1",
    "robot_manager_port": 5000
   }
   ``` 

## Calibration

From Opentrons robot version 6.0.0 labware calibrations are saved run-per-run, and thus we need to calibrate the labware and then extract the calibrations.
To do so run on each of the OT2s on a PC connected to the robot:
1. **Calibration**
   Open the [OT App](https://opentrons.com/ot-app/)
2. Load the calibration protocol for each robot:
   - [Reagent OT Calibration protocol](protocols/station_reagent_calibration.py)
   - [Library OT Calibration protocol](protocols/station_library_calibration.py)
3. Calibrate all requested labware using the **Labware Position Check* in the OT App.
4. Run the protocol on the OT and stop it when the robot starts moving to labware.
5. Download the runlog from the OT App
6. Load the runlog to the robot using *Jupyter Notebook*:
   1. Open the Jupyter url in a browser: *http://[robot-ip]:48888*
   2. enter the *config* directory (see [Setup](#setup))
   3. drag the runlog file in the jupyter page and then select *Upload* command
7. Log in the robot with ssh or open a Jupyter terminal
8. Execute this command:
   ``` 
   /var/user-packages/usr/bin/covmatic-covidseq-genoffset
   ``` 
9. When requested, insert the complete runlog filename; e.g. (change it with your specific runlog filename):
   ``` 
   OT1_station_reagent_calibration.py_2023-04-01T14_29_12.850Z.json*
   ``` 
10. Then insert the output file name **labware_offsets.json**
11. If the execution is completed without errors than labware calibrations has been saved successfully.


## Execution

The protocol is meant to be run using the [Covmatic Localwebserver system](https://pypi.org/project/covmatic-localwebserver).

Another way in which the protocol can be executed is running it with *opentrons_execute*:
1. log in the robot with *ssh* or with a Jupyter Terminal;
2. upload one protocol for each robot to */var/lib/jupyter/notebooks*
   1. [Reagent OT protocol](protocols/station_reagent.py)
   2. [Library OT protocol](protocols/station_library.py)
3. Execute the loaded protocol with:
   ```
   opentrons_execute /var/lib/jupyter/notebooks/station_{library or reagent}.py
   ```
4. When protocol pauses asking user interaction, resume calling the HTTP endpoint:
   ```
   {robot-ip-address}:8080/resume
   ```

## Development

If you want to develop the package follow these step:
1. check out the source code:
   ```
   git checkout https://github.com/ASST-Bergamo-Est/covmatic-covidseq.git
   ```
2. modify the code and update the version in *src/covmatic_covidseq/__init__.py*
3. build the code:
   ```
   hatch build
   ```
4. install locally with:
   ```
   pip install .
   ```
   or use the wheel created in the *dist* folder.

## Testing

The Covmatic-covidseq source code comes with a handful of tests to check that the code is doing as expected. 
It has been developed using a Test Driven Development approach.
To execute tests and coverage report just launch:
```
hatch run cov
```

## Publish

To publish a new version of the package be sure the package is satisfying the testing step;
then use *git* to add and commit everything.
The last step is to create a tag for version *x.y.x* with:
   ```
   git tag vx.y.x
   ```
and to commit the tag with: 
   ```
   git push origin tag vx.y.x
   ```
The *GitHub workflow* will then build the package, check for installation and unit testing and then upload the wheel on *PyPI*.