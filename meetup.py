import json                        
import os                           # lets us check if a file exists on the computer
import sys                          # lets us read command line arguments like --show
from collections import deque       # gives us an efficient queue for BFS
from itertools import combinations  # lets us generate every possible subset of a group

USERS_DB = "users_db.json"          # the file where all user data is saved
MIN_SLOT_MINUTES = 30               # minimum length of an availability slot in minutes
BLOCK_SIZE = 1                      # we track availability minute by minute


def load_db():
    if os.path.exists(USERS_DB):    # os.path.exists checks if the file already exists on disk
        with open(USERS_DB, "r") as file:
            return json.load(file)  # read the JSON file and convert it into a python dictionary
    return {}                       # if the file doesn't exist yet, start with an empty dictionary


def save_db(db):
    with open(USERS_DB, "w") as file:
        json.dump(db, file, indent=2)   # convert the dictionary into JSON and write it to the file


def ask_nonempty(prompt):
    while True:
        value = input(prompt).strip()   # strip removes any leading or trailing spaces from the input
        if value:
            return value                # if the input is not empty, return it
        print("This can't be blank.")   # otherwise keep asking


def ask_yes_no(prompt):
    while True:
        value = input(prompt).strip().lower()   # convert to lowercase so Yes and yes both work
        if value == "yes":
            return True
        if value == "no":
            return False
        print('Please answer "Yes" or "No".')


def login_or_register(db):
    print("===== MEETUP LOGIN =====")
    username = ask_nonempty("Enter your name: ")

    if username in db:                  # check if this user already has an account
        for _ in range(3):              # give them 3 attempts to enter the correct password
            password = ask_nonempty("Enter your password: ")
            if password == db[username]["password"]:
                print(f"Welcome back, {username}!")
                return username
            print("Incorrect password.")

        print("Too many failed attempts. Exiting.")
        sys.exit(1)                     # sys.exit stops the whole program immediately

    print(f"No account found for '{username}'. Creating a new one.")
    password = ask_nonempty("Choose a password: ")
    db[username] = {                    # create a new user entry with all the fields we need
        "password": password,
        "blacklist": [],                # people this user never wants to meet
        "wants_to_meet": [],            # people this user wants to meet
        "open_to_new": False,           # whether they are open to meeting people not on their list
        "availability": [],             # list of time slots when they are free
    }
    save_db(db)
    print(f"Account created for {username}.")
    return username


def ask_blacklist(db, username):
    saved_blacklist = db[username].get("blacklist", [])     # get the existing blacklist, or empty list if none
    if saved_blacklist:
        print(f"Your saved blacklist: {', '.join(saved_blacklist)}")

    response = input(
        "Is there anyone you want to blacklist? "
        "(comma-separated names, or press Enter to keep your current list): "
    ).strip()

    if not response:                    # if the user just pressed Enter, keep the existing blacklist
        return

    names_to_add = []
    for raw_name in response.split(","):        # split the input by commas to get individual names
        clean_name = raw_name.strip()           # remove spaces around each name
        if clean_name:
            names_to_add.append(clean_name)

    updated_blacklist = sorted(set(saved_blacklist) | set(names_to_add))    # combine old and new names, remove duplicates using a set, then sort alphabetically
    db[username]["blacklist"] = updated_blacklist
    print(f"Updated blacklist: {', '.join(updated_blacklist)}")


def ask_wants_to_meet(db, username):
    response = input("Who do you want to meet? (comma-separated names): ").strip()
    names = []

    if response:
        for raw_name in response.split(","):    # split by commas to get individual names
            clean_name = raw_name.strip()       # remove spaces around each name
            if clean_name:
                names.append(clean_name)

    db[username]["wants_to_meet"] = names


def time_to_minutes(time_text):
    hours, minutes = time_text.split(":")      # split "10:30" into "10" and "30"
    return int(hours) * 60 + int(minutes)      # convert to total minutes, e.g. 10:30 becomes 630


def minutes_to_time(total_minutes):
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"    # convert minutes back to HH:MM format, :02d makes sure we always get two digits


def ask_availability(db, username):
    print("\nEnter your availability, one slot per line.")
    print("Format: Day HH:MM HH:MM   (e.g. 'Monday 10:00 12:00')")
    print("Each time slot should be at least 30 minutes long.")
    print("Type 'done' when finished.")

    availability = []

    while True:
        line = input("> ").strip()
        if line.lower() == "done":
            break

        parts = line.split()                    # split the line into its three parts: day, start, end
        if len(parts) != 3:
            print("Invalid format. Example: Monday 10:00 12:00")
            continue

        day, start_text, end_text = parts       # unpack the three parts into separate variables

        try:
            start_minutes = time_to_minutes(start_text)     # convert start time to minutes
            end_minutes = time_to_minutes(end_text)         # convert end time to minutes
        except ValueError:
            print("Invalid time. Use HH:MM (24-hour).")
            continue

        if start_minutes >= end_minutes:
            print("Start time must be before end time.")
            continue

        if end_minutes - start_minutes < MIN_SLOT_MINUTES:
            print("Each availability slot must be at least 30 minutes long.")
            continue

        availability.append({
            "day": day,
            "start": start_text,
            "end": end_text,
        })

    db[username]["availability"] = availability


def ask_open_to_new(db, username):
    db[username]["open_to_new"] = ask_yes_no(
        "Are you open to meeting people not on your list (Yes/No)? "
    )


def build_graph(db):
    graph = {}
    for person in db:
        graph[person] = set()           # every person starts with an empty set of connections

    for person in db:
        wanted_people = db[person].get("wants_to_meet", [])
        for wanted_person in wanted_people:
            if wanted_person in db:                 # only add the connection if that person has an account
                graph[person].add(wanted_person)    # add a directed edge from person to wanted_person

    return graph                        # the graph is a dictionary where each key points to a set of people they want to meet


def can_meet(db, graph, person_a, person_b):
    if person_a == person_b:            # a person cannot meet themselves
        return False

    if person_b in db[person_a].get("blacklist", []):   # if person_b is on person_a's blacklist, they cannot meet
        return False
    if person_a in db[person_b].get("blacklist", []):   # if person_a is on person_b's blacklist, they cannot meet
        return False

    a_wants_b = person_b in graph[person_a]     # check if person_a listed person_b as someone they want to meet
    b_wants_a = person_a in graph[person_b]     # check if person_b listed person_a as someone they want to meet

    if a_wants_b and b_wants_a:                 # if both want to meet each other, they are compatible
        return True
    if a_wants_b and db[person_b].get("open_to_new", False):   # if person_a wants to meet person_b and person_b is open to new people
        return True
    if b_wants_a and db[person_a].get("open_to_new", False):   # if person_b wants to meet person_a and person_a is open to new people
        return True

    return False                        # in all other cases they cannot meet


def get_friends_for_bfs(graph, person):
    friends = set()

    for wanted_person in graph[person]:     # add everyone this person wants to meet
        friends.add(wanted_person)

    for other_person in graph:
        if person in graph[other_person]:   # also add everyone who wants to meet this person
            friends.add(other_person)

    return friends                          # returns everyone connected to this person in either direction


def find_groups(db, graph):
    visited = set()                         # keeps track of people we have already placed into a group
    groups = []

    for start_person in graph:
        if start_person in visited:         # skip people already assigned to a group
            continue

        group = set()
        queue = [start_person]              # start BFS from this person using a regular list as a queue

        while queue:
            person = queue.pop(0)           # take the first person from the front of the queue (BFS behavior)
            if person in visited:
                continue

            visited.add(person)             # mark this person as visited
            group.add(person)               # add them to the current group

            friends = get_friends_for_bfs(graph, person)
            for friend in friends:
                if friend in visited:
                    continue
                if can_meet(db, graph, person, friend):     # only add to queue if they are actually compatible
                    queue.append(friend)

        groups.append(group)                # once BFS is done, save this connected group

    return groups


def availability_to_blocks(availability):
    blocks = set()

    for slot in availability:
        day = slot["day"]
        start_minutes = time_to_minutes(slot["start"])  # convert start time to minutes
        end_minutes = time_to_minutes(slot["end"])      # convert end time to minutes

        for minute in range(start_minutes, end_minutes):    # add every single minute in this slot as a block
            blocks.add((day, minute))                       # each block is a tuple of (day, minute)

    return blocks                           # returns a set of every minute this person is available


def find_common_blocks(db, group):
    group_members = list(group)
    if not group_members:
        return set()

    shared_blocks = availability_to_blocks(db[group_members[0]]["availability"])    # start with the first person's blocks

    for person in group_members[1:]:                                                # go through every other person in the group
        person_blocks = availability_to_blocks(db[person]["availability"])
        shared_blocks &= person_blocks                                              # keep only blocks that exist for both people using set intersection

    return shared_blocks                    # returns only the minutes when everyone in the group is free


def merge_blocks_into_ranges(blocks):
    blocks_by_day = {}
    for day, minute in blocks:
        if day not in blocks_by_day:        # if we haven't seen this day before, create an empty list for it
            blocks_by_day[day] = []
        blocks_by_day[day].append(minute)   # add this minute to that day's list

    time_ranges = []

    for day, minutes in blocks_by_day.items():
        minutes.sort()                      # sort the minutes so we can find consecutive ones
        range_start = minutes[0]            # the start of the current time range
        previous_minute = minutes[0]

        for minute in minutes[1:]:          # go through each minute after the first
            if minute == previous_minute + BLOCK_SIZE:  # if this minute is right after the previous one, they are consecutive
                previous_minute = minute
            else:
                time_ranges.append((day, range_start, previous_minute + BLOCK_SIZE))   # gap found, save the current range
                range_start = minute        # start a new range
                previous_minute = minute

        time_ranges.append((day, range_start, previous_minute + BLOCK_SIZE))   # save the last range for this day

    return time_ranges                      # returns a list of (day, start_minutes, end_minutes) tuples


def all_pairs_compatible(db, graph, people):
    for i in range(len(people)):
        for j in range(i + 1, len(people)):             # check every unique pair without repeating
            if not can_meet(db, graph, people[i], people[j]):
                return False                            # if any pair cannot meet, the whole group is invalid
    return True


def find_largest_meetable_subgroups(db, graph, group):
    members = sorted(group)
    if len(members) < 2:
        return []

    for group_size in range(len(members), 1, -1):      # try from the largest possible group size down to 2
        options = []

        for people_tuple in combinations(members, group_size):  # combinations generates every possible subset of this size
            if not all_pairs_compatible(db, graph, people_tuple):   # check if everyone in this subset can meet each other
                continue

            shared_blocks = find_common_blocks(db, set(people_tuple))  # check if they have any shared availability
            if shared_blocks:
                options.append((set(people_tuple), shared_blocks))      # if both checks pass, this is a valid meeting option

        if options:
            return options              # return as soon as we find the largest valid group size

    return []


def print_results(db, graph, groups):
    print("\n========== PROPOSED MEETINGS ==========")

    if not groups:
        print("No groups could be formed.")
        return

    found_meeting = False

    for group_number, group in enumerate(groups, 1):    # enumerate gives us a counter starting from 1
        print(f"\nConnected group {group_number}: {', '.join(sorted(group))}")

        if len(group) < 2:
            print("  (only one person — no meeting possible)")
            continue

        options = find_largest_meetable_subgroups(db, graph, group)
        if not options:
            print("  No subset of this group has any common availability.")
            continue

        found_meeting = True
        largest_size = len(options[0][0])               # all options have the same size since we return at the largest valid size

        print(f"  Largest possible meeting size: {largest_size} people")
        print(f"  Found {len(options)} option(s) of that size:")

        for option_number, (people, shared_blocks) in enumerate(options, 1):
            print(f"    Option {option_number}: {', '.join(sorted(people))}")
            ranges = merge_blocks_into_ranges(shared_blocks)
            for day, start_minutes, end_minutes in ranges:
                start_time = minutes_to_time(start_minutes)
                end_time = minutes_to_time(end_minutes)
                print(f"      - {day} {start_time} - {end_time}")

    if not found_meeting:
        print("\nNo meetings could be scheduled with the current users.")


def main():
    db = load_db()                          # load all saved user data from the JSON file

    if len(sys.argv) > 1 and sys.argv[1] == "--show":  # sys.argv is the list of command line arguments, sys.argv[1] is the first argument after the filename
        graph = build_graph(db)
        groups = find_groups(db, graph)
        print_results(db, graph, groups)
        return                              # stop here without running the interactive prompts

    username = login_or_register(db)        # log in or create a new account

    print("\n----- BLACKLIST -----")
    ask_blacklist(db, username)

    print("\n----- WHO DO YOU WANT TO MEET -----")
    ask_wants_to_meet(db, username)

    print("\n----- YOUR AVAILABILITY -----")
    ask_availability(db, username)

    print("\n----- OPENNESS -----")
    ask_open_to_new(db, username)

    save_db(db)                             # save all updated user data back to the JSON file

    graph = build_graph(db)                 # build the social graph from all saved user data
    groups = find_groups(db, graph)         # find connected groups of compatible people
    print_results(db, graph, groups)        # print the final meeting suggestions


if __name__ == "__main__":
    main()
