
import json
import copy

NUMBERS = list(range(1, 13))
LETTERS = list(reversed(["A", "B", "C", "D", "E", "F", "G", "H"]))

WELLS = ["{}{}".format(a, b) for a in LETTERS for b in NUMBERS]
WELLS_ORDERING = [["{}{}".format(a, b) for b in NUMBERS] for a in LETTERS]

print("Got numbers: {}".format(NUMBERS))
print("Got letters: {}".format(LETTERS))
print("Got wells: {}".format(WELLS))
print("Got wells ordering: {}".format(WELLS_ORDERING))

filename = "customvertical_96_wellplate_100ul.json"

x_offset = 11.24
y_offset = 14.38

def get_letter_index_from_well(well_name: str):
    letter = well_name[:1]
    index = LETTERS.index(letter)
    print("Got column: {}. Index: {}".format(letter, index))
    return index

def get_number_index_from_well(well_name: str):
    number = int(well_name[1:])
    index = NUMBERS.index(number)
    print("Got row: {}. Index: {}".format(number, index))
    return index

def getpos_x_y(row: int, column: int):
    global x_offset
    global y_offset

    x_spacing = 9
    y_spacing = 9
    y_max = 85.47
    
    y_end = y_max - y_offset

    x_pos = x_offset + column * x_spacing
    y_pos = y_end - row * y_spacing
    print("Calculated positions for row {} column {}: x {} y {}".format(row, column, x_pos, y_pos))
    return x_pos, y_pos


def getpos_x_y_from_name(well_name: str):
    return getpos_x_y(get_number_index_from_well(well_name), get_letter_index_from_well(well_name))


def getpos_x_from_name(well_name: str):
    x, y = getpos_x_y_from_name(well_name)
    return x


def getpos_y_from_name(well_name: str):
    x, y = getpos_x_y_from_name(well_name)
    return y

def getwells():
    getpos_x_y_from_name("H11")
    getpos_x_y_from_name("H12")
    return []

def get_updated_labware(labware, x_offs, y_offs, data_to_update: dict = None):
    global x_offset
    global y_offset

    x_offset = x_offs
    y_offset = y_offs

    newdict = {}
    for field in labware:
        if field == "wells":
            newdict["wells"] = {name: {
                "depth": 14.78,
                "totalLiquidVolume": 100,
                "shape": "circular",
                "diameter": 5.34,
                "x": getpos_x_from_name(name),
                "y": getpos_y_from_name(name),
                "z": 6.22} for name in WELLS}
            print(newdict["wells"])
        elif field == "groups":
            newdict["groups"] = labware["groups"]
            newdict["groups"][0]["wells"] = WELLS
        elif field == "ordering":
            newdict["ordering"] = WELLS_ORDERING
        else:
            newdict[field] = labware[field]
        
        # Updating data
        if data_to_update and field in data_to_update:
            for d in data_to_update[field]:
                print("Copying {} {} value {}".format(field, d, data_to_update[field][d]))
                newdict[field][d] = data_to_update[field][d]
    return newdict


with open(filename, "r") as f:
    labware = json.load(f)

    x_offset = 11.24
    y_offset = 14.38

    data = {"brand": { "brand": "Custom", "brandId": "Vertical_PCR_Plate_100ul"},
            "metadata": {"displayName": "Vertical 96 Well Plate 100ul aligned {} {}"},
            "parameters": {"loadName":"customvertical_96_wellplate_100ul_{}{}"}
            }

    def getUpdatedData(top_bottom: str, left_right: str):
        newdata = copy.deepcopy(data)
        for d in newdata:
            for f in newdata[d]:
                newdata[d][f] = newdata[d][f].format(top_bottom, left_right)
        return newdata


    with open("customvertical_96_top_left_aligned.json", "w") as fp:
        json.dump(get_updated_labware(labware, 11.24, 12, getUpdatedData("top", "left") ), fp)

    with open("customvertical_96_bottom_left_aligned.json", "w") as fp:
        json.dump(get_updated_labware(labware, 11.24, -15, getUpdatedData("bottom", "left")), fp)

    with open("customvertical_96_top_right_aligned.json", "w") as fp:
        json.dump(get_updated_labware(labware, 54, 12, getUpdatedData("top", "right")), fp)

    with open("customvertical_96_bottom_right_aligned.json", "w") as fp:
        json.dump(get_updated_labware(labware, 54, -15, getUpdatedData("bottom", "right")), fp)


