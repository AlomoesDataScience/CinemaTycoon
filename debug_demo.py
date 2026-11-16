import subprocess
print(subprocess.run(["python3", "-m", "cinema_tycoon", "--demo", "3"], capture_output=True, text=True).stdout)
