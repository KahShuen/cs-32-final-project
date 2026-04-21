import json
import os
import sys
from collections import deque
from itertools import combinations

USERS_DB = "users_db.json"
MIN_SLOT_MINUTES = 30
BLOCK_SIZE = 1  # minute-level precision


def load_db():
    if os.path.exists(USERS_DB):
        with open(USERS_DB, "r") as file:
            return json.load(file)
    return {}


def save_db(db):
    with open(USERS_DB, "w") as file:
        json.dump(db, file, indent=2)


def ask_nonempty(prompt):
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("This can't be blank.")


def ask_yes_no(prompt):
    while True:
        value = input(prompt).strip().lower()
        if value == "yes":
            return True
        if value == "no":
            return False
        print('Please answer "Yes" or "No".')


def login_or_register(db):
    print("===== MEETUP LOGIN =====")
    username = ask_nonempty("Enter your name: ")

    if username in db:
        for _ in range(3):
            password = ask_nonempty("Enter your password: ")
            if password == db[username]["password"]:
                print(f"Welcome back, {username}!")
                return username
            print("Incorrect password.")

        print("Too many failed attempts. Exiting.")
        sys.exit(1)

    print(f"No account found for '{username}'. Creating a new one.")
    password = ask_nonempty("Choose a password: ")
    db[username] = {
        "password": password,
        "blacklist": [],
        "wants_to_meet": [],
        "open_to_new": False,
        "availability": [],
    }
    save_db(db)
    print(f"Account created for {username}.")
    return username


def ask_blacklist(db, username):
    saved_blacklist = db[username].get("blacklist", [])
    if saved_blacklist:
        print(f"Your saved blacklist: {', '.join(saved_blacklist)}")

    response = input(
        "Is there anyone you want to blacklist? "
        "(comma-separated names, or press Enter to keep your current list): "
    ).strip()

    if not response:
        return

    names_to_add = []
    for raw_name in response.split(","):
        clean_name = raw_name.strip()
        if clean_name:
            names_to_add.append(clean_name)

    updated_blacklist = sorted(set(saved_blacklist) | set(names_to_add))
    db[username]["blacklist"] = updated_blacklist
    print(f"Updated blacklist: {', '.join(updated_blacklist)}")


def ask_wants_to_meet(db, username):
    response = input("Who do you want to meet? (comma-separated names): ").strip()
    names = []

    if response:
        for raw_name in response.split(","):
            clean_name = raw_name.strip()
            if clean_name:
                names.append(clean_name)

    db[username]["wants_to_meet"] = names


def time_to_minutes(time_text):
    hours, minutes = time_text.split(":")
    return int(hours) * 60 + int(minutes)


def minutes_to_time(total_minutes):
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


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

        parts = line.split()
        if len(parts) != 3:
            print("Invalid format. Example: Monday 10:00 12:00")
            continue

        day, start_text, end_text = parts

        try:
            start_minutes = time_to_minutes(start_text)
            end_minutes = time_to_minutes(end_text)
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
        graph[person] = set()

    for person in db:
        wanted_people = db[person].get("wants_to_meet", [])
        for wanted_person in wanted_people:
            if wanted_person in db:
                graph[person].add(wanted_person)

    return graph


def can_meet(db, graph, person_a, person_b):
    if person_a == person_b:
        return False

    if person_b in db[person_a].get("blacklist", []):
        return False
    if person_a in db[person_b].get("blacklist", []):
        return False

    a_wants_b = person_b in graph[person_a]
    b_wants_a = person_a in graph[person_b]

    if a_wants_b and b_wants_a:
        return True
    if a_wants_b and db[person_b].get("open_to_new", False):
        return True
    if b_wants_a and db[person_a].get("open_to_new", False):
        return True

    return False


def get_friends_for_bfs(graph, person):
    friends = set()

    for wanted_person in graph[person]:
        friends.add(wanted_person)

    for other_person in graph:
        if person in graph[other_person]:
            friends.add(other_person)

    return friends


def find_groups(db, graph):
    visited = set()
    groups = []

    for start_person in graph:
        if start_person in visited:
            continue

        group = set()
        queue = deque([start_person])

        while queue:
            person = queue.popleft()
            if person in visited:
                continue

            visited.add(person)
            group.add(person)

            friends = get_friends_for_bfs(graph, person)
            for friend in friends:
                if friend in visited:
                    continue
                if can_meet(db, graph, person, friend):
                    queue.append(friend)

        groups.append(group)

    return groups


def availability_to_blocks(availability):
    blocks = set()

    for slot in availability:
        day = slot["day"]
        start_minutes = time_to_minutes(slot["start"])
        end_minutes = time_to_minutes(slot["end"])

        first_block = ((start_minutes + BLOCK_SIZE - 1) // BLOCK_SIZE) * BLOCK_SIZE
        last_block = (end_minutes // BLOCK_SIZE) * BLOCK_SIZE

        for minute in range(first_block, last_block, BLOCK_SIZE):
            blocks.add((day, minute))

    return blocks


def find_common_blocks(db, group):
    group_members = list(group)
    if not group_members:
        return set()

    shared_blocks = availability_to_blocks(db[group_members[0]]["availability"])

    for person in group_members[1:]:
        person_blocks = availability_to_blocks(db[person]["availability"])
        shared_blocks &= person_blocks

    return shared_blocks


def merge_blocks_into_ranges(blocks):
    blocks_by_day = {}
    for day, minute in blocks:
        blocks_by_day.setdefault(day, []).append(minute)

    time_ranges = []

    for day, minutes in blocks_by_day.items():
        minutes.sort()
        range_start = minutes[0]
        previous_minute = minutes[0]

        for minute in minutes[1:]:
            if minute == previous_minute + BLOCK_SIZE:
                previous_minute = minute
            else:
                time_ranges.append((day, range_start, previous_minute + BLOCK_SIZE))
                range_start = minute
                previous_minute = minute

        time_ranges.append((day, range_start, previous_minute + BLOCK_SIZE))

    return time_ranges


def all_pairs_compatible(db, graph, people):
    for i in range(len(people)):
        for j in range(i + 1, len(people)):
            if not can_meet(db, graph, people[i], people[j]):
                return False
    return True


def find_largest_meetable_subgroups(db, graph, group):
    members = sorted(group)
    if len(members) < 2:
        return []

    for group_size in range(len(members), 1, -1):
        options = []

        for people_tuple in combinations(members, group_size):
            if not all_pairs_compatible(db, graph, people_tuple):
                continue

            shared_blocks = find_common_blocks(db, set(people_tuple))
            if shared_blocks:
                options.append((set(people_tuple), shared_blocks))

        if options:
            return options

    return []


def print_results(db, graph, groups):
    print("\n========== PROPOSED MEETINGS ==========")

    if not groups:
        print("No groups could be formed.")
        return

    found_meeting = False

    for group_number, group in enumerate(groups, 1):
        print(f"\nConnected group {group_number}: {', '.join(sorted(group))}")

        if len(group) < 2:
            print("  (only one person — no meeting possible)")
            continue

        options = find_largest_meetable_subgroups(db, graph, group)
        if not options:
            print("  No subset of this group has any common availability.")
            continue

        found_meeting = True
        largest_size = len(options[0][0])

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
    db = load_db()

    if len(sys.argv) > 1 and sys.argv[1] == "--show":
        graph = build_graph(db)
        groups = find_groups(db, graph)
        print_results(db, graph, groups)
        return

    username = login_or_register(db)

    print("\n----- BLACKLIST -----")
    ask_blacklist(db, username)

    print("\n----- WHO DO YOU WANT TO MEET -----")
    ask_wants_to_meet(db, username)

    print("\n----- YOUR AVAILABILITY -----")
    ask_availability(db, username)

    print("\n----- OPENNESS -----")
    ask_open_to_new(db, username)

    save_db(db)

    graph = build_graph(db)
    groups = find_groups(db, graph)
    print_results(db, graph, groups)


if __name__ == "__main__":
    main()
