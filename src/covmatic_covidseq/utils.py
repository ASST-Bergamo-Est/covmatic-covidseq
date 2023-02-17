import os
import json


def get_labware_json_from_filename(filename: str = ""):
    with open(os.path.join(os.path.dirname(__file__), 'labware', filename)) as f:
        return json.load(f)
