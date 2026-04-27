import os
import sys
import subprocess

def get_python_path():
    return sys.executable

def get_project_path():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def manage_cron(action):
    project_path = get_project_path()
    python_path = get_python_path()
    log_path = os.path.join(project_path, "logs", "cron.log")
    
    # Cron command: Run every weekday at 21:50 (10 mins before NY close)
    # 50 21 * * 1-5
    cron_command = f"50 21 * * 1-5 cd {project_path} && {python_path} control.py rebalance --live >> {log_path} 2>&1"
    
    # Read existing crontab
    try:
        current_cron = subprocess.check_output("crontab -l", shell=True, stderr=subprocess.STDOUT).decode()
    except subprocess.CalledProcessError:
        current_cron = ""

    lines = current_cron.splitlines()
    
    if action == "add":
        if any(project_path in line for line in lines if "control.py" in line):
            print("Error: A cron job for this project already exists.")
            return
        
        lines.append(cron_command)
        print(f"Adding to crontab: {cron_command}")
        
    elif action == "remove":
        new_lines = [line for line in lines if not (project_path in line and "control.py" in line)]
        if len(new_lines) == len(lines):
            print("No existing cron job found for this project.")
            return
        lines = new_lines
        print(f"Removing cron job for project at {project_path}")

    # Write back to crontab
    new_cron = "\n".join(lines) + "\n"
    process = subprocess.Popen("crontab -", stdin=subprocess.PIPE, shell=True)
    process.communicate(input=new_cron.encode())
    
    print("Crontab updated successfully.")

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ["add", "remove"]:
        print("Usage: python scripts/manage_cron.py [add|remove]")
        sys.exit(1)
        
    manage_cron(sys.argv[1])
