import math
from lux.game import Game
from lux.game_map import Cell, RESOURCE_TYPES, Position
from lux.constants import Constants
from lux.game_constants import GAME_CONSTANTS
from lux import annotate
from ACTION_TYPES import ACTION_TYPES
import numpy as np
import GameStats
import Logfile
import ClusterManager

#logging.basicConfig(filename="agent.log", level=logging.INFO)
logfile = Logfile.logfile

DIRECTIONS = Constants.DIRECTIONS
game_state = None
night_cycle = 10

build_location = None

unit_to_city_dict = {}
unit_to_action_dict = {}
blocked_resources = {}

unit_movement = {}

unit_to_cluster_id_dict = {}
cluster_id_to_cluster_dict = {}

blocked_distance_param = 1
max_city_walk_distance_factor = 0
max_distance_to_fuel_city = 7 # TODO match to map size?
max_walk_home_distance = 3
max_build_to_adjacent_city_tile_distance = 4


def get_resource_tiles(game_state, width, height):
    resource_tiles: list = []
    for y in range(height):
        for x in range(width):
            cell = game_state.map.get_cell(x, y)
            if cell.has_resource():
                resource_tiles.append(cell)
    return resource_tiles


def get_closest_resources(unit, resource_tiles, player, observation):
    closest_dist = math.inf
    closest_resource_tile = None
    resource_tiles_possible = []
    # if the unit is a worker and we have space in cargo, lets find the nearest resource tile and try to mine it
    for resource_tile in resource_tiles:
        if resource_tile.resource.type == Constants.RESOURCE_TYPES.COAL and not player.researched_coal(): continue
        if resource_tile.resource.type == Constants.RESOURCE_TYPES.URANIUM and not player.researched_uranium(): continue
        # Skip already assigned resource tiles
        #if resource_tile in unit_to_resource_dict.values():
        #    resource_tiles_possible.append(resource_tile)
        #    continue

        dist = resource_tile.pos.distance_to(unit.pos)
        if dist < closest_dist:
            if resource_tile.pos in blocked_resources.values(): #  and dist <= blocked_distance_param:
                if dist < 3:
                    continue
                #if resource_tile.resource.type == Constants.RESOURCE_TYPES.URANIUM:
                    # Continue as farming Uranium takes a long time so units may need to wait a long tim
                #    continue
                #elif resource_tile.resource.type == Constants.RESOURCE_TYPES.COAL:
                #    if dist < 5:
                        # Higher distance a Coal need a bit longer to farm
                #        continue
                #elif dist < 2:
                    # Wood farms fast so distance does not need to bee that small
                #    continue
            closest_dist = dist
            closest_resource_tile = resource_tile

    if closest_resource_tile == None:
        with open(logfile, "a") as f:
            f.write(f"{observation['step']} No more Resources on the map!\n")
        closest_resource_tile, closest_dist = get_highest_resource(unit, resource_tiles, player, observation)
    return closest_resource_tile, closest_dist


# Returns the biggest cluster
def get_biggest_cluster(clusters):
    biggest_cluster = None
    max_tiles = 0
    for cluster in clusters:
        if len(cluster) > max_tiles:
            biggest_cluster = cluster
            max_tiles = len(biggest_cluster)
    return biggest_cluster


# Returns the biggest cluster for the given resource tpye
def get_biggest_cluster_by_type(clusters, resc_type):
    biggest_cluster = None
    max_tiles = 0
    for cluster in clusters:
        if cluster[0].resource.type != resc_type:
            continue
        if len(cluster) > max_tiles:
            biggest_cluster = cluster
            max_tiles = len(biggest_cluster)
    return biggest_cluster


def get_highest_resource(unit, resource_tiles, player, observation):
    closest_dist = math.inf
    closest_resource_tile = None
    resource_tiles_possible = []
    # if the unit is a worker and we have space in cargo, lets find the nearest resource tile and try to mine it
    for resource_tile in resource_tiles:
        if player.researched_coal() and resource_tile.resource.type == Constants.RESOURCE_TYPES.WOOD: continue
        if player.researched_uranium() and (resource_tile.resource.type == Constants.RESOURCE_TYPES.WOOD or resource_tile.resource.type == Constants.RESOURCE_TYPES.COAL): continue
        if resource_tile.resource.type == Constants.RESOURCE_TYPES.COAL and not player.researched_coal(): continue
        if resource_tile.resource.type == Constants.RESOURCE_TYPES.URANIUM and not player.researched_uranium(): continue

        dist = resource_tile.pos.distance_to(unit.pos)
        if dist < closest_dist:
            if resource_tile.pos in blocked_resources.values():  # and dist <= blocked_distance_param:
                if dist < 2:
                    continue
            closest_dist = dist
            closest_resource_tile = resource_tile

    if closest_resource_tile == None:
        with open(logfile, "a") as f:
            f.write(f"{observation['step']} No more Resources on the map!\n")
    return closest_resource_tile, closest_dist


def get_closest_city(player, unit):
    closest_dist = math.inf
    closest_city = None
    for k, city in player.cities.items():
        for city_tile in city.citytiles:
            dist = city_tile.pos.distance_to(unit.pos)
            if dist < closest_dist:
                closest_dist = dist
                closest_city = city
    return closest_city


def get_closest_citytile(player, unit):
    closest_dist = math.inf
    closest_city_tile = None
    for city in player.cities.values():
        for city_tile in city.citytiles:
            dist = city_tile.pos.distance_to(unit.pos)
            if dist < closest_dist:
                closest_dist = dist
                closest_city_tile = city_tile
    return closest_city_tile, dist


def get_closest_citytile_from_city(unit, targetCity):
    closest_dist = math.inf
    closest_city_tile = None
    for city_tile in targetCity.citytiles:
        dist = city_tile.pos.distance_to(unit.pos)
        if dist < closest_dist:
            closest_dist = dist
            closest_city_tile = city_tile
    return closest_city_tile


def move_to_given_tile(player, opponent, unit, target_position, observation, wants_to_build):

    global unit_movement

    with open(logfile, "a") as f:
        f.write(f"{observation['step']} {target_position}\n")

    # Calculation of the Differences of each Coordinate
    dir_diff = (target_position.x - unit.pos.x, target_position.y - unit.pos.y)
    xdiff = dir_diff[0]
    ydiff = dir_diff[1]

    # Failure: Unit is at given Tile and should not have entered this Method
    if xdiff == 0 and ydiff == 0:
        with open(logfile, "a") as f:
            f.write(f"{observation['step']} xdiff and ydiff = 0! Sign y: {np.sign(ydiff)} Sign x: {np.sign(xdiff)}\n")
        return None

    # Check which direction has the higher Difference
    if abs(ydiff) >= abs(xdiff):
        check_tile = game_state.map.get_cell(unit.pos.x, unit.pos.y + np.sign(ydiff))
        if is_target_position_valid(player, opponent, check_tile, observation, wants_to_build):
            unit_movement[unit.id] = check_tile
            return unit.move(unit.pos.direction_to(check_tile.pos))
        else:
            #Switch case with cas flutschers?
            if(xdiff == 0):
                xdiff = 1

            if (unit.pos.x + np.sign(xdiff) < game_state.map.width and unit.pos.x + np.sign(xdiff) >= 0):
                check_tile = game_state.map.get_cell(unit.pos.x + np.sign(xdiff), unit.pos.y)
                if is_target_position_valid(player, opponent, check_tile, observation, wants_to_build):
                    unit_movement[unit.id] = check_tile
                    return unit.move(unit.pos.direction_to(check_tile.pos))
            if (unit.pos.x - np.sign(xdiff) >= 0 and unit.pos.x - np.sign(xdiff) < game_state.map.width):
                check_tile = game_state.map.get_cell(unit.pos.x - np.sign(xdiff), unit.pos.y)
                if is_target_position_valid(player, opponent, check_tile, observation, wants_to_build):
                    unit_movement[unit.id] = check_tile
                    return unit.move(unit.pos.direction_to(check_tile.pos))
            #Failed to move
            with open(logfile, "a") as f:
                f.write(f"{observation['step']} Unit {unit.id} did not find a free tile to move!\n")
            if unit.id in unit_movement.keys():
                unit_movement.pop(unit.id)
            return None
    else:
        check_tile = game_state.map.get_cell(unit.pos.x + np.sign(xdiff), unit.pos.y)
        if is_target_position_valid(player, opponent, check_tile, observation, wants_to_build):
            unit_movement[unit.id] = check_tile
            return unit.move(unit.pos.direction_to(check_tile.pos))
        else:
            if (ydiff == 0):
                ydiff = 1
            if (unit.pos.y + np.sign(ydiff) < game_state.map.height and unit.pos.y + np.sign(ydiff) >= 0):
                check_tile = game_state.map.get_cell(unit.pos.x, unit.pos.y + np.sign(ydiff))
                if is_target_position_valid(player, opponent, check_tile, observation, wants_to_build):
                    unit_movement[unit.id] = check_tile
                    return unit.move(unit.pos.direction_to(check_tile.pos))
            if(unit.pos.y - np.sign(ydiff) >= 0 and unit.pos.y - np.sign(ydiff) < game_state.map.height):
                check_tile = game_state.map.get_cell(unit.pos.x, unit.pos.y - np.sign(ydiff))
                if is_target_position_valid(player, opponent, check_tile, observation, wants_to_build):
                    unit_movement[unit.id] = check_tile
                    return unit.move(unit.pos.direction_to(check_tile.pos))
            #Failed to move
            with open(logfile, "a") as f:
                f.write(f"{observation['step']} Unit {unit.id} did not find a free tile to move!\n")
            if unit.id in unit_movement.keys():
                unit_movement.pop(unit.id)
            return None



def is_target_position_valid(player, opponent, check_tile, observation, wants_to_build):

    global unit_movement

    if check_tile.citytile is not None:
        # Friendly City Tile
        if check_tile.citytile.team == player.team:
            if wants_to_build:
                return False
            else:
                return True
        else:
            # Enemy CityTile
            return False
    # Check if an other Unit already wants to move in that direction that turn
    if check_tile in unit_movement.values():
        #with open(logfile, "a") as f:
        #    f.write(f"{observation['step']} Unit movement blocked because already in unit_movement dict\n")
        return False
    # Check for Friendly Units/Enemy Units
    for unit_tmp in player.units:
        if unit_tmp.pos == check_tile.pos:
            if unit_tmp.id in unit_movement.keys():
                # The Unit wants to move away next turn so the tile is free
                return True
            else:
                #TODO check if the unit may still wants to move awaay next turn but was not tested yet maybe with cooldown test if it is even possible
                return False
    #TODO check for enemy units
    for unit_tmp in opponent.units:
        if unit_tmp.pos == check_tile.pos:
            return False

    return True


def build_worker_fun(player, observation):
    # TODO choose optimal City to spawn new worker
    # Choose fist City to spawn worker
    # city_to_spawn_new_worker = None
    with open(logfile, "a") as f:
        f.write(f"{observation['step']} We want to build a worker!\n")
    for city in player.cities.values():
        for cityTile in city.citytiles:
            if cityTile.can_act():
                with open(logfile, "a") as f:
                    f.write(f"{observation['step']} We build a worker!\n")
                return cityTile.build_worker()


# Returns True, if the position_to_test ist adjacent to a friendly citytile
def is_adjacent_to_resource_tile(position_to_test, observation):
    dirs = []
    #Checks for out of bounds tiles
    if position_to_test.x > 0:
        dirs.append((-1,0))
    if position_to_test.x < game_state.map.width-1:
        dirs.append((1,0))
    if position_to_test.y > 0:
        dirs.append((0,-1))
    if position_to_test.y < game_state.map.height-1:
        dirs.append((0, 1))

    for d in dirs:
        try:
            possible_empty_tile = game_state.map.get_cell(position_to_test.x + d[0], position_to_test.y + d[1])

            if possible_empty_tile.resource != None and possible_empty_tile.resource.amount > 0:
                return True

        except Exception as e:
            with open(logfile, "a") as f:
                f.write(f"{observation['step']}: Error While searching for adjacent resource tiles: {str(e)}\n")
            pass
    return False


# Returns True, if the position_to_test ist adjacent to a friendly citytile
def is_adjacent_to_city_tiles(position_to_test, player, observation):
    dirs = []
    #Checks for out of bounds tiles
    if position_to_test.x > 0:
        dirs.append((-1,0))
    if position_to_test.x < game_state.map.width-1:
        dirs.append((1,0))
    if position_to_test.y > 0:
        dirs.append((0,-1))
    if position_to_test.y < game_state.map.height-1:
        dirs.append((0, 1))

    for d in dirs:
        try:
            possible_empty_tile = game_state.map.get_cell(position_to_test.x + d[0], position_to_test.y + d[1])

            if possible_empty_tile.citytile != None and possible_empty_tile.citytile.team == player.team:
                return True

        except Exception as e:
            with open(logfile, "a") as f:
                f.write(f"{observation['step']}: Error While searching for adjacent city tiles: {str(e)}\n")
            pass
    return False


def is_tile_empty(position):
    possibly_empty_tile = game_state.map.get_cell(position.x, position.y)
    if possibly_empty_tile.resource == None and possibly_empty_tile.road == 0 and possibly_empty_tile.citytile == None:
        #with open(logfile, "a") as f:
        #    f.write(f"Empty Tile found\n")
        return True
    return False


# Returns the closest empty tile to empty near
def find_empty_tile_near(empty_near, game_state, observation):
    dirs = []

    #Checks for out of bounds tiles
    if empty_near.pos.x > 0:
        dirs.append((-1,0))
    if empty_near.pos.x < game_state.map.width-1:
        dirs.append((1,0))
    if empty_near.pos.y > 0:
        dirs.append((0,-1))
    if empty_near.pos.y < game_state.map.height-1:
        dirs.append((0, 1))

    for d in dirs:
        try:
            possible_empty_tile = game_state.map.get_cell(empty_near.pos.x + d[0], empty_near.pos.y + d[1])
            if is_tile_empty(possible_empty_tile.pos):
                return possible_empty_tile

        except Exception as e:
            with open(logfile, "a") as f:
                f.write(f"{observation['step']}: Error While searching for empty tiles: {str(e)}\n")
            pass
    return None


# Returns all closest empty tiles to empty near
def get_all_empty_tiles(empty_near, game_state, observation):
    dirs = []
    empty_tiles = []

    #Checks for out of bounds tiles
    if empty_near.pos.x > 0:
        dirs.append((-1,0))
    if empty_near.pos.x < game_state.map.width-1:
        dirs.append((1,0))
    if empty_near.pos.y > 0:
        dirs.append((0,-1))
    if empty_near.pos.y < game_state.map.height-1:
        dirs.append((0, 1))

    for d in dirs:
        try:
            possible_empty_tile = game_state.map.get_cell(empty_near.pos.x + d[0], empty_near.pos.y + d[1])
            if is_tile_empty(possible_empty_tile.pos):
                empty_tiles.append(possible_empty_tile)

        except Exception as e:
            with open(logfile, "a") as f:
                f.write(f"{observation['step']}: Error While searching for empty tiles: {str(e)}\n")
    return empty_tiles


# Returns the Cell of the requested direction from the given Position
def get_Cell_of_given_direction(currentPosition, direction, game_state):
    if direction == Constants.DIRECTIONS.NORTH:
        return game_state.map.get_cell(currentPosition.x - 1, currentPosition.y)
    elif direction == Constants.DIRECTIONS.SOUTH:
        return game_state.map.get_cell(currentPosition.x + 1, currentPosition.y)
    elif direction == Constants.DIRECTIONS.EAST:
        return game_state.map.get_cell(currentPosition.x, currentPosition.y + 1)
    elif direction == Constants.DIRECTIONS.NORTH:
        return game_state.map.get_cell(currentPosition.x, currentPosition.y - 1)


# Returns True if a City Tile is on the planned way
def is_city_tile_on_direct_way(position, target_pos, game_state):
    currentPosition = position
    while currentPosition != position:
        dir = position.direction_to(target_pos)
        cell = get_Cell_of_given_direction(currentPosition, dir, game_state)
        if cell.citytile is not None:
            return True
        else:
            currentPosition = cell.pos
    return False


def get_closest_empty_tile_adjacent_to_city(unit, game_state, city, observation):
    possible_empty_tiles = []

    for city_tile in city.citytiles:
        empty_tiles = get_all_empty_tiles(city_tile, game_state, observation)
        for tile in empty_tiles:
            if tile not in possible_empty_tiles:
                possible_empty_tiles.append(tile)

    closest_dist = math.inf
    closest_empty_tile = None
    for empty_tile in possible_empty_tiles:
        dist = unit.pos.distance_to(empty_tile.pos)
        if dist == closest_dist:
            # Chose the one tile, where the two directions are not 0 to prevent units getting stuck
            if not is_city_tile_on_direct_way(unit.pos, empty_tile.pos, game_state):
                closest_empty_tile = empty_tile
                with open(logfile, "a") as f:
                    f.write(
                        f"{observation['step']} Unit {unit.id} got prob. better empty tile to build to adjacent cityTile\n")
            #dir_diff = (unit.pos.x - empty_tile.pos.x, unit.pos.y - empty_tile.pos.y)
            #xdiff = dir_diff[0]
            #ydiff = dir_diff[1]
            #if xdiff != 0 and ydiff != 0:
            #    closest_empty_tile = empty_tile
            #    with open(logfile, "a") as f:
            #        f.write(f"{observation['step']} Unit {unit.id} got better empty tile to build to adjacent cityTile\n")
        elif dist < closest_dist:
            closest_dist = dist
            closest_empty_tile = empty_tile
    return closest_empty_tile

def get_closest_empty_tile(unit, game_state, observation):
    empty_tile = None
    tiles_to_check = []
    tiles_to_check.append(game_state.map.get_cell_by_pos(unit.pos))
    while empty_tile is None:
        for tile in tiles_to_check:
            empty_tiles = get_all_empty_tiles(tile, game_state, observation)
            if (len(empty_tiles) > 0):
                #TODO improve to closestTile?
                empty_tile = empty_tiles[0]
                break
            else:
                dirs=[]
                if tile.pos.x > 0:
                    dirs.append((-1, 0))
                if tile.pos.x < game_state.map.width - 1:
                    dirs.append((1, 0))
                if tile.pos.y > 0:
                    dirs.append((0, -1))
                if tile.pos.y < game_state.map.height - 1:
                    dirs.append((0, 1))
                for dir in dirs:
                    tiles_to_check.append(game_state.map.get_cell(tile.pos.x + dir[0], tile.pos.y + dir[1]))
    return empty_tile

def get_direct_adjacent_resc_tiles(tile_to_test, resc_list):
    adjacent_resc_tiles = []
    for tile in resc_list:
        if tile.pos.is_adjacent(tile_to_test.pos):
            # Only add Rescources with the same Resource type
            if tile_to_test.resource.type == tile.resource.type:
                adjacent_resc_tiles.append(tile)
    return adjacent_resc_tiles

def get_adjacent_resc_tiles(rescources_list, observation):
    resc_list_copy = list(rescources_list)
    clusters = []
    while len(resc_list_copy) > 0:
        cluster = []
        with open(logfile, "a") as f:
            f.write(f"{observation['step']} {resc_list_copy[0].pos}\n")
        cell = resc_list_copy[0]
        cluster.append(cell)
        resc_list_copy.pop(0)
        adjacent_tiles = get_direct_adjacent_resc_tiles(cell, resc_list_copy)
        cluster.extend(adjacent_tiles)
        resc_list_copy = list(set(resc_list_copy) - set(adjacent_tiles))
        while len(adjacent_tiles) > 0:
            for tile in adjacent_tiles:
                cluster.append(tile)
                adjacent_tiles.extend(get_direct_adjacent_resc_tiles(tile, resc_list_copy))
                adjacent_tiles.remove(tile)
                resc_list_copy = list(set(resc_list_copy) - set(adjacent_tiles))
        clusters.append(cluster)
    return clusters

# Creates and returns a Dictionary from the given List using ids starting from
def create_dict_from_list(item_list):
    dict = {}
    for idX, item in enumerate(item_list):
        dict[idX] = item
    return dict

def delete_dict_entry_by_value(dict, pValue):
    for key, value in dict.items():
        if value == pValue:
            del dict[key]
    return dict

# Adds an Entry to the unit_to_action_dict for the given parameters
def create_unit_to_action_entry(unit, action, target_position):
    global unit_to_action_dict
    if action is not None:
        unit_to_action_dict[unit.id] = action, target_position
    else:
        with open(logfile, "a") as f:
            f.write(f"Action was none!\n")


def choose_action_for_unit(player, unit, resource_list, isNight, opponent, observation):

    global blocked_resources
    global max_walk_home_distance
    global max_distance_to_fuel_city

    target_pos = None
    action = ACTION_TYPES.NONE

    with open(logfile, "a") as f:
        f.write(
            f"{observation['step']} Searching action for unit: {unit.id}!\n")

    if unit.id in blocked_resources.keys():
        blocked_resources.pop(unit.id)
    if isNight:
        # Move to closest City Tile if player has a cityTile
        if player.city_tile_count > 0:
            closest_city_tile, dist = get_closest_citytile(player, unit)
            if(closest_city_tile is None):
                # If there is no citytile then the unit should go farm
                closest_resource_tile, distance = get_closest_resources(unit, resource_list, player, observation)
                if (closest_resource_tile is not None):
                    return ACTION_TYPES.FARM, closest_resource_tile.pos
                else:
                    with open(logfile, "a") as f:
                        f.write(
                            f"{observation['step']} Error in get_closest_city Method returning None\n")
                    return ACTION_TYPES.NONE, None
            if dist > max_walk_home_distance:
                closest_resource_tile, distance = get_closest_resources(unit, resource_list, player, observation)
                with open(logfile, "a") as f:
                    f.write(
                        f"{observation['step']} Unit {unit.id} distance to home is too far. Distance to nearest resc Tile: {distance}\n")
                if dist < distance:
                    with open(logfile, "a") as f:
                        f.write(
                            f"{observation['step']} Unit {unit.id} distance to home is still closer than Distance to nearest resc Tile so moving to cityTile\n")
                    return ACTION_TYPES.STAY_HOME, closest_city_tile.pos
                else:
                    return ACTION_TYPES.FARM, closest_resource_tile.pos
            else:
                return ACTION_TYPES.STAY_HOME, closest_city_tile.pos
        else:
            closest_resource_tile, distance = get_closest_resources(unit, resource_list, player, observation)
            if (closest_resource_tile is not None):
                blocked_resources[unit.id] = closest_resource_tile.pos
                return ACTION_TYPES.FARM, closest_resource_tile.pos
            else:
                #TODO
                with open(logfile, "a") as f:
                    f.write(
                        f"{observation['step']} Error in get_closest_city Method2 returning None\n")
                return ACTION_TYPES.NONE, None
    else:
        if unit.get_cargo_space_left() == 0:
            action_list = [ACTION_TYPES.EXPLORE, ACTION_TYPES.BUILD_CITY, ACTION_TYPES.FUEL_UP_CITY]
            # Do not explore on the first day cylce
            if observation["step"] < 20:
                action = ACTION_TYPES.BUILD_CITY
            else:
                distribution = [.1, .4, .5]
                action = np.random.choice(action_list, p=distribution)

            if action == ACTION_TYPES.EXPLORE:
                target_cluster = ClusterManager.get_unexplored_cluster(player, unit, observation)
                if (target_cluster != None):
                    target_pos = ClusterManager.calculateIntegerCenterofCluster(target_cluster)
                else:
                    with open(logfile, "a") as f:
                        f.write(
                            f"{observation['step']} get_unexplored_cluster returned None!\n")
                    return ACTION_TYPES.NONE, None
            else:
                # TODO chose fuel up city based on closest city fuel need
                # If action set to BUILD_CITY then unit should build city instantly
                if action == ACTION_TYPES.BUILD_CITY:
                    closest_city = get_closest_city(player, unit)
                    if closest_city is None:
                        with open(logfile, "a") as f:
                            f.write(
                                f"{observation['step']}: Unit {unit.id} closest City returned None!\n")
                        tile = find_place_to_build_new_city(unit, game_state, observation)
                    else:
                        tile = find_place_to_build_cityTile_adjacent_to_city(unit, game_state, closest_city, observation)
                        # Unit got stuck when city was surrounded by rescources
                        if tile is None:
                            tile = find_place_to_build_new_city(unit, game_state, observation)
                    with open(logfile, "a") as f:
                        f.write(
                            f"{observation['step']}: Unit {unit.id} target_build_location at {tile.pos.x}, {tile.pos.y}!\n")
                    target_pos = tile.pos
                    return action, target_pos

                #Fuel up the City!
                possibleCities= []
                distances = []

                with open(logfile, "a") as f:
                    f.write(
                        f"{observation['step']} FUEL UP CITY!\n")

                for city in player.cities.values():
                    if city.fuel <= city.get_light_upkeep():
                        closest_city_tile = get_closest_citytile_from_city(unit, city)
                        distance = unit.pos.distance_to(closest_city_tile.pos)
                        if distance < max_distance_to_fuel_city:
                            possibleCities.append(city)
                            distances.append(distance)
                if len(possibleCities) != 0:
                        # Choose a random city with higher probability for closer cities
                        if len(possibleCities) > 1:
                            city = np.random.choice(possibleCities, p=1-(np.array(distances)/sum(distances)))
                        else:
                            city = possibleCities[0]
                        action = ACTION_TYPES.FUEL_UP_CITY
                        target_pos = get_closest_citytile_from_city(unit, city).pos
                else:
                    if len(player.cities.values()) == 0:
                        action = ACTION_TYPES.BUILD_NEW_CITY
                        target_pos = find_place_to_build_new_city(unit, game_state, observation).pos
                    else:
                        action = ACTION_TYPES.BUILD_CITY
                        closest_city = get_closest_city(player, unit)
                        tile = find_place_to_build_cityTile_adjacent_to_city(unit, game_state, closest_city, observation)
                        if tile is None:
                            tile = find_place_to_build_new_city(unit, game_state, observation)
                        with open(logfile, "a") as f:
                            f.write(f"{observation['step']}: Unit {unit.id} target_build_location at {tile.pos.x}, {tile.pos.y}!\n")
                        target_pos = tile.pos
            return action, target_pos
        else:
            closest_resource_tile, distance = get_closest_resources(unit, resource_list, player, observation)
            if (closest_resource_tile is not None):
                blocked_resources[unit.id] = closest_resource_tile.pos
                return ACTION_TYPES.FARM, closest_resource_tile.pos
            else:
                #TODO
                with open(logfile, "a") as f:
                    f.write(
                        f"{observation['step']} Error in choose_action_for_unit Method nothing matched!\n")
                return ACTION_TYPES.NONE, None


def find_place_to_build_new_city(unit, game_state, observation):
    tile = get_closest_empty_tile(unit, game_state, observation)
    return tile


def find_place_to_build_cityTile_adjacent_to_city(unit, game_state, city, observation):
    global max_build_to_adjacent_city_tile_distance
    distance = unit.pos.distance_to(get_closest_citytile_from_city(unit, city).pos)
    if (distance > max_build_to_adjacent_city_tile_distance):
        with open(logfile, "a") as f:
            f.write(
                f"{observation['step']} find_place_to_build_cityTile_adjacent_to_city used built to closest empty tile because closest city is too far away\n")
        tile = get_closest_empty_tile(unit, game_state, observation)
    else:
        with open(logfile, "a") as f:
            f.write(
                f"{observation['step']} find_place_to_build_cityTile_adjacent_to_city used built to closest empty adjacent tile\n")
        tile = get_closest_empty_tile_adjacent_to_city(unit, game_state, city, observation)
    return tile

def is_Rescource_Empty(position):
    cell = game_state.map.get_cell(position.x, position.y)
    if cell.has_resource():
        return False
    else:
        return True


def agent(observation, configuration):
    global game_state
    global build_location
    global night_cycle
    global unit_to_city_dict
    global blocked_resources
    global max_city_walk_distance_factor
    global unit_to_cluster_id_dict
    global unit_to_action_dict
    global cluster_id_to_cluster_dict
    global unit_movement

    ### Do not edit ###
    if observation["step"] == 0:
        game_state = Game()
        game_state._initialize(observation["updates"])
        game_state._update(observation["updates"][2:])
        game_state.id = observation.player
    else:
        game_state._update(observation["updates"])
    
    actions = []

    ### AI Code goes down here! ###
    player = game_state.players[observation.player]
    opponent = game_state.players[(observation.player + 1) % 2]
    width, height = game_state.map.width, game_state.map.height

    resource_tiles = get_resource_tiles(game_state, width, height)

    unit_movement = {}

    GameStats.updateStats(player, resource_tiles)

    if observation["step"] == 0:
        # Initialize the clusters
        Logfile.reset()
        ClusterManager.init_Clusters(resource_tiles, observation)
    else:
        # Update the clusters removing empty tiles from the cluster
        ClusterManager.update_Clusters()

    #Sets the isNight Variable to night, it is currently night
    if observation["step"] % 40 >= 30:
        isNight = True
        # Reset all units with the Build_City Actiontype
        for unit in player.units:
            if unit.id in unit_to_action_dict.keys():
                ACTION_TYPE, target_position = unit_to_action_dict[unit.id]
                if ACTION_TYPE == ACTION_TYPES.BUILD_CITY or ACTION_TYPE == ACTION_TYPES.BUILD_NEW_CITY:
                    with open(logfile, "a") as f:
                        f.write(
                            f"{observation['step']} Action for unit {unit.id} reseted\n")
                    # Give the unit a new Task
                    action, target_pos = choose_action_for_unit(player, unit, resource_tiles, isNight, opponent, observation)
                    create_unit_to_action_entry(unit, action, target_pos)
    else:
        isNight = False

    if observation["step"]% 40 == 0:
        #Reset all units with the Stay_Home Actiontype
        for unit in player.units:
            if unit.id in unit_to_action_dict.keys():
                ACTION_TYPE, target_position = unit_to_action_dict[unit.id]
                if ACTION_TYPE == ACTION_TYPES.STAY_HOME:
                    # Give the unit a new Task
                    action, target_pos = choose_action_for_unit(player, unit, resource_tiles, isNight, opponent, observation)
                    with open(logfile, "a") as f:
                        f.write(f"{observation['step']} Action for unit {unit.id} after night: Action: {action}, {target_pos}\n")
                    create_unit_to_action_entry(unit, action, target_pos)

    workers = [u for u in player.units if u.is_worker()]

    #max_city_walk_distance = (observation["step"]//40.0) * max_city_walk_distance_factor + 4

    for w in workers:
        if w.id not in unit_to_city_dict:
            with open(logfile, "a") as f:
                f.write(f"{observation['step']} Found worker unaccounted for {w.id}\n")
            city_assignment = get_closest_city(player, w)
            unit_to_city_dict[w.id] = city_assignment
        '''
        if w.id not in unit_to_cluster_id_dict:
            cluster_id = get_closest_cluster_id_by_resource_type(w.pos, clusters, RESOURCE_TYPES.WOOD)
            unit_to_cluster_id_dict[w.id] = cluster_id
        '''

    for unit in player.units:
        if unit.id not in unit_to_action_dict:
            # Get new Task for unit
            action, target_pos = choose_action_for_unit(player, unit, resource_tiles, isNight, opponent,observation)
            create_unit_to_action_entry(unit, action, target_pos)

    cities = player.cities.values()
    city_tiles = []

    for city in cities:
        for c_tile in city.citytiles:
            city_tiles.append(c_tile)

    for unit in player.units:
        if not unit.can_act():
            continue

        if unit.id not in unit_to_action_dict.keys():
            with open(logfile, "a") as f:
                f.write(f"{observation['step']} Unit not in unit dict {unit.id}\n")
            action, target_pos = choose_action_for_unit(player, unit, resource_tiles, isNight, opponent, observation)
            create_unit_to_action_entry(unit, action, target_pos)

        action, target_pos = unit_to_action_dict[unit.id]
        unit_action = None

        with open(logfile, "a") as f:
            f.write(f"{observation['step']} Unit {unit.id} has action {action} and target position {target_pos}\n")

        if action == ACTION_TYPES.NONE:
            # Attempt one more time to change Action to a usefull one
            action, target_pos = choose_action_for_unit(player, unit, resource_tiles, isNight, opponent, observation)
            create_unit_to_action_entry(unit, action, target_pos)

        if action == ACTION_TYPES.EXPLORE:
            if unit.pos.distance_to(target_pos) >= 3:
                unit_action = move_to_given_tile(player, opponent, unit, target_pos, observation, True)
                if unit_action == None:
                    with open(logfile, "a") as f:
                        f.write(f"{observation['step']} Unit {unit.id} has action None while Exploring\n")
                    continue
            elif unit.get_cargo_space_left() != 0:
                # It is probably night so the unit has to farm some resc first to then build a city and stay on the city tile adjacent to a resource tile so the city_tile does not run out of Fuel
                action = ACTION_TYPES.FARM
                resc_tile, distance = get_closest_resources(unit, resource_tiles, player, observation)
                target_pos = resc_tile.pos
                if target_pos is not None:
                    blocked_resources[unit.id] = resc_tile.pos
                    create_unit_to_action_entry(unit, action, target_pos)
            else:
                if is_tile_empty(unit.pos) and is_adjacent_to_resource_tile(unit.pos, observation):
                    actions.append(unit.build_city())
                    if unit.id in unit_to_action_dict.keys():
                        unit_to_action_dict.pop(unit.id)
                else:
                    if game_state.map.get_cell_by_pos(unit.pos).has_resource():
                        # Unit seems to be already on the cluster so unit should maybe go back to build a House
                        action = ACTION_TYPES.BUILD_NEW_CITY
                    else:
                        # Cluster not reached yet so go closer
                        unit_action = move_to_given_tile(player, opponent, unit, target_pos, observation, True)
                        if unit_action == None:
                            with open(logfile, "a") as f:
                                f.write(f"{observation['step']} Unit {unit.id} has action None while building new City\n")
                            continue
                        else:
                            actions.append(unit_action)
                            continue

        if action == ACTION_TYPES.FARM:
            # Unit is full or rescources so farming completed
            if unit.cargo.uranium >= 15 or unit.cargo.coal >= 40:
                action = ACTION_TYPES.FUEL_UP_CITY
                # If the unit farmed unranium then the Unit should fuel up the city
                # Fuel up the City!
                possibleCities = []
                distances = []
                if player.cities is not None:
                    for city in player.cities.values():
                        if city.fuel <= city.get_light_upkeep():
                            closest_city_tile = get_closest_citytile_from_city(unit, city)
                            dist = unit.pos.distance_to(closest_city_tile.pos)
                            if dist > 10:
                                continue
                            else:
                                possibleCities.append(closest_city_tile)
                                distances.append(dist)
                    if len(possibleCities) > 0:
                        chosen_city_tile = np.random.choice(possibleCities)
                        target_pos = chosen_city_tile.pos
                        unit_action = move_to_given_tile(player, opponent, unit, target_pos, observation, False)
                        if unit_action == None:
                            with open(logfile, "a") as f:
                                f.write(
                                    f"{observation['step']} Unit {unit.id} has action None while Farming with high resources to fuel up city within distance of 10\n")
                            continue
                        else:
                            actions.append(unit_action)
                            continue
                    else:
                        min_distance = math.inf
                        closest_city_tile = None
                        for city in player.cities.values():
                            if city.fuel <= city.get_light_upkeep():
                                if city.citytiles is not None:
                                    tmp_closest_city_tile = get_closest_citytile_from_city(unit, city)
                                    dist = unit.pos.distance_to(tmp_closest_city_tile.pos)
                                    if dist < min_distance:
                                        closest_city_tile = tmp_closest_city_tile
                                        min_distance = dist
                        if closest_city_tile is not None:
                            target_pos = closest_city_tile.pos
                            unit_action = move_to_given_tile(player, opponent, unit, target_pos, observation, False)
                            if unit_action == None:
                                with open(logfile, "a") as f:
                                    f.write(
                                        f"{observation['step']} Unit {unit.id} has action None while Farming with high resources to fuel up city without distance\n")
                                continue
                            else:
                                actions.append(unit_action)
                                continue
                        else:
                            action, target_pos = choose_action_for_unit(player, unit, resource_tiles, isNight, opponent, observation)
                            create_unit_to_action_entry(unit, action, target_pos)
                            continue

            if unit.get_cargo_space_left() == 0:
                action, target_pos = choose_action_for_unit(player, unit, resource_tiles, isNight, opponent, observation)
                create_unit_to_action_entry(unit, action, target_pos)
                with open(logfile, "a") as f:
                    f.write(f"{observation['step']} Unit {unit.id} got new Action {action} after Farming at: {target_pos}\n")
                if target_pos is not None:
                    if action == ACTION_TYPES.BUILD_CITY or action == ACTION_TYPES.BUILD_NEW_CITY:
                        unit_action = move_to_given_tile(player, opponent, unit, target_pos, observation, True)
                    else:
                        unit_action = move_to_given_tile(player, opponent, unit, target_pos, observation, False)
                    if unit_action == None:
                        with open(logfile, "a") as f:
                            f.write(f"{observation['step']} Unit {unit.id} has action None while Farming\n")
                        continue
                    else:
                        actions.append(unit_action)
                        continue

            # Unit is on target Resource Tile and has space left and wants to farm. #TODO what when tile gets empty while collecting?
            if unit.pos == target_pos:

                if not is_Rescource_Empty(target_pos):
                    continue
                else:
                    with open(logfile, "a") as f:
                        f.write(f"{observation['step']} Unit {unit.id} resource tile exausted during farming. Searching new action for unit\n")
                    action, target_pos = choose_action_for_unit(player, unit, resource_tiles, isNight, opponent,observation)
                    create_unit_to_action_entry(unit, action, target_pos)
                    # If the action if farming then the unit can proceed else it needs to wait a turn
                    if action != ACTION_TYPES.FARM:
                        continue

            if target_pos is not None:
                unit_action = move_to_given_tile(player, opponent, unit, target_pos, observation, False)
                if unit_action == None:
                    with open(logfile, "a") as f:
                        f.write(f"{observation['step']} Unit {unit.id} has action None while Farming with target_pos None\n")
                    continue
                else:
                    actions.append(unit_action)
                    continue

            if target_pos is None:
                with open(logfile, "a") as f:
                    f.write(f"{observation['step']}: Unit {unit.id} target farming pos is None!\n")
                resc_tile, distance = get_closest_resources(unit, resource_tiles, player, observation)
                target_pos = resc_tile.pos
                if target_pos is not None:
                    blocked_resources[unit.id] = target_pos.pos
                    create_unit_to_action_entry(unit, action, target_pos)
                else:
                    if unit.id in unit_to_action_dict.keys():
                        unit_to_action_dict.pop(unit.id)
                    continue
        elif action == ACTION_TYPES.NONE:
            with open(logfile, "a") as f:
                f.write(f"{observation['step']}: Action still NONE asserted to unit with id: {unit.id}!\n")
            continue
        elif action == ACTION_TYPES.BUILD_CITY:
            if unit.get_cargo_space_left() != 0:
                with open(logfile, "a") as f:
                    f.write(f"{observation['step']} Unit {unit.id} wanted to Build a City but did not had enough rescources\n")
                action, target_pos = choose_action_for_unit(player, unit, resource_tiles, isNight, opponent,observation)
                create_unit_to_action_entry(unit, action, target_pos)
                continue
            # Move to target tile to build the City
            # Check if unit is close to the target location and if the tile is blocked by (enemy) unit chose close new building location to prevent beeing blocked
            if target_pos is None:
                with open(logfile, "a") as f:
                    f.write(f"{observation['step']}: Unit {unit.id} target build position was None!\n")
                cell = find_place_to_build_cityTile_adjacent_to_city(unit, game_state, get_closest_city(player, unit), observation)
                if cell is None:
                    cell = find_place_to_build_new_city(unit, game_state, observation)
                target_pos = cell.pos


            if target_pos is None:
                with open(logfile, "a") as f:
                    f.write(f"{observation['step']}: Unit {unit.id} did not found place to build!\n")
                if unit.id in unit_to_action_dict.keys():
                    unit_to_action_dict.pop(unit.id)
                continue
            if unit.pos == target_pos:
                if game_state.map.get_cell_by_pos(unit.pos).citytile is not None:
                    with open(logfile, "a") as f:
                        f.write(f"{observation['step']}: Unit {unit.id} is on target_position and wants to build a City!\n")
                unit_action = unit.build_city()
                actions.append(unit_action)
                if unit.id in unit_to_action_dict.keys():
                    unit_to_action_dict.pop(unit.id)
                continue
            else:
                unit_action = move_to_given_tile(player, opponent, unit, target_pos, observation, False)
                if unit_action == None:
                    with open(logfile, "a") as f:
                        f.write(f"{observation['step']} Unit {unit.id} has action None while Building a City\n")
                    continue
                else:
                    actions.append(unit_action)
                    continue
        elif action == ACTION_TYPES.BUILD_NEW_CITY:
            if unit.get_cargo_space_left() != 0:
                with open(logfile, "a") as f:
                    f.write(f"{observation['step']} Unit {unit.id} wanted to Build new City but did not had enough rescources\n")
                action, target_pos = choose_action_for_unit(player, unit, resource_tiles, isNight, opponent,observation)
                create_unit_to_action_entry(unit, action, target_pos)
                continue
            # Move to target tile to build the City
            if target_pos is not None:
                if unit.pos == target_pos:
                    unit_action = unit.build_city()
                    actions.append(unit_action)
                    if unit.id in unit_to_action_dict.keys():
                        unit_to_action_dict.pop(unit.id)
                    continue
                else:
                    unit_action = move_to_given_tile(player, opponent, unit, target_pos, observation, False)
                    if unit_action == None:
                        with open(logfile, "a") as f:
                            f.write(f"{observation['step']} Unit {unit.id} has action None while Build new City\n")
                        continue
                    else:
                        actions.append(unit_action)
                        continue
            # Check if unit is close to the target location and if the tile is blocked by (enemy) unit chose close new building location to prevent beeing blocked
            if target_pos is None:
                target_pos = find_place_to_build_new_city(player, game_state, observation)
            if target_pos is None:
                with open(logfile, "a") as f:
                    f.write(f"{observation['step']}: Unit {unit.id} did not found place to build!\n")
                if unit.id in unit_to_action_dict.keys():
                    unit_to_action_dict.pop(unit.id)
                continue

        elif action == ACTION_TYPES.STAY_HOME:
            # status to stay/move to a city tile because it is currently night to save fuel on units
            if game_state.map.get_cell_by_pos(unit.pos).citytile is not None:
                # Unit is on friendly cityTile so unit stays there
                continue

            if target_pos is not None:
                unit_action = move_to_given_tile(player, opponent, unit, target_pos, observation, False)
                if unit_action == None:
                    with open(logfile, "a") as f:
                        f.write(f"{observation['step']} Unit {unit.id} has action None while stay home\n")
                    continue
                else:
                    actions.append(unit_action)
                    continue
            else:
                closest_city, distance = get_closest_citytile(player, unit)
                unit_action = move_to_given_tile(player, opponent, unit, closest_city, observation, False)
                if unit_action == None:
                    with open(logfile, "a") as f:
                        f.write(f"{observation['step']} Unit {unit.id} has action None while Stay Home\n")
                    continue
                else:
                    actions.append(unit_action)
                    continue
        elif action == ACTION_TYPES.FUEL_UP_CITY:
            if target_pos is not None:
                # Unit arrived at the City so it fueled it up and is ready for new orders # TODO optimize because unit can't do anything for one turn
                if unit.pos == target_pos:
                    if unit.id in unit_to_action_dict.keys():
                        unit_to_action_dict.pop(unit.id)
                    continue
                unit_action = move_to_given_tile(player, opponent, unit, target_pos, observation, False)
                if unit_action == None:
                    with open(logfile, "a") as f:
                        f.write(f"{observation['step']} Unit {unit.id} has action None while Fueling up the city\n")
                    continue
                else:
                    actions.append(unit_action)
                    continue
            else:
                if unit.id in unit_to_action_dict.keys():
                    unit_to_action_dict.pop(unit.id)
                continue
        if unit_action is not None:
            actions.append(unit_action)
            if unit.id in unit_to_action_dict.keys():
                unit_to_action_dict.pop(unit.id)
        else:
            with open(logfile, "a") as f:
                f.write(f"{observation['step']}: Action for unit {unit.id} returned NONE!\n")


    # TODO optimize a little bit more for example at the end when there are already too many units on the field
    can_create = len(city_tiles) - len(workers)

    if len(city_tiles) > 0:
        for city_tile in city_tiles:
            if city_tile.can_act():
                if can_create > 0:
                    actions.append(city_tile.build_worker())
                    can_create -= 1
                    with open(logfile, "a") as f:
                        f.write(f"{observation['step']}: Created a worker!\n")
                else:
                    actions.append(city_tile.research())
                    with open(logfile, "a") as f:
                        f.write(f"{observation['step']}: Doing Research!\n")
    
    return actions
