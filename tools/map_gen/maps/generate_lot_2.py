import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from parking_lot_generator import *

lot = make_lot(12, 12)

lot[6][11] = spot_descriptor(square_type.Entrance, special_spots.Regular)

fill(lot, 0, 0, 1, 10, square_type.Spot_Right, special_spots.Regular)

fill(lot, 11, 11, 1, 5, square_type.Spot_Left, special_spots.Handicap)
fill(lot, 11, 11, 6, 10, square_type.Spot_Left, special_spots.Regular)

fill(lot, 2, 9, 0, 0, square_type.Spot_Down, special_spots.Regular)

fill(lot, 3, 3, 2, 4, square_type.Spot_Right, special_spots.Regular)
fill(lot, 2, 2, 2, 4, square_type.Spot_Left, special_spots.Regular)
fill(lot, 5, 5, 2, 4, square_type.Spot_Left, special_spots.Regular)
fill(lot, 6, 6, 2, 4, square_type.Spot_Right, special_spots.Regular)
fill(lot, 8, 8, 2, 4, square_type.Spot_Left, special_spots.Regular)
fill(lot, 9, 9, 2, 4, square_type.Spot_Right, special_spots.Regular)

fill(lot, 3, 3, 6, 8, square_type.Spot_Left, special_spots.Regular)
fill(lot, 4, 4, 6, 8, square_type.Spot_Right, special_spots.Regular)
fill(lot, 7, 7, 6, 8, square_type.Spot_Left, special_spots.Regular)
fill(lot, 8, 8, 6, 8, square_type.Spot_Right, special_spots.Regular)

fill(lot, 2, 9, 10, 10, square_type.Spot_Up, special_spots.Regular)

print_lot_format(lot)

response = compute_lot_img(lot)
write_to_file(response, "lot2")
