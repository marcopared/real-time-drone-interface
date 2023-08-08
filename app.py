from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles   # Used for serving static files
from fastapi.templating import Jinja2Templates
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import uvicorn
import sys
import pprint
sys.path.append('./rktellolib/src')
from rktellolib import Tello
import time
import re
import asyncio
from threading import Thread

# Data visualization using Plotly Express
import plotly.express as px

from urllib.request import urlopen
import json
import time

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

websocket_manager = ConnectionManager()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

start_time = time.time()
pp = pprint.PrettyPrinter(width=41, compact=True)
positions_dict = {"x": 0, "y": 0, "z": 0, "coordinates": []}
drone = None

def dead_reckoning(x, y, z, vgx, vgy, vgz, time_diff=1):
    x = round(x + vgx * time_diff, 2)
    y = round(y + vgy * time_diff, 2)
    z = round(z + vgz * time_diff, 2)
    return x, y, z

def parse(data):
    match = re.search(r'vgx:(-?\d+);vgy:(-?\d+);vgz:(-?\d+)', data)
    if match:
        vgx, vgy, vgz = map(int, match.groups())
        vgx, vgy, vgz = vgx*-1, vgy*-1, vgz*-1
        current_time = round(time.time() - start_time, 1) # Gets the current time in seconds since the epoch
        # print(f'Time: {current_time}, vgx: {vgx}, vgy: {vgy}, vgz: {vgz}')
        return current_time, vgx, vgy, vgz

def read_saved_data():
    with open("data/saved_raw_data.txt", "r") as f:
        for line in f:
            time.sleep(0.1)
            current_time, vgx, vgy, vgz = parse(line)
            x, y, z = dead_reckoning(positions_dict["x"], positions_dict["y"], positions_dict["z"], vgx, vgy, vgz)
            positions_dict["x"] = x
            positions_dict["y"] = y
            positions_dict["z"] = z
            positions_dict["coordinates"].append((x, y, z))
            print(f'Position: ({x}, {y}, {z})')

# TODO: Test index.html with drone
def read_telemetry(data, save_data=False):
    current_time, vgx, vgy, vgz = parse(data)
    x, y, z = dead_reckoning(positions_dict["x"], positions_dict["y"], positions_dict["z"], vgx, vgy, vgz)
    positions_dict["x"] = x
    positions_dict["y"] = y
    positions_dict["z"] = z
    positions_dict["coordinates"].append((x, y, z))

    if save_data:
        with open('data/saved_raw_data.txt', 'a') as raw_file, open('data/saved_parsed_data.txt', 'a') as parsed_file:
            raw_file.write(data + '\n')
            parsed_file.write(f'Time: {current_time}, Position: ({x}, {y}, {z}), Velocities: ({vgx}, {vgy}, {vgz})\n')


def control_drone(command, v_lr=0, v_fb=0, v_ud=0, v_yaw=0):
    global drone
    if command == "takeoff":
        print("Drone taking off.")
        return drone.takeoff()
    elif command == "land":
        print("Drone landing.")
        return drone.land()
    
    if command == "left":
        v_lr = -30
    elif command == "right":
        v_lr = 30
    elif command == "forward":
        v_fb = 30
    elif command == "back":
        v_fb = -30
    elif command == "up":
        v_ud = 30
    elif command == "down":
        v_ud = -30
    elif command == "ccw":
        v_yaw = 30
    elif command == "cw":
        v_yaw = -30
    
    print(f"Sending RC values to drone v_lr: {v_lr}, v_fb: {v_fb}, v_ud: {v_ud}, v_yaw: {v_yaw}")
    drone.rc(v_lr, v_fb, v_ud, v_yaw)
    time.sleep(1)
    drone.rc(0, 0, 0, 0)
    
def square_pattern(repetitions=1):
    global drone
    for _ in range(repetitions):
        print("Starting square_pattern")
        drone.takeoff()

        drone.forward(100)
        drone.cw(90)
        drone.forward(100)
        drone.cw(90)
        drone.forward(100)
        drone.cw(90)
        drone.forward(100)
        drone.cw(90)

        drone.land()
        drone.disconnect()

# For testing purposes
def plot_coordinates(coordinates):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    xs = [coord[0] for coord in coordinates]
    ys = [coord[1] for coord in coordinates]
    zs = [coord[2] for coord in coordinates]

    ax.plot(xs, ys, zs, 'b-')  # Connects the points with lines

    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')

    plt.show()

@app.on_event("startup")
def startup():
    # sample_thread = Thread(target=read_saved_data)
    # sample_thread.start()

    # Initialize the drone.
    global drone
    drone = Tello(debug=True, has_video=False, state_callback=read_telemetry)
    drone.connect()

    # square_pattern_thread = Thread(target=square_pattern)
    # square_pattern_thread.start()

# TODO: Test websocket with drone
@app.websocket("/ws/controls")
async def websocket_controls_endpoint(websocket: WebSocket):
    await websocket_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            command = json.loads(data)['command']
            # Send the command to the drone.
            print(f"Received command: {command}")
            control_drone(command)
            await websocket.send_text("Command received")
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except KeyboardInterrupt:
        # Perform cleanup here
        await websocket.close()
        print("WebSocket connection closed gracefully")

    except Exception as e:
        print(f"An error occurred: {e}")

@app.websocket("/ws/positions")
async def websocket_positions_endpoint(websocket: WebSocket):
    await websocket_manager.connect(websocket)
    try:
        while True:
            await websocket.send_json(positions_dict)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except KeyboardInterrupt:
        # Perform cleanup here
        await websocket.close()
        print("WebSocket connection closed gracefully")

    except Exception as e:
        print(f"An error occurred: {e}")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/control", response_class=HTMLResponse)
async def get_control(request: Request):
    return templates.TemplateResponse("control.html", {"request": request})

@app.get("/api/drone", response_class=JSONResponse)
async def get_drone_position():
    return {
        "coordinates": positions_dict["coordinates"],
    }
        
@app.on_event("shutdown")
async def shutdown():
    # Safely disconnect the drone when the server is shutting down.
    global drone
    if drone:
        drone.disconnect()

    print(len(positions_dict["coordinates"])) # Expecting 278 lines for text file
    plot_coordinates(positions_dict["coordinates"])


if __name__ == "__main__":
    try:
        print("Running server.")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except KeyboardInterrupt:
        print("Application closed.")
        pp.pprint(positions_dict)


