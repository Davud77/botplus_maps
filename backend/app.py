import subprocess

scripts = ["login.py", "upload_pano.py", "tms.py", "get_pano.py"]

for script in scripts:
    subprocess.call(["python", script])
