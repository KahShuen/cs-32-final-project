import json
import os
import sys
from collections import deque
from itertools import combinations



USERS_DB = "users_db.json"


def load_db():
    # read the saved users file and returns empty dictionary if it doesn't exist yet
    if os.path.exists(USERS_DB):
        with open(USERS_DB, "r") as f:
            return json.load(f)
    return {}


def save_db(db):
    with open(USERS_DB, "w") as f:
        json.dump(db, f, indent=2)



def ask_yes_no(prompt):
    # this will only accept yes or no and is case-insensitive
    while True:
        ans = input(prompt).strip().lower()
        if ans == "yes":
            return True
        if ans == "no":
            return False
        print('Please answer "Yes" or "No".')


def ask_nonempty(prompt):
    while True:
        ans = input(prompt).strip()
        if ans:
            return ans
        print("This can't be blank.")


# existing users login while new users will register a new account
def login_or_register(db):
    print("===== MEETUP LOGIN =====")
    name = ask_nonempty("Enter your name: ")

    if name in db:
        # users who have registered before will be asked to key their password with max 3 tries
        for _ in range(3):
            pw = ask_nonempty("Enter your password: ")
            if pw == db[name]["password"]:
                print(f"Welcome back, {name}!")
                return name
            print("Incorrect password.")
        print("Too many failed attempts. Exiting.")
        sys.exit(1)
    else:
        # new users will be asked to create an account and key in their blacklist + open to new ppl preference
        print(f"No account found for '{name}'. Creating a new one.")
        pw = ask_nonempty("Choose a password: ")
        db[name] = {
            "password": pw,
            "blacklist": [],
            "wants_to_meet": [],
            "open_to_new": False,
            "availability": [],
        }
        save_db(db)
        print(f"Account created for {name}.")
        return name



# shows users the current blacklist they have and ask if they want to change the list
def ask_blacklist(db, name):
    # show what we already remember from previous sessions
    current = db[name].get("blacklist", [])
    if current:
        print(f"Your saved blacklist: {', '.join(current)}")

    ans = input(
        "Is there anyone you want to blacklist? "
        "(comma-separated names, or press Enter to keep your current list): "
    ).strip()

    if ans:
        new_names = [n.strip() for n in ans.split(",") if n.strip()]
        # merge with existing blacklist and ensure no duplicates
        merged = sorted(set(current) | set(new_names))
        db[name]["blacklist"] = merged
        print(f"Updated blacklist: {', '.join(merged)}")


def ask_wants_to_meet(db, name):
    ans = input("Who do you want to meet? (comma-separated names): ").strip()
    if ans:
        names = [n.strip() for n in ans.split(",") if n.strip()]
    else:
        names = []
    db[name]["wants_to_meet"] = names


def ask_availability(db, name):
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
        day, start, end = parts
        # quick sanity check that the times parse
        try:
            s = time_to_minutes(start)
            e = time_to_minutes(end)
        except ValueError:
            print("Invalid time. Use HH:MM (24-hour).")
            continue
        if s >= e:
            print("Start time must be before end time.")
            continue
        if e - s < 30:
            print("Each availability slot must be at least 30 minutes long.")
            continue
        availability.append({"day": day, "start": start, "end": end})

    db[name]["availability"] = availability


def ask_open(db, name):
    db[name]["open_to_new"] = ask_yes_no(
        "Are you open to meeting people not on your list (Yes/No)? "
    )


# building the directed graph, meaning if A wants to meet B, A -> B, it shld return something like {"Alice": {"Bob"}, "Bob": {"Charlie"}, ...}
def build_graph(db):
    
    graph = {name: set() for name in db}
    for name, data in db.items():
        for target in data.get("wants_to_meet", []):
            if target in db:  # only add edges to people who actually have an account
                graph[name].add(target)
    return graph

# checking the open to new ppl and blacklist conditions before creating the possible grpings
def can_meet(db, graph, a, b):
    """Decide if A and B are allowed to be in the same group.

    Rules (consistent with the directed graph):
      - If either has the other in their blacklist -> NO.
      - If both want to meet each other (A->B AND B->A) -> YES.
      - If only A->B exists, B must be open_to_new.
      - If only B->A exists, A must be open_to_new.
    """
    if a == b:
        return False
    if b in db[a].get("blacklist", []):
        return False
    if a in db[b].get("blacklist", []):
        return False

    a_wants_b = b in graph[a]
    b_wants_a = a in graph[b]

    if a_wants_b and b_wants_a:
        return True
    if a_wants_b and db[b].get("open_to_new", False):
        return True
    if b_wants_a and db[a].get("open_to_new", False):
        return True
    return False


def find_groups(db, graph):
    """BFS to find connected components in the COMPATIBILITY relation.

    The graph is directed (from build_graph), but two people end up in the
    same component only if can_meet(...) is true between them, which already
    accounts for direction + open_to_new + blacklist.
    """
    visited = set()
    groups = []

    for start in graph:
        if start in visited:
            continue

        component = set()
        queue = deque([start])

        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            component.add(node)

            # candidates = people node points to or people who point to node
            candidates = set(graph[node])
            for other in graph:
                if node in graph[other]:
                    candidates.add(other)

            for neighbor in candidates:
                if neighbor not in visited and can_meet(db, graph, node, neighbor):
                    queue.append(neighbor)

        groups.append(component)

    return groups


# ---------- availability blocks ----------

# Use 1-minute blocks so overlaps are as precise as possible.
# Example: 07:15-08:30 and 07:20-08:00 intersect exactly at 07:20-08:00.
BLOCK = 1


def time_to_minutes(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def minutes_to_time(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def availability_to_blocks(availability):
    """Turn a person's availability into a set of (day, start_minute) blocks.

    A block is only included if it lies fully inside one of the free windows,
    so partial blocks at the edges are dropped (which is what we want).
    """
    blocks = set()
    for slot in availability:
        day = slot["day"]
        start = time_to_minutes(slot["start"])
        end = time_to_minutes(slot["end"])
        # round start UP to the next block boundary, end DOWN to the previous
        first = ((start + BLOCK - 1) // BLOCK) * BLOCK
        last = (end // BLOCK) * BLOCK
        for m in range(first, last, BLOCK):
            blocks.add((day, m))
    return blocks


def common_blocks(db, group):
    members = list(group)
    if not members:
        return set()
    common = availability_to_blocks(db[members[0]]["availability"])
    for member in members[1:]:
        common &= availability_to_blocks(db[member]["availability"])
    return common


def merge_blocks_into_ranges(blocks):
    """Group adjacent blocks back into readable (day, start, end) windows."""
    by_day = {}
    for day, minute in blocks:
        by_day.setdefault(day, []).append(minute)

    ranges = []
    for day, minutes in by_day.items():
        minutes.sort()
        run_start = minutes[0]
        prev = minutes[0]
        for m in minutes[1:]:
            if m == prev + BLOCK:
                prev = m
            else:
                ranges.append((day, run_start, prev + BLOCK))
                run_start = m
                prev = m
        ranges.append((day, run_start, prev + BLOCK))
    return ranges


# ---------- finding the BIGGEST meetable subgroups ----------

def all_pairs_compatible(db, graph, combo):
    # A BFS component can contain pairs that aren't directly compatible
    # (e.g. two people who both connect to Alice but not to each other, or
    # a blacklisted pair). Before proposing a meeting we must check every
    # pair individually.
    for i in range(len(combo)):
        for j in range(i + 1, len(combo)):
            if not can_meet(db, graph, combo[i], combo[j]):
                return False
    return True


def find_largest_meetable_subgroups(db, graph, component):
    """Inside one connected component, find every subset of the largest
    possible size such that:
      - every pair in the subset is compatible (blacklist / openness respected)
      - AND the subset shares at least one common time block.

    Returns a list of (set_of_names, set_of_common_blocks).
    A meeting needs at least 2 people.
    """
    members = sorted(component)
    n = len(members)
    if n < 2:
        return []

    # Try the biggest possible group first; if no subset of that size works,
    # drop down by one and try again.
    for size in range(n, 1, -1):
        results = []
        for combo in combinations(members, size):
            if not all_pairs_compatible(db, graph, combo):
                continue
            blocks = common_blocks(db, set(combo))
            if blocks:
                results.append((set(combo), blocks))
        if results:
            return results
    return []


# ---------- output ----------

def format_output(db, graph, groups):
    print("\n========== PROPOSED MEETINGS ==========")

    if not groups:
        print("No groups could be formed.")
        return

    any_meeting = False
    for i, group in enumerate(groups, 1):
        print(f"\nConnected group {i}: {', '.join(sorted(group))}")

        if len(group) < 2:
            print("  (only one person — no meeting possible)")
            continue

        meetable = find_largest_meetable_subgroups(db, graph, group)
        if not meetable:
            print("  No subset of this group has any common availability.")
            continue

        any_meeting = True
        size = len(meetable[0][0])
        print(f"  Largest possible meeting size: {size} people")
        print(f"  Found {len(meetable)} option(s) of that size:")
        for j, (people, blocks) in enumerate(meetable, 1):
            print(f"    Option {j}: {', '.join(sorted(people))}")
            for day, start, end in merge_blocks_into_ranges(blocks):
                print(f"      - {day} {minutes_to_time(start)} - {minutes_to_time(end)}")

    if not any_meeting:
        print("\nNo meetings could be scheduled with the current users.")


# ---------- main ----------

def main():
    db = load_db()

    # "--show" lets you view current proposed meetings without logging in
    # or changing anything. Handy for inspecting the preloaded sample data.
    if len(sys.argv) > 1 and sys.argv[1] == "--show":
        graph = build_graph(db)
        groups = find_groups(db, graph)
        format_output(db, graph, groups)
        return

    name = login_or_register(db)

    print("\n----- BLACKLIST -----")
    ask_blacklist(db, name)

    print("\n----- WHO DO YOU WANT TO MEET -----")
    ask_wants_to_meet(db, name)

    print("\n----- YOUR AVAILABILITY -----")
    ask_availability(db, name)

    print("\n----- OPENNESS -----")
    ask_open(db, name)

    save_db(db)

    graph = build_graph(db)
    groups = find_groups(db, graph)
    format_output(db, graph, groups)


if __name__ == "__main__":
    main()
