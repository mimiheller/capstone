import paramiko
import getpass
import subprocess

# Establish initial SSH connection
def ssh_connect(hostname, username, password): 
    global ssh_client

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(hostname, username=username, password=password)
    print("SSH connection successful...")

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

def scp_file(file, dest): 
    try: 
        subprocess.run(["scp", file, dest])
    except Exception as e: 
        print(f"Failed to SCP file: {e}")

f = "test.txt"
dest = "ubuntu@172.24.58.116:/home/ubuntu/test"

#print("scping file:")
#scp_file(f, dest)
# check if file is in FPGA 

start_ssh_connection()
flag = run_command(ssh_client, "cat /home/ubuntu/test/flag.txt")
print(f"Flag: {flag}")
