# Luke's Media Downloader

## USAGE
I recommend running this in tmux so you can detach the session
```bash
python -m venv .venv
pip install -r requirements.txt
tmux
source .venv/bin/activate
python app.py
```
<br/>
tmux detach: `Ctrl+b d`
tmux attach: `tmux a`
<br/>
<em>This lets you see the console output from the program if something went wrong</em>
<br/>
You may need to run the python script as sudo to get it to save to an external drive.

## Notes
This runs a simple url input page on port 5000 at the IP of the device running the script (e.g., 192.168.1.134:5000)
