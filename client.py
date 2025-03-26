import paramiko
import getpass
import argparse
import sys
import time
import threading
import signal
import socket
import subprocess

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
    username = "ubuntu"
    hostname = "172.24.58.116"
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
def trigger_bitnet(input_text):
    print("Generating result...")
    # Extract last 10 words
    def get_last_n_words(text, n=10):
        words = text.split()
        return " ".join(words[-n:]) if len(words) >= n else text

    context = get_last_n_words(input_text)
    return context

def scp_file_FPGA_device(remote_file, local_dest): 
    pword = "18-500E1"
    try: 
        subprocess.run(["sshpass", "-p", pword, "scp", "ubuntu@172.24.58.116:" + remote_file, local_dest], check=True)
        print(f"File {remote_file} successfully copied to {local_dest}")
    except Exception as e: 
        print(f"Failed to SCP file: {e}")

def scp_file_device_FPGA(file, dest): 
    pword = "18-500E1"
    try: 
        subprocess.run(["sshpass", "-p", pword, "scp", file, dest], check=True)
        #subprocess.run(["scp", file, dest])
    except Exception as e: 
        print(f"Failed to SCP file: {e}")

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
                context = trigger_bitnet(data)
                f = "prompt.txt"

                # Write data to the file
                with open(f, "w") as file:
                    file.write(context)

                # Wait for flag from FPGA
                while True:
                    # Check the flag (retrieve it from the remote server)
                    flag = run_command(ssh_client, "cat /home/ubuntu/test/flag.txt")
                    print(f"Flag: {flag}")
                    
                    # Check if the flag indicates that the transfer should happen
                    if flag.strip() == "True":  # assuming flag is a string 'True' or 'False'
                        print("Flag is True. Proceeding with SCP transfer...")
                        
                        # Set the flag to False
                        run_command(ssh_client, "echo False > /home/ubuntu/test/flag.txt")

                        # Trigger SCP transfer
                        dest = "ubuntu@172.24.58.116:/home/ubuntu/test"
                        scp_file_device_FPGA(f, dest)

                        # Check if file is in FPGA
                        print("Running command: cat prompt.txt")
                        print(run_command(ssh_client, "cat /home/ubuntu/test/prompt.txt"))

                        # Wait for flag to be set back to true 
                        while True:
                            flag = run_command(ssh_client, "cat /home/ubuntu/test/flag.txt")
                            if flag.strip() == "True":
                                print("Flag is True. Proceeding with SCP transfer back to client...")
                                scp_file_FPGA_device("/home/ubuntu/test/prompt.txt", "received_text_FPGA.txt")
                                break
                            
                            time.sleep(1)
                        break

                    # Continue checking every 1 second until flag is True
                    time.sleep(1)

                
                # result = trigger_bitnet(ssh_client, data)
                # # send result back to lua   - this is not working rn 
                # print(f"Result generated: {result}")
                # conn.send(result.encode())
                
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
    #fpga_thread = threading.Thread(target=wait_fpga, daemon=True)
    #fpga_thread.start()

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