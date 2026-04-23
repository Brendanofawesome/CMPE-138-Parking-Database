from enum import Enum
from PIL import Image, ImageDraw
from typing import NamedTuple
import csv
import os

class parking_spot(NamedTuple):
    spot_id: str
    spot_type: str
    
    start_x: int
    end_x: int
    
    start_y: int
    end_y: int

square_type = Enum("square_type", 
                   "Spot_Left Spot_Right Spot_Down Spot_Up \
                    Path Entrance Transparent")

special_spots = Enum("special_spot_types",
                     "Handicap EV Regular")

class spot_descriptor(NamedTuple):
    type: square_type
    special: special_spots

def fill(arr: list[list[spot_descriptor]], x_start: int, x_end: int, y_start: int, y_end: int, type: square_type, special: special_spots) -> None:
    for i in range(x_start, x_end + 1):
        for j in range(y_start, y_end + 1):
            arr[i][j] = spot_descriptor(type, special)
            
def make_lot(x_size: int, y_size: int) -> list[list[spot_descriptor]]:
    return [[spot_descriptor(square_type.Path, special_spots.Regular) for _ in range(y_size)] for _ in range(x_size)]
            
def print_lot_format(arr: list[list[spot_descriptor]]) -> None:
    #get the longest enum name
    longest_length: int = 0
    for square in square_type:
        longest_length = max(longest_length, len(square.name))
        
    longest_row_index: int = len(str(len(arr[0]) - 1))
        
    #print the column numbers
    print(" " * (longest_row_index + 2), end="")
    print(" ".join(f"{i:<{longest_length}}" for i in range(len(arr))))
    
    #print each row
    for y in range(len(arr[0])):
        print(f"{y:<{longest_row_index}}", end=": ")
        for x in range(len(arr)):
            print(f"{arr[x][y].type.name:<{longest_length}} ", end="")
        print()

def compute_lot_img(arr: list[list[spot_descriptor]]) -> tuple[Image.Image, list[parking_spot]]:
    PIXELS_PER_SQUARE: int = 30
    PIXELS_PER_BORDER: int = 4
    
    #initialize the image
    img = Image.new("RGBA", (len(arr)*PIXELS_PER_SQUARE + PIXELS_PER_BORDER * 2, len(arr[0])*PIXELS_PER_SQUARE + PIXELS_PER_BORDER * 2), color=(0, 0, 0, 0,))
    draw_handle = ImageDraw.Draw(img)
    
    bounding_boxes: list[parking_spot] = []
    
    current_spot_id: int = 0
    
    #generate from top to bottom, left-to-right
    for j in range(len(arr[0])):
        for i in range(len(arr)):
            current_square_type: square_type = arr[i][j].type
            current_special_type: special_spots = arr[i][j].special
            #print(f"placing a {current_square_type.name} at position x:{i}, y:{j}")
            
            start_x = i * PIXELS_PER_SQUARE + PIXELS_PER_BORDER
            end_x = (i+1) * PIXELS_PER_SQUARE+PIXELS_PER_BORDER - 1
            
            start_y = j * PIXELS_PER_SQUARE + PIXELS_PER_BORDER
            end_y = (j+1) * PIXELS_PER_SQUARE+PIXELS_PER_BORDER - 1
            
            #perform spot placing logic
            if(current_square_type not in (square_type.Path, square_type.Entrance, square_type.Transparent)):
                bounding_boxes.append(parking_spot(str(current_spot_id), current_special_type.name, start_x, end_x, start_y, end_y))
                current_spot_id = current_spot_id + 1
                
                spot_color = "black"
                if(current_special_type == special_spots.Handicap): spot_color = "blue"
                elif(current_special_type == special_spots.EV): spot_color = "orange"
                draw_handle.rectangle([start_x, start_y, end_x, end_y], fill="white", outline=spot_color, width=PIXELS_PER_BORDER)
                    
                #remove open side
                match current_square_type:
                    case(square_type.Spot_Up):
                        draw_handle.rectangle([start_x+PIXELS_PER_BORDER, start_y, end_x-PIXELS_PER_BORDER, start_y+PIXELS_PER_BORDER], fill="white", outline=None)
                    case(square_type.Spot_Down):
                        draw_handle.rectangle([start_x+PIXELS_PER_BORDER, end_y-PIXELS_PER_BORDER, end_x-PIXELS_PER_BORDER, end_y], fill="white", outline=None)
                    case(square_type.Spot_Left):
                        draw_handle.rectangle([start_x, start_y+PIXELS_PER_BORDER, start_x+PIXELS_PER_BORDER, end_y-PIXELS_PER_BORDER], fill="white", outline=None)
                    case(square_type.Spot_Right):
                        draw_handle.rectangle([end_x-PIXELS_PER_BORDER, start_y+PIXELS_PER_BORDER, end_x, end_y-PIXELS_PER_BORDER], fill="white", outline=None)
            
            #place exterior border if necessary
            if(current_square_type != square_type.Transparent):
                border_color = "red"
                if(current_square_type == square_type.Entrance):
                    border_color = "yellow"
                    
                left_is_edge_or_transparent = i == 0 or arr[i - 1][j].type == square_type.Transparent
                right_is_edge_or_transparent = i == len(arr) - 1 or arr[i + 1][j].type == square_type.Transparent
                top_is_edge_or_transparent = j == 0 or arr[i][j - 1].type == square_type.Transparent
                bottom_is_edge_or_transparent = j == len(arr[0]) - 1 or arr[i][j + 1].type == square_type.Transparent

                if(left_is_edge_or_transparent):
                    draw_handle.rectangle([start_x-PIXELS_PER_BORDER, start_y, start_x - 1, end_y], fill=border_color, outline=None)
                if(right_is_edge_or_transparent):
                    draw_handle.rectangle([end_x + 1, start_y, end_x + PIXELS_PER_BORDER, end_y], fill=border_color, outline=None)
                
                if(top_is_edge_or_transparent):
                    draw_handle.rectangle([start_x, start_y-PIXELS_PER_BORDER, end_x, start_y - 1], fill=border_color, outline=None)
                if(bottom_is_edge_or_transparent):
                    draw_handle.rectangle([start_x, end_y + 1, end_x, end_y + PIXELS_PER_BORDER], fill=border_color, outline=None)
            
            #fill paths in grey
            if(current_square_type in (square_type.Path, square_type.Entrance)):
                draw_handle.rectangle([start_x, start_y, end_x, end_y], fill="grey", outline=None)

    return (img, bounding_boxes)

def write_to_file(lot: tuple[Image.Image, list[parking_spot]], filename: str):
    output_dir = os.path.join(os.path.dirname(__file__), "gen")
    os.makedirs(output_dir, exist_ok=True)
    
    lot[0].save(os.path.join(output_dir, f"{filename}.png"))

    with open(os.path.join(output_dir, f"{filename}.csv"), 'w', newline='') as file:
        writer = csv.writer(file)
        
        row_names = (row for row in lot[1][0]._fields)
        writer.writerow(row_names)
        
        writer.writerows(lot[1])


if __name__ == "__main__":
    test_lot = make_lot(10, 10)
    test_lot[9][4] = spot_descriptor(square_type.Entrance, special_spots.Regular)
    fill(test_lot, 0, 0, 0, 9, square_type.Spot_Right, special_spots.Regular)
    fill(test_lot, 2, 2, 0, 6, square_type.Spot_Left, special_spots.Regular)
    fill(test_lot, 2, 2, 8, 9, square_type.Spot_Left, special_spots.Regular)
    fill(test_lot, 3, 9, 0, 0, square_type.Spot_Down, special_spots.Regular)
    fill(test_lot, 4, 8, 2, 2, square_type.Spot_Up, special_spots.Regular)
    fill(test_lot, 4, 8, 3, 3, square_type.Spot_Down, special_spots.Regular)
    fill(test_lot, 4, 8, 6, 6, square_type.Spot_Down, special_spots.Regular)
    fill(test_lot, 4, 8, 5, 5, square_type.Spot_Up, special_spots.Regular)
    fill(test_lot, 3, 3, 8, 9, square_type.Spot_Right, special_spots.Regular)
    fill(test_lot, 5, 5, 8, 9, square_type.Spot_Left, special_spots.Regular)
    fill(test_lot, 6, 6, 8, 9, square_type.Spot_Right, special_spots.Regular)
    fill(test_lot, 9, 9, 8, 9, square_type.Spot_Left, special_spots.Regular)

    print_lot_format(test_lot)

    img, spots = compute_lot_img(test_lot)
    img.show()