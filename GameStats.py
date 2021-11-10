import math
from lux.game import Game
from lux.game_objects import Player, Unit, UNIT_TYPES, City, CityTile
from lux.game_map import Cell, RESOURCE_TYPES, Position
from lux.constants import Constants
from lux.game_constants import GAME_CONSTANTS
from lux import annotate
from ACTION_TYPES import ACTION_TYPES
import numpy as np

number_of_units = 0
number_of_city_tiles = 0
number_of_resources = 0
clusters_list = []


def updateStats(player: Player, resource_list: list):
    global number_of_units
    global number_of_city_tiles
    global number_of_resources

    number_of_units = len(player.units)
    number_of_city_tiles = player.city_tile_count
    number_of_resources = len(resource_list)