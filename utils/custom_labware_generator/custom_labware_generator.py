
import json

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

    y_end = (y_offset + 7 * y_spacing)

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

def get_updated_labware(labware, x_offs, y_offs):
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
    return newdict


with open(filename, "r") as f:
    labware = json.load(f)

    x_offset = 11.24
    y_offset = 14.38



    with open("customvertical_96_top_aligned.json", "w") as fp:
        json.dump(get_updated_labware(labware, 11.24, 14.38), fp)

    with open("customvertical_96_bottom_aligned.json", "w") as fp:
        json.dump(get_updated_labware(labware, 11.24, 50), fp)


