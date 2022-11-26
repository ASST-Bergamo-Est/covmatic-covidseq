# Custom labware generator for vertical 96-well plates

## Introduction

The python script included in this folder is used to generate the labware json files for the vertical plates used in this workflow;
we've basically two types of plate:
1. top aligned, so with the top left corner aligned with the OT slot;
2. bottom aligned, with the bottom left corner aligned with the OT slot.

In this way we can have two plates in 3 vertical slot spaces.

## How to use

Just execute the script with the python interpreter; if you want you can update the offsets.
After the files are generated you've to edit manually some labware names (eg. see where "top" and "bottom" has been added)