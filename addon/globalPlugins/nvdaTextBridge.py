# -*- coding: UTF-8 -*-
import globalPluginHandler
import speech
import scriptHandler
import ui
import api
import textInfos
import threading
import asyncio
import json
import websockets # External library, ensure it's bundled with the add-on or available in NVDA's environment

# Configuration
HOST = 'localhost'
PORT = 8765

# Set to store connected WebSocket clients
clients = set()
# Lock for thread-safe operations on clients set
clients_lock = threading.Lock()

# WebSocket server task
server_task = None
# Asyncio event loop for the server
loop = None

def get_text_from_speech_sequence(speechSequence):
    """
    Extracts plain text from NVDA's speech sequence.
    A speech sequence can be a list of strings or TextInfos.
    """
    text_parts = []
    for item in speechSequence:
        if isinstance(item, str):
            text_parts.append(item)
        elif isinstance(item, textInfos.TextInfo):
            text_parts.append(item.text)
        # Add handling for other types if necessary
    return "".join(text_parts).strip()

async def broadcast(message):
    """
    Sends a message to all connected WebSocket clients.
    """
    if clients:
        # Create a JSON message
        json_message = json.dumps({"type": "speech", "text": message})
        # Use a copy of the set for iteration as it might change
        current_clients = list(clients)
        tasks = [client.send(json_message) for client in current_clients]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True) # Handle exceptions to prevent one client error from stopping others

async def server_handler(websocket, path):
    """
    Manages new WebSocket connections.
    """
    with clients_lock:
        clients.add(websocket)
    try:
        # Keep the connection alive, listening for any client messages (though we don't expect any for this plugin)
        async for message in websocket:
            # For now, we just log client messages if any, but don't act on them
            print(f"Received message from client (ignoring): {message}")
            pass # We are primarily broadcasting from NVDA to clients
    except websockets.exceptions.ConnectionClosed:
        pass # Connection closed normally
    except Exception as e:
        print(f"WebSocket connection error: {e}")
    finally:
        with clients_lock:
            clients.remove(websocket)

def start_websocket_server():
    """
    Starts the WebSocket server in a new thread.
    """
    global server_task, loop
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        start_server_coro = websockets.serve(server_handler, HOST, PORT)
        server = loop.run_until_complete(start_server_coro)
        
        # ui.message(f"NVDA Text Bridge server started on ws://{HOST}:{PORT}")
        print(f"NVDA Text Bridge WebSocket server started on ws://{HOST}:{PORT}")
        loop.run_forever()
    except OSError as e:
        # ui.message(f"Error starting server (port {PORT} likely in use): {e}")
        print(f"Error starting WebSocket server (port {PORT} likely in use): {e}")
    except Exception as e:
        # ui.message(f"WebSocket server thread error: {e}")
        print(f"WebSocket server thread error: {e}")
    finally:
        if server and hasattr(server, 'close'):
            loop.run_until_complete(server.wait_closed())
        if loop and loop.is_running():
            loop.stop() # Ensure loop stops
        # loop.close() # This can cause issues if called from a running loop's thread. Better to let it be garbage collected or manage carefully.
        print("NVDA Text Bridge WebSocket server stopped.")


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self):
        super(GlobalPlugin, self).__init__()
        self._original_speak = speech.speechFunctions.speak
        speech.speechFunctions.speak = self._hook_speak
        
        self.server_thread = None
        self.start_server()

    def start_server(self):
        if self.server_thread is None or not self.server_thread.is_alive():
            self.server_thread = threading.Thread(target=start_websocket_server, daemon=True)
            self.server_thread.start()
            ui.message("NVDA Text Bridge server starting...")


    def _hook_speak(self, speechSequence, *args, **kwargs):
        """
        Hooks NVDA's speak function to capture text.
        """
        text = get_text_from_speech_sequence(speechSequence)
        if text:
            # print(f"NVDA Spoke: {text}") # For debugging in NVDA Python console
            if loop and clients: # Ensure loop is available and there are clients
                asyncio.run_coroutine_threadsafe(broadcast(text), loop)
        
        # Call the original speak function
        return self._original_speak(speechSequence, *args, **kwargs)

    def terminate(self):
        """
        Called when the add-on is unloaded.
        """
        speech.speechFunctions.speak = self._original_speak # Restore original speak function
        
        global loop, server_task
        if loop:
            # ui.message("Stopping NVDA Text Bridge server...")
            print("Attempting to stop NVDA Text Bridge WebSocket server...")
            # Stop the asyncio event loop
            loop.call_soon_threadsafe(loop.stop)
            
            # Wait for the server thread to finish
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=5) # Wait for 5 seconds
                if self.server_thread.is_alive():
                    print("Server thread did not stop in time.")
        
        ui.message("NVDA Text Bridge stopped.")
        super(GlobalPlugin, self).terminate()

    # Example: Add a script to announce the server status (optional)
    # def script_showServerStatus(self, gesture):
    #     status = "running" if self.server_thread and self.server_thread.is_alive() and loop and loop.is_running() else "stopped"
    #     port_status = f"on ws://{HOST}:{PORT}" if status == "running" else ""
    #     ui.message(f"NVDA Text Bridge server is {status} {port_status}. Clients: {len(clients)}")
    # script_showServerStatus.__doc__ = _("Shows the status of the NVDA Text Bridge WebSocket server.")
    # script_showServerStatus.category = scriptHandler.CATEGORY_TOOLS
    # script_showServerStatus.description = _("Show NVDA Text Bridge server status")
    # __gestures = {
    #     "kb:NVDA+shift+alt+s": "showServerStatus", # Example gesture
    # }
