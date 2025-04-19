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
        if exit_status != 0: 
            error = stderr.read().decode('utf-8')
        else: 
            error = None

        output = stdout.read().decode('utf-8')

        return exit_status, output, error
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

    while True:
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow reusing the port
            server_socket.bind((host, port))
            server_socket.listen(1)

            print(f"Server listening on {host}:{port}...")
            break  

        except OSError as e:
            if e.errno == 48:  # Address already in use
                print(f"Port {port} already in use. Retrying in 5 seconds...")
                time.sleep(5)
            else:
                raise  

    while True:
        try: 
            conn, addr = server_socket.accept()
            print(f"Connection from {addr}")

            client_done = False
            
            while not client_done: 
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
                    exit_status, FPGA_available, _ = run_command(ssh_client, "cat /home/ubuntu/test/flag.txt")
                    
                    # Check FPGA is available
                    if FPGA_available.strip() == "False":
                        _ , check_2, _ = run_command(ssh_client, "cat /home/ubuntu/test/output_ready.txt")
                        print(f"output_ready: {check_2}")
                        print("Proceeding with SCP transfer...")

                        # SCP file
                        dest = "ubuntu@172.24.58.116:/home/ubuntu/test"
                        scp_file_device_FPGA(f, dest)  

                        # Set Flag 
                        set_flag_true = "echo True > /home/ubuntu/test/flag.txt"
                        run_command(ssh_client, set_flag_true)
                        # Wait for data ready flag 
                        while True:
                            _ , data_ready, _ = run_command(ssh_client, "cat /home/ubuntu/test/output_ready.txt")
                            if data_ready.strip() == "True":
                                print("Proceeding with SCP transfer back to client...")
                                _ , check, _ = run_command(ssh_client, "cat /home/ubuntu/test/response.txt")
                                print(f"response: {check}")
                                scp_file_FPGA_device("/home/ubuntu/test/response.txt", "received_text_FPGA.txt")
                                scp_file_FPGA_device("/home/ubuntu/test/power.txt", "power.txt")
                                break 
                            time.sleep(1)
                        
                        break

                    else:
                        print("Waiting for other user...")

                    # Continue checking every 1 second until flag is True
                    time.sleep(1)

                # Ensure file has been successfully transferred
                while not (os.path.exists("received_text_FPGA.txt") and os.path.exists("power.txt")):
                    print("Waiting for file transfer to complete...")
                    time.sleep(1)
                


                print("SCP transfer complete...")
                ack_message = "ACK: File transfer complete\n"
                conn.sendall(ack_message.encode('utf-8'))
                
                # Set flags for next user
                run_command(ssh_client, "echo False > /home/ubuntu/test/output_ready.txt")
                run_command(ssh_client, "echo False > /home/ubuntu/test/flag.txt")
                
                

                client_done = True
                

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
