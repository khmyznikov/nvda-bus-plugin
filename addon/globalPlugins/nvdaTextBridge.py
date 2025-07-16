import globalPluginHandler
from speech.extensions import pre_speechQueued  # Import the event
from logHandler import log
import asyncio
import threading
import sys
import os

# Add the lib directory to the path so we can import the websockets module
addon_dir = os.path.dirname(os.path.dirname(__file__))
lib_path = os.path.join(addon_dir, "lib")
sys.path.append(lib_path)

import websockets

class WebSocketServer:
    def __init__(self, host='127.0.0.1', port=8765):
        self.host = host
        self.port = port
        self.clients = set()
        self.server = None
        self.loop = None
        self.thread = None
        self.running = False

    async def ws_handler(self, websocket):
        """Handle client connections"""
        self.clients.add(websocket)
        try:
            log.info(f"NVDA Text Bridge: WebSocket client connected: {websocket.remote_address}")
            # Keep connection alive until client disconnects
            await websocket.wait_closed()
        finally:
            self.clients.remove(websocket)
            log.info(f"NVDA Text Bridge: WebSocket client disconnected: {websocket.remote_address}")

    async def broadcast(self, message):
        """Send message to all connected clients"""
        if not self.clients:
            return
            
        # Create tasks for sending to each client
        tasks = [client.send(message) for client in self.clients.copy()]
        if tasks:
            # Run all tasks concurrently and gather results
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Check for exceptions
            for client, result in zip(self.clients.copy(), results):
                if isinstance(result, Exception):
                    log.error(f"NVDA Text Bridge: Error sending to client {client.remote_address}: {result}")
                    # Client might be disconnected, try to remove it
                    try:
                        self.clients.remove(client)
                        await client.close()
                    except:
                        pass

    def send_message(self, message):
        """Send message from outside the event loop"""
        if self.loop and self.running:
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)

    async def start_server(self):
        """Start the WebSocket server"""
        self.server = await websockets.serve(
            self.ws_handler, self.host, self.port
        )
        log.info(f"NVDA Text Bridge: WebSocket server started on {self.host}:{self.port}")
        self.running = True
        # Keep the server running
        await self.server.wait_closed()

    def run_server(self):
        """Run the server in a new event loop"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.start_server())
        except Exception as e:
            log.error(f"NVDA Text Bridge: WebSocket server error: {e}")
        finally:
            self.running = False
            self.loop.close()

    def start(self):
        """Start the server in a background thread"""
        self.thread = threading.Thread(target=self.run_server, daemon=True)
        self.thread.start()
        log.info("NVDA Text Bridge: WebSocket server thread started")

    def stop(self):
        """Stop the WebSocket server"""
        if self.server and self.loop and self.running:
            async def shutdown():
                if self.server is not None:
                    self.server.close()
                    await self.server.wait_closed()
                    log.info("NVDA Text Bridge: WebSocket server stopped")
            
            future = asyncio.run_coroutine_threadsafe(shutdown(), self.loop)
            try:
                future.result(timeout=5)
            except:
                log.error("NVDA Text Bridge: Failed to stop WebSocket server gracefully")
        
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""
	NVDA Text Bridge Global Plugin
	Captures all text spoken by NVDA and outputs it to the View Log
	and sends it to connected WebSocket clients
	"""

	def __init__(self):
		"""Initialize the plugin and set up speech interception"""
		super().__init__()
		
		self._captureEnabled = True
		
		# Initialize WebSocket server
		self.ws_server = WebSocketServer()
		self.ws_server.start()

		pre_speechQueued.register(self._onPreSpeechQueued)
		
		log.info("NVDA Text Bridge: Plugin initialized - speech capture enabled")
	
	def _onPreSpeechQueued(self, speechSequence):
		"""
		Handler for pre_speechQueued event.
		Captures speech before it is queued and sends it to WebSocket clients.
		"""

		for chunk in speechSequence:
			if not isinstance(chunk, str):  # Not text (maybe a pitch change, beep, etc.). Not useful for us.
				continue
			log.info(f"NVDA Text Bridge: Raw speech sequence: {chunk}")
			# Send the speech text to WebSocket clients
			self.ws_server.send_message(chunk)
	
	def terminate(self):
		"""Clean up when the plugin is terminated"""
		try:
			pre_speechQueued.unregister(self._onPreSpeechQueued)
		except:
			pass
			
		# Stop the WebSocket server
		if hasattr(self, 'ws_server'):
			self.ws_server.stop()
			
		log.info("NVDA Text Bridge: Plugin terminated")
		super().terminate()
