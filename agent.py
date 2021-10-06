import math, sys
from lux.game import Game
from lux.game_map import Cell, RESOURCE_TYPES
from lux.constants import Constants
from lux.game_constants import GAME_CONSTANTS
from lux import annotate
import logging
import numpy as np

#logging.basicConfig(filename="agent.log", level=logging.INFO)
logfile = "agent.log"

open(logfile, "w")

DIRECTIONS = Constants.DIRECTIONS
game_state = None
night_cycle = 10

build_location = None

unit_to_city_dict = {}
unit_to_resource_dict = {}

def get_resource_tiles(game_state, width, height):
    resource_tiles: list[Cell] = []
    for y in range(height):
        for x in range(width):
            cell = game_state.map.get_cell(x, y)
            if cell.has_resource():
                resource_tiles.append(cell)
    return resource_tiles

def get_closest_resources(unit, resource_tiles, player):
    closest_dist = math.inf
    closest_resource_tile = None
    # if the unit is a worker and we have space in cargo, lets find the nearest resource tile and try to mine it
    for resource_tile in resource_tiles:
        if resource_tile.resource.type == Constants.RESOURCE_TYPES.COAL and not player.researched_coal(): continue
        if resource_tile.resource.type == Constants.RESOURCE_TYPES.URANIUM and not player.researched_uranium(): continue
        # Skip already zugewiesene resource tiles
        if resource_tile in unit_to_resource_dict.values(): continue

        dist = resource_tile.pos.distance_to(unit.pos)
        if dist < closest_dist:
            closest_dist = dist
            closest_resource_tile = resource_tile
    return closest_resource_tile

def get_closest_city(player, unit):
    closest_dist = math.inf
    closest_city_tile = None
    for k, city in player.cities.items():
        for city_tile in city.citytiles:
            dist = city_tile.pos.distance_to(unit.pos)
            if dist < closest_dist:
                closest_dist = dist
                closest_city_tile = city_tile
    return closest_city_tile

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

    if abs(ydiff) > abs(xdiff):
        check_tile = game_state.map.get_cell(unit.pos.x, unit.pos.y + np.sign(ydiff))
        if is_target_position_valid(player, opponent, unit_movement, check_tile, observation, wants_to_build):
            unit_movement[unit.id] = check_tile
            return unit.move(unit.pos.direction_to(check_tile.pos))
        else:
            check_tile = game_state.map.get_cell(unit.pos.x + np.sign(xdiff), unit.pos.y)
            if is_target_position_valid(player, opponent, unit_movement, check_tile, observation, wants_to_build):
                unit_movement[unit.id] = check_tile
                return unit.move(unit.pos.direction_to(check_tile.pos))
            else:
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
            check_tile = game_state.map.get_cell(unit.pos.x, unit.pos.y + np.sign(ydiff))
            if is_target_position_valid(player, opponent, unit_movement, check_tile, observation, wants_to_build):
                unit_movement[unit.id] = check_tile
                return unit.move(unit.pos.direction_to(check_tile.pos))
            else:
                #Failed to move
                with open(logfile, "a") as f:
                    f.write(f"{observation['step']} Unit did not find a free tile to move!\n")
                return None



def is_target_position_valid(player, opponent, unit_movement, check_tile, observation, wants_to_build):
    if check_tile.citytile != None:
        # Friendly City Tile
        if check_tile.citytile.team == player.team:
            if wants_to_build:
                with open(logfile, "a") as f:
                    f.write(f"{observation['step']} Movement Not Valid: Friendly City Tile but wanats to build!\n")
                return False
            else:
                with open(logfile, "a") as f:
                    f.write(f"{observation['step']} Movement Valid: Friendly City Tile!\n")
                return True
        else:
            # Enemy CityTile
            with open(logfile, "a") as f:
                f.write(f"{observation['step']} Movement Not Valid: Opponent City Tile in the way!\n")
            return False
    # Check if an other Unit already wants to move in that direction that turn
    if check_tile in unit_movement.values():
        with open(logfile, "a") as f:
            f.write(f"{observation['step']} Movement Not Valid: Another Unit already wants to move there!\n")
        return False
    # Check for Friendly Units/Enemy Units
    for unit_tmp in player.units:
        if unit_tmp.pos == check_tile.pos:
            if unit_tmp.id in unit_movement.keys():
                # The Unit wants to move away next turn so the tile is free
                with open(logfile, "a") as f:
                    f.write(f"{observation['step']} Movement Valid: Friendly Unit on Tile but waants to move away!\n")
                return True
            else:
                #TODO check if the unit may still wants to move awaay next turn but was not tested yet maybe with cooldown test if it is even possible
                with open(logfile, "a") as f:
                    f.write(f"{observation['step']} Movement Not Valid: Friendly Unit in the way!\n")
                return False
    #TODO check for enemy units
    for unit_tmp in opponent.units:
        if unit_tmp.pos == check_tile.pos:
            with open(logfile, "a") as f:
                f.write(f"{observation['step']} Movement Not Valid: Opponent Unit in the way!\n")
            return False

    with open(logfile, "a") as f:
        f.write(f"{observation['step']} Movement Valid: No case matched, so I guess the way is free!\n")
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

def build_city(player, observation):
    pass

def move_to_target_position(player, unit, target_position):
    pass

def find_empty_tile_near(empty_near, game_state, observation):
    dirs = [(1, 0), (0, 1), (-1, 0), (0, -1), (1, -1), (-1, 1), (-1, -1), (1, 1)]

    for d in dirs:
        try:
            possible_empty_tile = game_state.map.get_cell(empty_near.pos.x + d[0], empty_near.pos.y + d[1])
            # logging.WARNING(f"{observation['step']}: Checking {possible_empty_tile}")

            if possible_empty_tile.resource == None and possible_empty_tile.road == 0 and possible_empty_tile.citytile == None:
                build_location = possible_empty_tile
                #actions.append(annotate.circle(build_location.pos.x, build_location.pos.y))
                return build_location
                # logging.WARNING(f"{observation['step']}: Found build location: {possible_empty_tile}")

        except Exception as e:
            # logging.WARNING(f"{observation['step']}: While searching for empty tiles: {str(e)}")
            with open(logfile, "a") as f:
                f.write(f"{observation['step']}: While searching for empty tiles: {str(e)}\n")
            pass

def agent(observation, configuration):
    global game_state
    global build_location
    global night_cycle
    global unit_to_resource_dict
    global unit_to_city_dict

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

    for w in workers:
        if w.id not in unit_to_city_dict:
            with open(logfile, "a") as f:
                f.write(f"{observation['step']} Found worker unaccounted for {w.id}\n")
            city_assignment = get_closest_city(player, w)
            unit_to_city_dict[w.id] = city_assignment

    for w in workers:
        if w.id not in unit_to_resource_dict:
            with open(logfile, "a") as f:
                f.write(f"{observation['step']} Found worker w/o resource {w.id}\n")
            resource_assignment = get_closest_resources(w, resource_tiles, player)
            unit_to_resource_dict[w.id] = resource_assignment

    #with open(logfile, "a") as f:
    #    f.write(f"{observation['step']} workers: {workers}\n")

    cities = player.cities.values()
    city_tiles = []

    for city in cities:
        for c_tile in city.citytiles:
            city_tiles.append(c_tile)

    build_city = True
    for city in player.cities.values():
        if city.fuel < city.get_light_upkeep()*20: #TODO - 5 * len(city.citytiles):
            build_city = False
            break
        elif len(workers) / len(city_tiles) >= 0.75:
            build_city = True

    #logging.info(f"{cities}")
    #logging.info(f"{city_tiles}")

    #TODO check collisions of workers aand prevent them
    #unit_movement_tiles = []
    unit_movement = {}

    # we iterate over all our units and do something with them
    for unit in player.units:
        if unit.is_worker() and unit.can_act():
            if unit.get_cargo_space_left() > 0:
                #closest_resource_tile = get_closest_resources(unit, resource_tiles, player)
                #if closest_resource_tile is not None:
                #    actions.append(unit.move(unit.pos.direction_to(closest_resource_tile.pos)))
                intended_resource = unit_to_resource_dict[unit.id]
                cell = game_state.map.get_cell(intended_resource.pos.x, intended_resource.pos.y)

                if not cell.has_resource():
                    intended_resource = get_closest_resources(unit, resource_tiles, player)
                    unit_to_resource_dict[unit.id] = intended_resource
                # Move to the intended resource
                movement = move_to_given_tile(player, opponent, unit, intended_resource, unit_movement, observation, False)
                if movement != None:
                    actions.append(movement)


            else:
                if build_city:
                    with open(logfile, "a") as f:
                        f.write(f"{observation['step']} We want to build a city!\n")
                    if build_location is None:
                        empty_near = game_state.map.get_cell_by_pos(unit.pos)
                        build_location = find_empty_tile_near(empty_near, game_state, observation)

                    if unit.pos == build_location.pos:
                        actions.append(unit.build_city())
                        build_city = False
                        build_location = None
                        continue
                    else:
                        #logging.INFO(f"{observation['step']}: Navigating to where we wish to build!")
                        with open(logfile, "a") as f:
                            f.write(f"{observation['step']}: Navigating to where we wish to build!\n")
                        movement = move_to_given_tile(player, opponent, unit, build_location, unit_movement, observation, build_city)
                        with open(logfile, "a") as f:
                            f.write(f"{observation['step']}: Movement to build a City: {movement}\n")
                        if movement != None:
                            actions.append(movement)
                        '''
                        #actions.append(unit.move(unit.pos.direction_to(build_location.pos)))
                        dir_diff = (build_location.pos.x - unit.pos.x, build_location.pos.y-unit.pos.y)
                        xdiff = dir_diff[0]
                        ydiff = dir_diff[1]

                        # decrease in x? West
                        # increase in x? East
                        # decrease in y? North
                        # increase in y? South

                        if abs(ydiff) > abs(xdiff):
                            check_tile = game_state.map.get_cell(unit.pos.x, unit.pos.y+np.sign(ydiff))
                            if check_tile.citytile == None:
                                if np.sign(ydiff) == 1:
                                    actions.append(unit.move("s"))
                                else:
                                    actions.append(unit.move("n"))
                            else:
                                if np.sign(xdiff) == 1:
                                    actions.append(unit.move("e"))
                                else:
                                    actions.append(unit.move("w"))
                        else:
                            check_tile = game_state.map.get_cell(unit.pos.x + np.sign(xdiff), unit.pos.y)
                            if check_tile.citytile == None:
                                if np.sign(xdiff) == 1:
                                    actions.append(unit.move("e"))
                                else:
                                    actions.append(unit.move("w"))
                            else:
                                if np.sign(ydiff) == 1:
                                    actions.append(unit.move("s"))
                                else:
                                    actions.append(unit.move("n"))
                        '''
                        continue
                # if unit is a worker and there is no cargo space left, and we have cities, lets return to them
                elif len(player.cities) > 0:
                    '''
                    if unit.id in unit_to_city_dict:
                        if unit_to_city_dict[unit.id] in city_tiles:
                            with open(logfile, "a") as f:
                                f.write(f"{observation['step']}: city in list: {unit_to_city_dict[unit.id]}\n")
                        else:
                            with open(logfile, "a") as f:
                                f.write(f"{observation['step']}: city not in list: {unit_to_city_dict[unit.id]}\n")
                    '''

                    if unit.id in unit_to_city_dict and unit_to_city_dict[unit.id] in city_tiles:

                        movement = move_to_given_tile(player, opponent, unit, unit_to_city_dict[unit.id], unit_movement, observation, build_city)
                        with open(logfile, "a") as f:
                            f.write(f"{observation['step']}: ifMovement: {movement}\n")
                        if movement != None:
                            actions.append(movement)

                        #move_dir = unit.pos.direction_to(unit_to_city_dict[unit].pos)
                        #actions.append(unit.move(move_dir))
                    else:
                        unit_to_city_dict[unit.id] = get_closest_city(player, unit)
                        movement = move_to_given_tile(player, opponent, unit, unit_to_city_dict[unit.id], unit_movement, observation, build_city)
                        with open(logfile, "a") as f:
                            f.write(f"{observation['step']}: elseMovement: {movement}\n")
                        if movement != None:
                            actions.append(movement)

                        #move_dir = unit.pos.direction_to(unit_to_city_dict[unit.id].pos)
                        #actions.append(unit.move(move_dir))
                    '''
                    if build_location:
                        actions.append(unit.move(unit.pos.direction_to(build_location.pos)))
                    else:
                        city_with_lowest_fuel = None
                        for city in player.cities.values():
                            if city_with_lowest_fuel is None:
                                city_with_lowest_fuel = city
                            elif city_with_lowest_fuel.fuel > city.fuel:
                                city_with_lowest_fuel = city
                        with open(logfile, "a") as f:
                            f.write(f"{observation['step']}: City with lowest fuel: {str(city_with_lowest_fuel.cityid)} {str(city_with_lowest_fuel.fuel)}\n")
                        #closest_city_tile = get_closest_city(player, unit)


                        if city_with_lowest_fuel is not None:
                            #Find nearest CityTile of that City
                            nearest_city_tile = None
                            for city_tile in city_with_lowest_fuel.citytiles:
                                if nearest_city_tile is None:
                                    nearest_city_tile = city_tile
                                if unit.pos.distance_to(nearest_city_tile.pos) > unit.pos.distance_to(city_tile.pos):
                                    nearest_city_tile = city_tile

                            move_dir = unit.pos.direction_to(nearest_city_tile.pos)
                            actions.append(unit.move(move_dir))'''

    # you can add debug annotations using the functions in the annotate object
    # actions.append(annotate.circle(0, 0))

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
