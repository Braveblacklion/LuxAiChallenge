import math, sys
from lux.game import Game
from lux.constants import Constants
from lux import annotate
import numpy as np

#logging.basicConfig(filename="agent.log", level=logging.INFO)
logfile = "agent_highest.log"

open(logfile, "w")

DIRECTIONS = Constants.DIRECTIONS
game_state = None
night_cycle = 10

build_location = None

unit_to_city_dict = {}
blocked_resources = {}

blocked_distance_param = 1
max_city_walk_distance_factor = 0

# Returns a list of all Resource Tiles in the Game
def get_resource_tiles(game_state, width, height):
    resource_tiles: list = []
    for y in range(height):
        for x in range(width):
            cell = game_state.map.get_cell(x, y)
            if cell.has_resource():
                resource_tiles.append(cell)
    return resource_tiles

# Get Closest researched resource
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
                if dist < 2:
                    continue
            closest_dist = dist
            closest_resource_tile = resource_tile

    if closest_resource_tile == None:
        with open(logfile, "a") as f:
            f.write(f"{observation['step']} No more Resources on the map!\n")
    return closest_resource_tile, closest_dist

# Get Closest resource of the highest researched type
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

# Returns the city with has the closest city tile to the unit
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

# Returns the closest CityTile fomr given City to the unit
def get_closest_citytile_from_city(unit, targetCity):
    closest_dist = math.inf
    closest_city_tile = None
    for city_tile in targetCity.citytiles:
        dist = city_tile.pos.distance_to(unit.pos)
        if dist < closest_dist:
            closest_dist = dist
            closest_city_tile = city_tile
    return closest_city_tile

# Unit movement
def move_to_given_tile(player, opponent, unit, target_location, unit_movement, observation, wants_to_build):
    dir_diff = (target_location.pos.x - unit.pos.x, target_location.pos.y - unit.pos.y)
    xdiff = dir_diff[0]
    ydiff = dir_diff[1]

    #with open(logfile, "a") as f:
    #    f.write(f"{observation['step']} Tile Validation started!\n")

    # decrease in x? West
    # increase in x? East
    # decrease in y? North
    # increase in y? South
    if xdiff == 0 and ydiff == 0:
        with open(logfile, "a") as f:
            f.write(f"{observation['step']} xdiff and ydiff = 0! Sign y: {np.sign(ydiff)} Sign x: {np.sign(xdiff)}\n")

        return None

    if abs(ydiff) >= abs(xdiff):
        check_tile = game_state.map.get_cell(unit.pos.x, unit.pos.y + np.sign(ydiff))
        if is_target_position_valid(player, opponent, unit_movement, check_tile, observation, wants_to_build):
            unit_movement[unit.id] = check_tile
            return unit.move(unit.pos.direction_to(check_tile.pos))
        else:
            #Switch case with cas flutschers?
            if(xdiff == 0):
                xdiff = 1

            if (unit.pos.x + np.sign(xdiff) < game_state.map.width and unit.pos.x + np.sign(xdiff) >= 0):
                check_tile = game_state.map.get_cell(unit.pos.x + np.sign(xdiff), unit.pos.y)
                if is_target_position_valid(player, opponent, unit_movement, check_tile, observation, wants_to_build):
                    unit_movement[unit.id] = check_tile
                    return unit.move(unit.pos.direction_to(check_tile.pos))
            if (unit.pos.x - np.sign(xdiff) >= 0 and unit.pos.x - np.sign(xdiff) < game_state.map.width):
                check_tile = game_state.map.get_cell(unit.pos.x - np.sign(xdiff), unit.pos.y)
                if is_target_position_valid(player, opponent, unit_movement, check_tile, observation, wants_to_build):
                    unit_movement[unit.id] = check_tile
                    return unit.move(unit.pos.direction_to(check_tile.pos))
            #Failed to move
            with open(logfile, "a") as f:
                f.write(f"{observation['step']} Unit did not find a free tile to move!\n")
            return None
    else:
        check_tile = game_state.map.get_cell(unit.pos.x + np.sign(xdiff), unit.pos.y)
        if is_target_position_valid(player, opponent, unit_movement, check_tile, observation, wants_to_build):
            unit_movement[unit.id] = check_tile
            return unit.move(unit.pos.direction_to(check_tile.pos))
        else:
            if (ydiff == 0):
                ydiff = 1
            if (unit.pos.y + np.sign(ydiff) < game_state.map.height and unit.pos.y + np.sign(ydiff) >= 0):
                check_tile = game_state.map.get_cell(unit.pos.x, unit.pos.y + np.sign(ydiff))
                if is_target_position_valid(player, opponent, unit_movement, check_tile, observation, wants_to_build):
                    unit_movement[unit.id] = check_tile
                    return unit.move(unit.pos.direction_to(check_tile.pos))
            if(unit.pos.y - np.sign(ydiff) >= 0 and unit.pos.y - np.sign(ydiff) < game_state.map.height):
                check_tile = game_state.map.get_cell(unit.pos.x, unit.pos.y - np.sign(ydiff))
                if is_target_position_valid(player, opponent, unit_movement, check_tile, observation, wants_to_build):
                    unit_movement[unit.id] = check_tile
                    return unit.move(unit.pos.direction_to(check_tile.pos))
            #Failed to move
            with open(logfile, "a") as f:
                f.write(f"{observation['step']} Unit did not find a free tile to move!\n")
            return None



def is_target_position_valid(player, opponent, unit_movement, check_tile, observation, wants_to_build):
    if check_tile.citytile != None:
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
        return False
    # Check for Friendly Units/Enemy Units
    for unit_tmp in player.units:
        if unit_tmp.pos == check_tile.pos:
            if unit_tmp.id in unit_movement.keys():
                # The Unit wants to move away next turn so the tile is free
                return True
            else:
                #TODO check if the unit may still wants to move away next turn but was not tested yet maybe with cooldown test if it is even possible
                return False
    #TODO check for enemy units
    for unit_tmp in opponent.units:
        if unit_tmp.pos == check_tile.pos:
            return False

    return True

# Returns True, if the position_to_test ist adjacent to a friendly citytile
def is_adjacent_to_resource_tile(position_to_test, player, observation):
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

# Checks if the tile at the give position is empty or not
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

# Returns the closest empty Tile to the unit
def get_closest_empty_tile(unit, game_state, city, observation):
    possible_empty_tiles = []

    for city_tile in city.citytiles:
        possible_empty_tiles.extend(get_all_empty_tiles(city_tile, game_state, observation))

    closest_dist = math.inf
    closest_empty_tile = None
    for empty_tile in possible_empty_tiles:
        dist = unit.pos.distance_to(empty_tile.pos)
        if dist < closest_dist:
            closest_dist = dist
            closest_empty_tile = empty_tile
    return closest_empty_tile

# Main Function
def agent(observation, configuration):
    global game_state
    global build_location
    global night_cycle
    global unit_to_city_dict
    global blocked_resources
    global max_city_walk_distance_factor

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

    workers = [u for u in player.units if u.is_worker()]

    max_city_walk_distance = (observation["step"]/40.0) * max_city_walk_distance_factor + 4


    for w in workers:
        if w.id not in unit_to_city_dict:
            with open(logfile, "a") as f:
                f.write(f"{observation['step']} Found worker unaccounted for {w.id}\n")
            city_assignment = get_closest_city(player, w)
            unit_to_city_dict[w.id] = city_assignment

    cities = player.cities.values()
    city_tiles = []

    for city in cities:
        for c_tile in city.citytiles:
            city_tiles.append(c_tile)

    build_city = True
    for city in player.cities.values():
        if city.fuel < city.get_light_upkeep()*20: #TODO - 5 * len(city.citytiles):
            build_city = False
            with open(logfile, "a") as f:
                f.write(f"{observation['step']} City needs more Fuel: needs {city.get_light_upkeep()*20} but has only {city.fuel}\n")
            break
        elif len(workers) / len(city_tiles) >= 0.75:
            build_city = True
    if observation['step'] <= 20:
        build_city = True

    unit_movement = {}
    # we iterate over all our units and do something with them
    for unit in player.units:
        #TODO change iterate from newest agent to oldest...??? usefull
        #TODO check if nightcycle is close if so all units should return to the closest CityTile
        if unit.is_worker() and unit.can_act():
            with open(logfile, "a") as f:
                f.write(f"{observation['step']} Unit: {unit.id}\n")
            if unit.get_cargo_space_left() > 0:
                #with open(logfile, "a") as f:
                #    f.write(f"{observation['step']} Unit has cargo space left!\n")
                unit_cell = game_state.map.get_cell(unit.pos.x, unit.pos.y)
                #if resource_tile.resource.type == Constants.RESOURCE_TYPES.COAL and not player.researched_coal(): continue
                #if resource_tile.resource.type == Constants.RESOURCE_TYPES.URANIUM and not player.researched_uranium(): continue
                if unit_cell.resource != None and unit_cell.resource.amount > 0:
                    if unit_cell.resource.type == Constants.RESOURCE_TYPES.COAL and not player.researched_coal(): continue
                    if unit_cell.resource.type == Constants.RESOURCE_TYPES.URANIUM and not player.researched_uranium(): continue
                    #unit is farming
                    blocked_resources[unit.id] = unit_cell.pos
                    continue

                intended_resource, distance = get_closest_resources(unit, resource_tiles, player, observation)
                if intended_resource == None:
                    with open(logfile, "a") as f:
                        f.write(f"{observation['step']} Intended resource returned None! because no more free Rescources!\n")
                    # TODO maybe move to city or block enemy players
                    continue
                #unit_to_resource_dict[unit.id] = intended_resource
                cell = game_state.map.get_cell(intended_resource.pos.x, intended_resource.pos.y)

                if unit.pos != cell.pos:
                    # Move to the intended resource
                    movement = move_to_given_tile(player, opponent, unit, intended_resource, unit_movement, observation, False)
                    if movement != None:
                        actions.append(movement)
                        ## Add annotations fot the way of the unit
                        actions.append(annotate.x(intended_resource.pos.x, intended_resource.pos.y))
                        actions.append(annotate.line(unit.pos.x, unit.pos.y, intended_resource.pos.x, intended_resource.pos.y))
                        if distance <= 1:
                            blocked_resources[unit.id] = cell.pos
                        #with open(logfile, "a") as f:
                        #    f.write(
                        #        f"{observation['step']} Movement found: {movement}\n")
                    else:
                        with open(logfile, "a") as f:
                            f.write(f"{observation['step']} Unit wants to move to Resource but movement returned None!\n")
                        continue
                #else:
                    #with open(logfile, "a") as f:
                    #    f.write(f"{observation['step']} Unit at intendet resource position!\n")
            else:
                if build_city:
                    with open(logfile, "a") as f:
                        f.write(f"{observation['step']} We want to build a city!\n")

                    ##Check Players Location first. If building is possible then start building
                    unit_pos_is_possible_build_location = False
                    if is_tile_empty(unit.pos):
                        unit_pos_is_possible_build_location = True
                        is_adjacent = is_adjacent_to_city_tiles(unit.pos, player, observation)

                        if is_adjacent:
                            actions.append(unit.build_city())
                            build_city = False
                            build_location = None
                            unit_to_city_dict.pop(unit.id)
                            with open(logfile, "a") as f:
                                f.write(
                                    f"{observation['step']}: Found Buildplace on unit pos and building now! {unit.id}\n")
                            continue
                    # check adjacent tiles of unit


                    ##First try only build whereever possible to an adjacent citytile
                    closest_city = get_closest_city(player, unit)
                    if closest_city != None:
                        build_location = get_closest_empty_tile(unit, game_state, closest_city, observation)
                    if build_location != None:
                        actions.append(annotate.circle(build_location.pos.x, build_location.pos.y))
                        with open(logfile, "a") as f:
                            f.write(
                                f"{observation['step']}: New Method found Buildplace on: x={build_location.pos.x}, y={build_location.pos.y}\n")


                    # If building to adjacent city tile is not possible then try to build somewhere else
                    if build_location == None:
                        with open(logfile, "a") as f:
                            f.write(f"{observation['step']}: Build Location none found adjacent to a CityTile!\n")
                        if unit_pos_is_possible_build_location:
                            actions.append(unit.build_city())
                            build_city = False
                            build_location = None
                            # Remove the unit out of the dict to automatically get the city assigned on next step, because the City is the closest
                            unit_to_city_dict.pop(unit.id)
                            with open(logfile, "a") as f:
                                f.write(
                                    f"{observation['step']}: Found Buildplace on unit pos non aadjaacent but building now!\n")
                            continue
                        else:
                            empty_near = game_state.map.get_cell_by_pos(unit.pos)
                            build_location = find_empty_tile_near(empty_near, game_state, observation)
                            if build_location != None:
                                with open(logfile, "a") as f:
                                    f.write(f"{observation['step']}: Build Location ({build_location.pos.x} ,{build_location.pos.y})\n")
                                actions.append(annotate.circle(build_location.pos.x, build_location.pos.y))
                            if build_location == None:
                                with open(logfile, "a") as f:
                                    f.write(f"{observation['step']}: Build Location none found even with backup method!!!\n")
                                continue

                    if unit.pos == build_location.pos:
                        actions.append(unit.build_city())
                        build_city = False
                        build_location = None
                        #Remove the unit out of the dict to automatically get the city assigned on next step, because the City is the closest
                        unit_to_city_dict.pop(unit.id)
                        continue
                    else:
                        with open(logfile, "a") as f:
                            f.write(f"{observation['step']}: Navigating to where we wish to build with {unit.id}!\n")
                        movement = move_to_given_tile(player, opponent, unit, build_location, unit_movement, observation, build_city)
                        if movement != None:
                            actions.append(movement)
                            if unit.id in blocked_resources.keys():
                                blocked_resources.pop(unit.id)
                        else:
                            with open(logfile, "a") as f:
                                f.write(
                                    f"{observation['step']}: Navigating to where we wish to build failed! Got no direction for {unit.id}!\n")
                # if unit is a worker and there is no cargo space left, and we have cities, lets return to them
                elif len(player.cities) > 0:
                    if unit.id in unit_to_city_dict:
                        cityFound = False
                        for city in city_tiles:
                            if (unit_to_city_dict[unit.id].cityid == city.cityid):
                                cityFound = True
                                break
                        if cityFound:
                            #Check if city already has enough fuel if so the
                            target_city_tile = get_closest_citytile_from_city(unit, unit_to_city_dict[unit.id])
                            if unit.pos.distance_to(target_city_tile.pos) >= max_city_walk_distance:
                                if is_tile_empty(unit.pos):
                                    actions.append(unit.build_city())
                                    with open(logfile, "a") as f:
                                        f.write(f"{observation['step']}: Build new City because old one is too far away\n")
                                    continue
                            movement = move_to_given_tile(player, opponent, unit, target_city_tile, unit_movement, observation, build_city)
                            if movement != None:
                                actions.append(movement)
                                if unit.id in blocked_resources.keys():
                                    blocked_resources.pop(unit.id)
                        else:
                            unit_to_city_dict[unit.id] = get_closest_city(player, unit)
                            target_city_tile = get_closest_citytile_from_city(unit, unit_to_city_dict[unit.id])
                            # Check if the distance to closest City tile is too high. If So build a city if the tile is empty elso move in to the closest city tile direction
                            if unit.pos.distance_to(target_city_tile.pos) >= max_city_walk_distance:
                                if is_tile_empty(unit.pos):
                                    actions.append(unit.build_city())
                                    with open(logfile, "a") as f:
                                        f.write(f"{observation['step']}: Build new City because old one is too far away\n")
                                    continue
                            movement = move_to_given_tile(player, opponent, unit, target_city_tile, unit_movement, observation, build_city)
                            with open(logfile, "a") as f:
                                f.write(f"{observation['step']}: elseMovement: {movement}\n")
                            if movement != None:
                                actions.append(movement)
                                if unit.id in blocked_resources.keys():
                                    blocked_resources.pop(unit.id)

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
