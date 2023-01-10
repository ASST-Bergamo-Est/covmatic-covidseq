# CovidSeq protocol for Opentrons OT2

## Introduction

Here you can find protocols to execute the CovidSeq library preparation on the pipetting robot OT2.
The system is divided in these part:
1. OT1 "Reagent" used for reagent store and mix preparation; equipped with single channel P300 and P1000 pipettes.
2. OT2 "Library preparation": used to work on samples to prepare the library; equipped with multichannel P20 and P300 pipettes.
3. OT3 "Dilute and denature": used to work on the library pool, the last part of CovidSeq preparation; equipped with single channel pipette.

Between OT1 and OT2 there is a robotic arm: an Automata Eva robot. This robot has to bring plates back and forth between OT1 and OT2.
