# cs-32-final-project

Meetup Scheduler

This is a terminal-based tool that helps users find groups they can meet with based on preferences and availability. We decided on this idea because in college, people tend to be very busy, and it is hard to find time to meet their friends, and scheduling is a chore. We hope to create a tool to help students coordinate meetups.

Users can:
- Create an account and log in
- Blacklist people
- Choose who they want to meet
- Enter their availabilities
- Indicate if they are open to meeting new people

Our tool will then find overlapping social connections. Then, our tool will generate an optimal set of people who can meet as a group, as well as propose the date and time for that meeting.

e.g., if A wants to meet B, B wants to meet C, and C wants to meet A, D wants to meet E, E wants to meet D. The system organizes a group meeting for A, B, and C at a mutually available time, and another meeting for D and E at another mutually available time.

How to use:
Run the program by keying python3 meetup.py into the python terminal
The whole interface works in the python terminal

1. Login or Register
- Enter your name
- If you’re new, create a password
- If returning, enter your password (3 attempts)
2. Blacklist
- Enter names of people you do not want to meet
- Press Enter to keep your existing list
3. Who You Want to Meet
- Enter names (comma-separated)
4. Availability
- Format: Day HH:MM HH:MM
- Example: Monday 10:00 12:00
- Type done when finished
5. Open to New People
- Answer Yes or No
6. View Results
- The program prints: connected groups, largest possible meeting groups, all valid time slots

Files:
- meetup.py: main program
- users_db.json: stores user data

Credits:
- We used Codex and Claude to help us with this code. We used the AI to help with architecting the timeslots, and generating test inputs and testing edge cases. 

