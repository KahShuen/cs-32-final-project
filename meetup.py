import json                        
import os                           # lets us check if a file exists on the computer
import sys                          
from itertools import combinations  # lets us generate every possible subset of a group

USERS_DB = "users_db.json"         
MIN_SLOT_MINUTES = 30               
BLOCK_SIZE = 1                      
DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
VALID_DAYS = set(DAY_ORDER)
FULL_SEARCH_GROUP_LIMIT = 14
CAPPED_SEARCH_MAX_SIZE = 5


def normalize_name(name_text):
    return name_text.strip().lower()


def parse_names_csv(text):
    names = []
    for raw_name in text.split(","):
        clean_name = normalize_name(raw_name)
        if clean_name:
            names.append(clean_name)
    return names


def parse_time_to_minutes(time_text):
    parts = time_text.split(":")
    if len(parts) != 2:
        raise ValueError("Time must use HH:MM.")

    hours_text, minutes_text = parts
    if (not hours_text.isdigit()) or (not minutes_text.isdigit()):
        raise ValueError("Time must contain only numbers.")

    hours = int(hours_text)
    minutes = int(minutes_text)
    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
        raise ValueError("Time is out of range.")

    return hours * 60 + minutes


def normalize_db(db):
    normalized = {}

    for raw_username, raw_data in db.items():
        username = normalize_name(raw_username)
        if not username:
            continue

        if username not in normalized:
            normalized[username] = {
                "password": str(raw_data.get("password", "")),
                "blacklist": [],
                "wants_to_meet": [],
                "open_to_new": bool(raw_data.get("open_to_new", False)),
                "availability": [],
            }

        user = normalized[username]
        blacklist = raw_data.get("blacklist", [])
        wants_to_meet = raw_data.get("wants_to_meet", [])
        availability = raw_data.get("availability", [])

        user["blacklist"].extend([normalize_name(name) for name in blacklist if normalize_name(name)])
        user["wants_to_meet"].extend([normalize_name(name) for name in wants_to_meet if normalize_name(name)])
        user["open_to_new"] = user["open_to_new"] or bool(raw_data.get("open_to_new", False))

        for slot in availability:
            day = normalize_name(slot.get("day", ""))
            start = str(slot.get("start", "")).strip()
            end = str(slot.get("end", "")).strip()
            if day not in VALID_DAYS:
                continue
            try:
                start_minutes = parse_time_to_minutes(start)
                end_minutes = parse_time_to_minutes(end)
            except ValueError:
                continue
            if end_minutes - start_minutes < MIN_SLOT_MINUTES:
                continue
            user["availability"].append({"day": day, "start": start, "end": end})

        user["blacklist"] = sorted(set([name for name in user["blacklist"] if name != username]))
        user["wants_to_meet"] = sorted(set([name for name in user["wants_to_meet"] if name != username]))

    return normalized



def load_db():
    if os.path.exists(USERS_DB):    # os.path.exists checks if the file already exists on disk
        with open(USERS_DB, "r") as file:
            raw_db = json.load(file)  # read the JSON file and convert it into a python dictionary
            return normalize_db(raw_db)
    return {}                         # if the file doesn't exist yet, start with an empty dictionary


def save_db(db):
    with open(USERS_DB, "w") as file:
        json.dump(db, file, indent=2)   # convert the dictionary into JSON and write it to the file


def ask_nonempty(prompt):
    while True:
        value = input(prompt).strip()   # strip removes any leading or trailing spaces from the input
        if value:
            return value                # if the input is not empty, return it
        print("This can't be blank.")   # otherwise keep asking

# for open to meet new prompt later
def ask_yes_no(prompt):
    while True:
        value = input(prompt).strip().lower()   # convert to lowercase so it isn't case sensitive
        if value in ("yes", "y"):
            return True
        if value in ("no", "n"):
            return False
        print('Please answer "yes" or "no".')


def login_or_register(db):
    username = normalize_name(ask_nonempty("Name: "))

    if username in db:                  # check if this user already has an account
        for _ in range(3):              # we give them 3 attempts to enter the correct password
            password = ask_nonempty("Password: ")
            if password == db[username]["password"]:
                print(f"Welcome back, {username}.")
                return username, True
            print("Incorrect password.")

        print("Too many failed attempts.")
        sys.exit(1)                     # stops the whole program immediately

    print(f"Creating account for {username}.")
    password = ask_nonempty("Choose password: ")
    db[username] = {                    # create a new user entry with all the fields we need
        "password": password,
        "blacklist": [],                # people the user never wants to meet
        "wants_to_meet": [],            # people the user wants to meet
        "open_to_new": False,           # whether they are open to meeting people not on their list
        "availability": [],             # list of time slots when they are free
    }
    save_db(db)
    print("Account created.")
    return username, False


def ask_blacklist(db, username):
    saved_blacklist = db[username].get("blacklist", [])     # get the existing blacklist, or empty list if none
    if saved_blacklist:
        print(f"Current blacklist: {', '.join(saved_blacklist)}")
    else:
        print("Current blacklist: (empty)")

    action = input("Type 'add', 'remove', or Enter to keep current: ").strip().lower()
    if not action:
        return

    if action == "add":
        response = input("Add to blacklist (comma names): ").strip()
        if not response:
            return
        names_to_add = parse_names_csv(response)
        updated_blacklist = sorted(set(saved_blacklist) | set(names_to_add))
        updated_blacklist = [name for name in updated_blacklist if name != username]
        db[username]["blacklist"] = updated_blacklist
        return

    if action == "remove":
        response = input("Remove from blacklist (comma names): ").strip()
        if not response:
            return
        names_to_remove = set(parse_names_csv(response))
        updated_blacklist = [name for name in saved_blacklist if name not in names_to_remove]
        db[username]["blacklist"] = sorted(updated_blacklist)
        return

    print("Invalid choice. Keeping current blacklist.")


def ask_wants_to_meet(db, username):
    response = input("People you want to meet (comma names): ").strip()
    names = parse_names_csv(response) if response else []
    names = [name for name in names if name != username]
    db[username]["wants_to_meet"] = names


def ask_add_wants_to_meet(db, username):
    saved_wants = db[username].get("wants_to_meet", [])
    response = input("Add people you want to meet (comma names): ").strip()
    if not response:
        return

    names_to_add = parse_names_csv(response)
    updated_wants = sorted(set(saved_wants) | set(names_to_add))
    updated_wants = [name for name in updated_wants if name != username]
    db[username]["wants_to_meet"] = updated_wants


def ask_remove_wants_to_meet(db, username):
    saved_wants = db[username].get("wants_to_meet", [])
    if saved_wants:
        print(f"Current want-to-meet list: {', '.join(saved_wants)}")
    else:
        print("Current want-to-meet list: (empty)")
        return

    response = input("Remove people from want-to-meet list (comma names): ").strip()
    if not response:
        return

    names_to_remove = set(parse_names_csv(response))
    updated_wants = [name for name in saved_wants if name not in names_to_remove]
    db[username]["wants_to_meet"] = sorted(updated_wants)


def ask_returning_user_action():
    print("\nChoose an action:")
    print("1) Edit blacklist (add/remove)")
    print("2) Add people to want-to-meet list")
    print("3) Remove people from want-to-meet list")
    print("4) Change availability")
    print("5) Change openness to meeting new people")
    print("6) Exit")

    while True:
        choice = input("Enter 1, 2, 3, 4, 5, or 6: ").strip()
        if choice in ("1", "2", "3", "4", "5", "6"):
            return choice
        print("Invalid choice. Please enter 1, 2, 3, 4, 5, or 6.")


def time_to_minutes(time_text):
    return parse_time_to_minutes(time_text)


def minutes_to_time(total_minutes):
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"    # convert minutes back to HH:MM format, :02d makes sure we always get two digits


def ask_availability(db, username):
    print("\nAvailability format: Day HH:MM HH:MM (type 'done' to finish)")

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

        day = normalize_name(day)
        if day not in VALID_DAYS:
            print("Invalid day. Use Monday-Sunday.")
            continue

        try:
            start_minutes = parse_time_to_minutes(start_text)
            end_minutes = parse_time_to_minutes(end_text)
        except ValueError:
            print("Invalid time. Use HH:MM in 24-hour format.")
            continue

        if start_minutes >= end_minutes:
            print("Start time must be before end time.")
            continue

        if end_minutes - start_minutes < MIN_SLOT_MINUTES:
            print("Each availability slot must be at least 30 minutes long.")
            continue

        availability.append({
            "day": day,
            "start": minutes_to_time(start_minutes),
            "end": minutes_to_time(end_minutes),
        })

    db[username]["availability"] = availability


def ask_open_to_new(db, username):
    db[username]["open_to_new"] = ask_yes_no(
        "Open to meeting people not on your list? (yes/no): "
    )


def build_graph(db):
    graph = {}
    reverse_graph = {}
    for person in db:
        graph[person] = set()           # every person starts with an empty set of connections
        reverse_graph[person] = set()   # keep incoming edges so BFS neighbor lookup is fast

    for person in db:
        wanted_people = db[person].get("wants_to_meet", [])
        for wanted_person in wanted_people:
            if wanted_person in db:                 # only add the connection if that person has an account
                graph[person].add(wanted_person)    # add a directed edge from person to wanted_person
                reverse_graph[wanted_person].add(person)

    return graph, reverse_graph


def can_meet(db, graph, person_a, person_b):
    if person_a == person_b:            # a person cannot meet themselves
        return False

    if person_b in db[person_a].get("blacklist", []):   # if person b is on person a's blacklist, they cannot meet
        return False
    if person_a in db[person_b].get("blacklist", []):   # if person a is on person b's blacklist, they cannot meet
        return False

    a_wants_b = person_b in graph[person_a]     # check if person a listed person b as someone they want to meet
    b_wants_a = person_a in graph[person_b]     # check if person b listed person a as someone they want to meet

    if a_wants_b and b_wants_a:                 # if both want to meet each other, they are compatible!
        return True
    if a_wants_b and db[person_b].get("open_to_new", False):   # if person a wants to meet person b and person b is open to new people
        return True
    if b_wants_a and db[person_a].get("open_to_new", False):   # if person b wants to meet person a and person a is open to new people
        return True

    return False                        # in all other cases they cannot meet


def get_friends_for_bfs(graph, reverse_graph, person):
    friends = set(graph[person])
    friends |= reverse_graph[person]
    return friends                          # returns everyone connected to this person in either direction


def find_groups(db, graph, reverse_graph):
    visited = set()                         # keeps track of people we have already placed into a group
    groups = []

    for start_person in graph:
        if start_person in visited:         # skip people already assigned to a group
            continue

        group = set()
        queue = [start_person]              # start BFS from this person using a regular list as a queue
        queue_index = 0

        while queue_index < len(queue):
            person = queue[queue_index]
            queue_index += 1
            if person in visited:
                continue

            visited.add(person)             # mark this person as visited
            group.add(person)               # add them to the current group

            friends = get_friends_for_bfs(graph, reverse_graph, person)
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

    sorted_days = sorted(blocks_by_day.keys(), key=lambda day_name: DAY_ORDER.index(day_name))
    for day in sorted_days:
        minutes = blocks_by_day[day]
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
    members = [person for person in sorted(group) if db[person].get("availability")]
    if len(members) < 2:
        return [], False

    search_max_size = len(members)
    was_capped = False
    if len(members) > FULL_SEARCH_GROUP_LIMIT:
        search_max_size = min(search_max_size, CAPPED_SEARCH_MAX_SIZE)
        was_capped = True

    for group_size in range(search_max_size, 1, -1):      # try from the largest possible group size down to 2
        options = []

        for people_tuple in combinations(members, group_size):  # combinations generates every possible subset of this size
            if not all_pairs_compatible(db, graph, people_tuple):   # check if everyone in this subset can meet each other
                continue

            shared_blocks = find_common_blocks(db, set(people_tuple))  # check if they have any shared availability
            if shared_blocks:
                options.append((set(people_tuple), shared_blocks))      # if both checks pass, this is a valid meeting option

        if options:
            return options, was_capped              # return as soon as we find the largest valid group size

    return [], was_capped


def print_results(db, graph, groups):
    print("\nMeeting options:")
    found_meeting = False
    option_number = 1

    for group in groups:
        if len(group) < 2:
            continue

        options, was_capped = find_largest_meetable_subgroups(db, graph, group)
        if not options:
            continue

        found_meeting = True
        if was_capped:
            print(
                f"\nNote: group has {len(group)} people; search was capped at size {CAPPED_SEARCH_MAX_SIZE} for speed."
            )
        for people, shared_blocks in options:
            print(f"\nOption {option_number}: {', '.join(sorted(people))}")
            ranges = merge_blocks_into_ranges(shared_blocks)
            for day, start_minutes, end_minutes in ranges:
                start_time = minutes_to_time(start_minutes)
                end_time = minutes_to_time(end_minutes)
                print(f"- {day.capitalize()} {start_time} - {end_time}")
            option_number += 1

    if not found_meeting:
        print("No meetings can be scheduled with current data.")


def main():
    db = load_db()                          # load all saved user data from the JSON file

    if len(sys.argv) > 1 and sys.argv[1] == "--show":  # sys.argv is the list of command line arguments, sys.argv[1] is the first argument after the filename
        graph, reverse_graph = build_graph(db)
        groups = find_groups(db, graph, reverse_graph)
        print_results(db, graph, groups)
        return                              # stop here without running the interactive prompts

    username, is_returning_user = login_or_register(db)        # log in or create a new account

    if is_returning_user and db[username].get("availability"):
        graph, reverse_graph = build_graph(db)
        groups = find_groups(db, graph, reverse_graph)
        print_results(db, graph, groups)

        while True:
            action = ask_returning_user_action()
            if action == "1":
                ask_blacklist(db, username)
            elif action == "2":
                ask_add_wants_to_meet(db, username)
            elif action == "3":
                ask_remove_wants_to_meet(db, username)
            elif action == "4":
                ask_availability(db, username)
            elif action == "5":
                ask_open_to_new(db, username)
            else:
                save_db(db)
                print("Exited.")
                return

            save_db(db)
            graph, reverse_graph = build_graph(db)
            groups = find_groups(db, graph, reverse_graph)
            print_results(db, graph, groups)

    ask_blacklist(db, username)

    ask_wants_to_meet(db, username)

    ask_availability(db, username)

    ask_open_to_new(db, username)

    save_db(db)                             # save all updated user data back to the JSON file

    graph, reverse_graph = build_graph(db)  # build the social graph from all saved user data
    groups = find_groups(db, graph, reverse_graph)         # find connected groups of compatible people
    print_results(db, graph, groups)        # print the final meeting suggestions


if __name__ == "__main__":
    main()
