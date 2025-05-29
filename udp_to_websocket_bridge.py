import asyncio
import websockets
import socket
import json
import logging

# Configuration
UDP_IP = "127.0.0.1"
UDP_PORT = 12345
WEBSOCKET_HOST = "localhost"
WEBSOCKET_PORT = 8765

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set to store connected WebSocket clients
connected_clients = set()

async def send_to_client(client, message):
    """Safely send a message to a single WebSocket client."""
    try:
        await client.send(message)
    except websockets.exceptions.ConnectionClosed:
        logging.info(f"Client {client.remote_address} disconnected during send. Will be removed if not already.")
        # The main websocket_handler's finally block will handle removal from connected_clients
    except Exception as e:
        logging.error(f"Error sending to client {client.remote_address}: {e}")

class UDPServerProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport
        logging.info(f"UDP listener started on {UDP_IP}:{UDP_PORT}")

    def datagram_received(self, data, addr):
        message_content = data.decode('utf-8')
        logging.info(f"UDP | Received from {addr}: {message_content}")

        # Prepare JSON message for WebSocket clients
        json_payload = json.dumps({"type": "speech", "text": message_content})

        # Broadcast to all connected WebSocket clients
        clients_to_send = list(connected_clients) # Iterate over a copy
        if not clients_to_send:
            logging.info("UDP | No WebSocket clients connected to forward the message.")
        
        for client in clients_to_send:
            asyncio.create_task(send_to_client(client, json_payload))
            logging.info(f"WS  | Sent to {client.remote_address}: {message_content}")


    def error_received(self, exc):
        logging.error(f"UDP | Error received: {exc}")

    def connection_lost(self, exc):
        logging.info("UDP | Listener stopped.")

async def websocket_handler(websocket): # Removed 'path' argument
    """Handles WebSocket client connections."""
    connected_clients.add(websocket)
    logging.info(f"WS  | Client connected: {websocket.remote_address}")
    try:
        # Keep the connection alive until the client disconnects
        await websocket.wait_closed()
    except websockets.exceptions.ConnectionClosedError:
        logging.info(f"WS  | Client connection closed error: {websocket.remote_address}")
    finally:
        connected_clients.remove(websocket)
        logging.info(f"WS  | Client disconnected: {websocket.remote_address}")

async def main():
    """Main function to start UDP listener and WebSocket server."""
    loop = asyncio.get_running_loop()

    # Start UDP server
    logging.info(f"Starting UDP server on {UDP_IP}:{UDP_PORT}...")
    udp_transport, udp_protocol = await loop.create_datagram_endpoint(
        lambda: UDPServerProtocol(),
        local_addr=(UDP_IP, UDP_PORT)
    )

    # Start WebSocket server
    logging.info(f"Starting WebSocket server on {WEBSOCKET_HOST}:{WEBSOCKET_PORT}...")
    async with websockets.serve(websocket_handler, WEBSOCKET_HOST, WEBSOCKET_PORT):
        logging.info("UDP to WebSocket bridge is running. Press Ctrl+C to stop.")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bridge shutting down...")
    except Exception as e:
        logging.error(f"Unhandled exception in main: {e}")
