import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from parking_lot_generator import *

lot = make_lot(14, 10)

lot[13][5] = spot_descriptor(square_type.Entrance, special_spots.Regular)
lot[13][4] = spot_descriptor(square_type.Entrance, special_spots.Regular)

fill(lot, 1, 13, 0, 0, square_type.Spot_Down, special_spots.Regular)
fill(lot, 1, 13, 9, 9, square_type.Spot_Up, special_spots.Regular)

fill(lot, 0, 0, 2, 5, square_type.Spot_Right, special_spots.Handicap)
fill(lot, 0, 0, 6, 7, square_type.Spot_Right, special_spots.EV)

fill(lot, 3, 11, 2, 2, square_type.Spot_Up, special_spots.Regular)
fill(lot, 3, 11, 3, 3, square_type.Spot_Down, special_spots.Regular)

fill(lot, 3, 11, 6, 6, square_type.Spot_Up, special_spots.Regular)
fill(lot, 3, 11, 7, 7, square_type.Spot_Down, special_spots.Regular)

print_lot_format(lot)

response = compute_lot_img(lot)
write_to_file(response, "lot3")
