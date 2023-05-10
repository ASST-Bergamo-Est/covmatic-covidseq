import os
import json

default_index_order = [
    "A1", "B1", "C1", "D1", "E1", "F1", "G1", "H1",
    "A2", "B2", "C2", "D2", "E2", "F2", "G2", "H2",
    "A3", "B3", "C3", "D3", "E3", "F3", "G3", "H3",
    "A4", "B4", "C4", "D4", "E4", "F4", "G4", "H4",
    "A5", "B5", "C5", "D5", "E5", "F5", "G5", "H5",
    "A6", "B6", "C6", "D6", "E6", "F6", "G6", "H6"]

def get_labware_json_from_filename(filename: str = ""):
    with open(os.path.join(os.path.dirname(__file__), 'labware', filename)) as f:
        return json.load(f)


def parse_v6_log_and_create_labware_offsets_json(log_filepath: str=None, output_filepath=None):
    if log_filepath is None:
        log_filepath = input("Insert OT app log path: ")

    if output_filepath is None:
        output_filepath = input("Insert output file path: ")

    with open(log_filepath, "r") as f:
        log_dict = json.load(f)

    output_offsets = []

    our_offsets_id = [l['offsetId'] for l in filter(lambda x: 'offsetId' in x, log_dict['labware'])]

    for l in filter(lambda x: x['id'] in our_offsets_id, log_dict['labwareOffsets']):
        output_offsets.append({
            'labware_name': l['definitionUri'].split('/')[1],
            'slot': l['location']['slotName'],
            'offsets': l['vector']
        })

    with open(output_filepath, "w") as f:
        json.dump(output_offsets, f)