import paramiko
import getpass
import sys
import time
import threading
import signal
import socket
import subprocess
import os

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

        start_server_thread()

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
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode('utf-8')
        return exit_status, output
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

                # Write context to file to scp to FPGA
                with open(f, "w") as file:
                    file.write(context)

                # Wait for flag from FPGA
                while True:

                    # Check the flag 
                    exit_status, flag = run_command(ssh_client, "cat /home/ubuntu/test/flag.txt")
                    print(f"Flag: {flag}")
                    
                    # Check FPGA is available
                    if flag.strip() == "True":  

                        # Set Flag Atomically
                        lock = "flock /home/ubuntu/test/flag.txt -c"
                        set_flag = "echo False > /home/ubuntu/test/flag.txt"
                        lock_flag = f"{lock} \"{set_flag}\""
                       
                        exit_status, cmd = run_command(ssh_client, lock_flag)

                        # make sure there isnt race condition with another client
                        if exit_status == 0: 
                            print("Flag is True. Proceeding with SCP transfer...")
                       
                            # Trigger SCP transfer
                            dest = "ubuntu@172.24.58.116:/home/ubuntu/test"
                            scp_file_device_FPGA(f, dest)

                            # Wait for flag to be set back to true - how do i deal with race cond here 
                            while True:
                                exit_status, flag = run_command(ssh_client, "cat /home/ubuntu/test/flag.txt")
                                if flag.strip() == "True":
                                    print("Proceeding with SCP transfer back to client...")
                                    scp_file_FPGA_device("/home/ubuntu/test/prompt.txt", "received_text_FPGA.txt")
                                    break
                                    
                                time.sleep(1)
                            break

                        else:
                            print("Could not acquire lock, retrying...")

                    # Continue checking every 1 second until flag is True
                    time.sleep(1)
                
                # Ensure file has been successfully transferred
                while not os.path.exists("received_text_FPGA.txt"):
                    print("Waiting for file transfer to complete...")
                    time.sleep(1)

                print("SCP transfer complete. Sending ACK...")
                
                ack_message = "ACK: File transfer complete\n"
                conn.sendall(ack_message.encode('utf-8'))

                time.sleep(1)
            
            print("Client disconnected")
            conn.close() 
        
        except ConnectionResetError: 
            print("Client disconnected unexpectedly (Connection reset by peer)")
            continue    # listen for new connection
        except OSError: 
            break       # socket closed 

def start_server_thread(): 
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