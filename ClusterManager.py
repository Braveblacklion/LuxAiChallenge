import math
from lux.game_objects import Position, Constants
from lux.game_map import RESOURCE_TYPES, Cell
import Logfile
import numpy as np

logfile = Logfile.logfile
cluster_list = []
explored_clusters = []

# Initialises the clusters
def init_Clusters(resources_list, observation):
    cluster_list = get_adjacent_resc_tiles(resources_list, observation)
    return cluster_list

# Updates the cluster while removing cells with no resources and returns the updated cluster_list
def update_Clusters():
    global cluster_list
    cluster_list_new = []
    for cluster in cluster_list:
        for cell in cluster:
            if not cell.has_resource:
                cluster.pop(cell)
                #with open(logfile, "a") as f:
                #    f.write(f"{observation['step']} update_clusters: Removed cell ({cell.pos.x}, {cell.pos.y}) without resc from cluster\n")
        cluster_list_new.append(cluster)
    cluster_list = cluster_list_new
    return cluster_list

def get_direct_adjacent_resc_tiles(tile_to_test :Cell, resc_list: list):
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

def get_unexplored_cluster(player, unit):
    searched_resource_type = []
    if player.researched_uranium():
        searched_resource_type = [Constants.RESOURCE_TYPES.URANIUM, Constants.RESOURCE_TYPES.COAL, Constants.RESOURCE_TYPES.WOOD]
    elif player.researched_coal():
        searched_resource_type = [Constants.RESOURCE_TYPES.COAL, Constants.RESOURCE_TYPES.WOOD]
    else:
        searched_resource_type = [Constants.RESOURCE_TYPES.WOOD]

    possible_clusters = []
    distance_to_cluster = []

    for resource_type in searched_resource_type:
        for cluster in cluster_list:
            if len(cluster) == 0:
                continue
            if cluster[0].resource.type == resource_type:
                possible_clusters.append(cluster)
                distance_to_cluster.append(unit.pos.distance_to(calculateCenterofCluster(cluster)))

    if len(possible_clusters) == 0:
        return None

    if len(possible_clusters) == 1:
        return possible_clusters[0]
    else:
        cluster = np.random.choice(possible_clusters, p=1 - np.array(distance_to_cluster) / sum(distance_to_cluster))

    return cluster

def update_Clusters_with_empty_list(cluster_list, observation):
    cluster_list_new = []
    empty_clusters = []
    for idX, cluster in enumerate(cluster_list):
        for cell in cluster:
            if not cell.has_resource:
                cluster.pop(cell)
                with open(logfile, "a") as f:
                    f.write(f"{observation['step']} update_clusters: Removed cell ({cell.pos.x}, {cell.pos.y}) without resc from cluster\n")
        if len(cluster) == 0:
            empty_clusters.append(idX)
            with open(logfile, "a") as f:
                f.write(
                    f"{observation['step']} update_clusters: Empty cluster detected {cluster}\n")
        else:
            cluster_list_new.append(cluster)
    return cluster_list_new, empty_clusters


def calculateCenterofCluster(cluster):
    x_sum = 0
    y_sum = 0
    count = 0
    for tile in cluster:
        x_sum += tile.pos.x
        y_sum += tile.pos.y
        count += 1
    x = x_sum/count
    y = y_sum/count

    return x,y

# Returns the closest cluster regarding its center from the given position
def get_closest_cluster(position, clusters):
    closest_dist = math.inf
    closest_cluster = None
    for cluster in clusters:
        x,y = calculateCenterofCluster(cluster)
        dist = position.pos.distance_to((x,y))
        if dist < closest_dist:
            closest_dist = dist
            closest_cluster = cluster
    return closest_cluster

# Returns the dict key of the closest cluster regarding its center from the given position
def get_closest_cluster_from_dict(position, dict):
    closest_dist = math.inf
    closest_cluster_key = None
    for key, value in dict:
        x,y = calculateCenterofCluster(value)
        dist = position.pos.distance_to((x,y))
        if dist < closest_dist:
            closest_dist = dist
            closest_cluster_key = key
    return closest_cluster_key

# Returns the closest cluster with special resource type regarding its center from the given position
def get_closest_cluster_by_resource_type(position: Position, clusters: list, resourceType: RESOURCE_TYPES):
    closest_dist = math.inf
    closest_cluster = None
    for cluster in clusters:
        if cluster[0].resource.type != resourceType:
            continue
        x,y = calculateCenterofCluster(cluster)
        dist = position.distance_to(Position(x,y))
        if dist < closest_dist:
            closest_dist = dist
            closest_cluster = cluster
    return closest_cluster

# Returns the closest cluster with special resource type regarding its center from the given position
def get_closest_cluster_id_by_resource_type(position, cluster_dict, resourceType):
    closest_dist = math.inf
    closest_cluster_id = None
    for key, value in cluster_dict:
        if value[0].resource.type != resourceType:
            continue
        x,y = calculateCenterofCluster(value)
        dist = position.distance_to(Position(x,y))
        if dist < closest_dist:
            closest_dist = dist
            closest_cluster_id = key
    return closest_cluster_id

