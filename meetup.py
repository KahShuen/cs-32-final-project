import json
import sys
from collections import deque


def load_users(filepath):
    # read the json file and return the list of user dicts
    pass


def build_graph(users):
    # take the list of users and build an undirected graph (adjacency list)
    # for each user, look at their wants_to_meet list and add edges both ways
    # return something like {"Alice": {"Bob"}, "Bob": {"Alice", "Charlie"}, ...}
    pass


def find_groups(graph):
    # use BFS to find connected components in the graph
    # start from an unvisited node, explore all reachable nodes = one group
    # repeat until all nodes visited
    # return a list of groups, where each group is a set of names
    # e.g. [{"Alice", "Bob", "Charlie"}, {"David", "Eve"}]
    pass


def find_common_times(users, group):
    # for a given group of people, find time slots where ALL of them are free
    # approach: chop each person's availability into 30-min blocks,
    # then intersect everybody's blocks
    # return the set of common blocks
    pass


def format_output(groups, users):
    # for each group, print who's in it and when they can meet
    # if no common time, say so
    pass


if __name__ == "__main__":
    filepath = sys.argv[1]
    users = load_users(filepath)
    graph = build_graph(users)
    groups = find_groups(graph)
    format_output(groups, users)
