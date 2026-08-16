with open("main.py", "r") as f:
    c = f.read()

c = c.replace(
'''"<b>Step 6/8:</b> Type 2 to 4 of your <b>Interests & Hobbies</b> separated by commas.

"''',
'"<b>Step 6/8:</b> Type 2 to 4 of your <b>Interests & Hobbies</b> separated by commas.\\n\\n"'
)

c = c.replace(
'''f"<b>Step 7/8:</b> Write a short <b>Bio</b> about yourself.

"''',
'f"<b>Step 7/8:</b> Write a short <b>Bio</b> about yourself.\\n\\n"'
)

c = c.replace(
'''f"<b>Step 8/8:</b> Upload a <b>Real Photo</b> of yourself!

"''',
'f"<b>Step 8/8:</b> Upload a <b>Real Photo</b> of yourself!\\n\\n"'
)

c = c.replace(
'''f"<b>Profile Created Successfully</b>

"''',
'f"<b>Profile Created Successfully</b>\\n\\n"'
)

with open("main.py", "w") as f:
    f.write(c)
