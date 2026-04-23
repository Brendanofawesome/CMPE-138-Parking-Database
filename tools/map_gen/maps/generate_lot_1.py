import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from parking_lot_generator import *

test_lot = make_lot(10, 10)
test_lot[9][4] = spot_descriptor(square_type.Entrance, special_spots.Regular)
fill(test_lot, 0, 0, 0, 9, square_type.Spot_Right, special_spots.Regular)
fill(test_lot, 2, 2, 0, 6, square_type.Spot_Left, special_spots.Regular)
fill(test_lot, 2, 2, 8, 9, square_type.Spot_Left, special_spots.Regular)
fill(test_lot, 3, 9, 0, 0, square_type.Spot_Down, special_spots.EV)
fill(test_lot, 4, 8, 2, 2, square_type.Spot_Up, special_spots.Regular)
fill(test_lot, 4, 8, 3, 3, square_type.Spot_Down, special_spots.Regular)
fill(test_lot, 4, 8, 6, 6, square_type.Spot_Down, special_spots.Regular)
fill(test_lot, 4, 8, 5, 5, square_type.Spot_Up, special_spots.Regular)
fill(test_lot, 3, 3, 8, 9, square_type.Spot_Right, special_spots.Regular)
fill(test_lot, 5, 5, 8, 9, square_type.Spot_Left, special_spots.Regular)
fill(test_lot, 6, 6, 8, 9, square_type.Spot_Right, special_spots.Regular)
fill(test_lot, 9, 9, 8, 9, square_type.Spot_Left, special_spots.Handicap)

fill(test_lot, 0, 2, 0, 0, square_type.Transparent, special_spots.Regular)

print_lot_format(test_lot)

response = compute_lot_img(test_lot)
write_to_file(response, "lot1")