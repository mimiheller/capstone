import paramiko
import getpass
import argparse
import sys
import time
import threading
import signal
import socket

fpga_ready_event = threading.Event()
conn = None
ssh_client = None

def signal_handler(sig, frame):
    print("\n Shutting down...")

    if conn: 
        print("Closing server socket...")
        conn.close()
    
    if ssh_client: 
        print("Closing SSH connection...")
        ssh_client.close()
    
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Establish initial SSH connection
def ssh_connect(hostname, username, password): 
    global ssh_client

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try: 
        ssh_client.connect(hostname, username=username, password=password)
        print("SSH connection successful...")

        start_server_and_fgpa_threads()

        while True: 
            time.sleep(1)

    except KeyboardInterrupt: 
        print("\n SSH connection closed...")
        ssh_client.close()
        sys.exit()

def start_ssh_connection(): 
    parser = argparse.ArgumentParser(description="SSH connection")
    parser.add_argument("username", help="SSH username")
    args = parser.parse_args()
    hostname = 'localhost'
    username = args.username
    password = getpass.getpass(f"Enter password for {username}@{hostname}: " )
    
    ssh_connect(hostname, username, password)

# Run a command via SSH 
def run_command(ssh, command): 
    try: 
        stdin, stdout, stderr = ssh.exec_command(command)
        return stdout.read().decode('utf-8')
    except Exception as e: 
        print(f"Failed to run command: {e}")
        return None

# Process text captured on hot key trigger
def trigger_bitnet(ssh_client, input_text):
    print("Generating result...")
    # Extract last 10 words
    def get_last_n_words(text, n=10):
        words = text.split()
        return " ".join(words[-n:]) if len(words) >= n else text

    context = get_last_n_words(input_text)
    return context

def wait_fpga(): 
    flag = 1 # change as necessary 
    while True: 
        if flag: 
            fpga_ready_event.set() 

        time.sleep(1)
    
def listen_on_connection():


    print("Starting TCP server...")
    host = 'localhost'
    port = 5050
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(1)

    print(f"Server listening on {host}:{port}...")
    
    while True:
        try: 
            conn, addr = server_socket.accept()
            print(f"Connection from {addr}")
            
            while True: 
                data = conn.recv(1024).decode('utf-8')
                
                if not data: 
                    break # connection closed 

                print(f"Recieved: {data}")
                fpga_ready_event.wait()
                result = trigger_bitnet(ssh_client, data)
                # send result back to lua 
                print(f"Result generated: {result}")
                conn.send(result.encode())
                time.sleep(1)
            
            print("Client disconnected")
            conn.close() 
        
        except ConnectionResetError: 
            print("Client disconnected unexpectedly (Connection reset by peer)")
            continue    # listen for new connection
        except OSError: 
            break       # socket closed 

def start_server_and_fgpa_threads(): 
    # Thread to check for FPGA readiness
    fpga_thread = threading.Thread(target=wait_fpga, daemon=True)
    fpga_thread.start()

    # Thread to check for input from user 
    connection_thread = threading.Thread(target=listen_on_connection, daemon=True)
    connection_thread.start()

start_ssh_connection()

# Keep the program alive while handling both connections
try:
    while True:
        time.sleep(1)  # Main thread sleeps, waiting for keyboard interrupt or other tasks
except KeyboardInterrupt:
    print("\nExiting program.")