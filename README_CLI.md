# floodWatch2

Describes the actions required ot perform initial loading of floodareas, stations, readings

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run CLI Commands

```bash
export FLASK_APP=app
flask load-station-data
flask load-floodarea-data
```
